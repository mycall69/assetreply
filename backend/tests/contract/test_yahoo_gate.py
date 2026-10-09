"""주식과 대시보드가 함께 지나는 Yahoo 관문 (014 T008) — FR-019, FR-026, research R14-10.

같은 출처(Yahoo 비공식 엔드포인트)다. 클라이언트마다 세마포어를 따로 가지면 **합친 호출을 아무도
보지 않아**, 대시보드 수집과
주식 수집이 합쳐 출처 한도를 넘긴다(008 `EcosGate`와 같은 까닭). 관문은 이벤트 루프마다 하나다:

- 동시에 나가는 Yahoo 요청 수를 `YAHOO_MAX_CONCURRENT_REQUESTS`로 묶는다
- 누가 429를 받아 `pause`하면 그동안 **모두의 다음 요청**이 기다린다

주식 클라이언트(`YahooStockClient`)의 관문은 **선택 인자**다 — 넘기지 않으면 지금 동작
그대로다(FR-026, 기존 계약 테스트 불변).
"""

from __future__ import annotations

import asyncio
import dataclasses
import datetime as dt
from pathlib import Path
from typing import Self

import pytest

from src.config.settings import Settings, load_settings
from src.ingestion.yahoo.client import YahooStockClient
from src.ingestion.yahoo.errors import StockSourceRateLimited
from src.ingestion.yahoo.gate import YahooGate, get_yahoo_gate

STOCK = Path(__file__).parent / "fixtures" / "stock"
NOW = dt.datetime(2026, 10, 3, 0, 0, tzinfo=dt.UTC)
TOYOTA = (dt.date(2021, 9, 1), dt.date(2021, 10, 29))


def _settings(**over: object) -> Settings:
    return dataclasses.replace(load_settings(), **over)  # type: ignore[arg-type]


class Resp:
    def __init__(self, body: str, status: int = 200) -> None:
        self._body = body
        self.status = status

    async def text(self) -> str:
        return self._body

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *exc: object) -> None:
        return None


class Session:
    """`interval`별 응답 목록을 차례로 돌려준다. 목록 끝에 닿으면 마지막 것을 되풀이한다."""

    def __init__(self, routes: dict[str, list[Resp]]) -> None:
        self.routes = routes
        self.calls: dict[str, int] = {}

    def get(self, url: str, *, params: dict[str, str] | None = None, **_: object) -> Resp:
        interval = (params or {})["interval"]
        n = self.calls.get(interval, 0)
        self.calls[interval] = n + 1
        items = self.routes[interval]
        return items[min(n, len(items) - 1)]

    async def close(self) -> None:
        return None


def _toyota_routes(*, first_429: bool) -> dict[str, list[Resp]]:
    chunk = Resp((STOCK / "chart_split_float.json").read_text(encoding="utf-8"))
    splits = Resp((STOCK / "splits_toyota_since_2021_09.json").read_text(encoding="utf-8"))
    head = [Resp("Too Many Requests", 429)] if first_429 else []
    return {"1d": [*head, chunk], "1mo": [splits]}


async def test_동시_자리는_한도를_넘지_않는다() -> None:
    gate = YahooGate(2)
    now = 0
    peak = 0
    release = asyncio.Event()

    async def one() -> None:
        nonlocal now, peak
        async with gate.slot():
            now += 1
            peak = max(peak, now)
            await release.wait()
            now -= 1

    tasks = [asyncio.create_task(one()) for _ in range(5)]
    await asyncio.sleep(0)
    await asyncio.sleep(0)
    release.set()
    await asyncio.gather(*tasks)
    assert peak == 2


async def test_pause하면_다른_쪽의_자리가_기다린다(monkeypatch: pytest.MonkeyPatch) -> None:
    gate = YahooGate(2)
    order: list[str] = []
    resume = asyncio.Event()

    async def held_sleep(seconds: float) -> None:
        order.append(f"sleep {seconds}")
        await resume.wait()

    monkeypatch.setattr(asyncio, "sleep", held_sleep)

    async def other() -> None:
        async with gate.slot():
            order.append("other")

    pausing = asyncio.create_task(gate.pause(3.0))
    for _ in range(3):
        await asyncio.wait([pausing], timeout=0)
    waiting = asyncio.create_task(other())
    for _ in range(3):
        await asyncio.wait([waiting], timeout=0)
    assert order == ["sleep 3.0"]  # 쉬는 동안 다른 쪽이 나가지 않는다
    resume.set()
    await asyncio.gather(pausing, waiting)
    assert order == ["sleep 3.0", "other"]


async def test_관문은_이벤트_루프마다_하나다() -> None:
    settings = _settings(yahoo_max_concurrent_requests=3)
    first = get_yahoo_gate(settings)
    assert get_yahoo_gate(settings) is first


def test_다른_루프는_다른_관문이다() -> None:
    settings = _settings(yahoo_max_concurrent_requests=3)

    async def grab() -> YahooGate:
        return get_yahoo_gate(settings)

    assert asyncio.run(grab()) is not asyncio.run(grab())


async def test_관문_없는_주식_클라이언트는_지금_그대로다(no_sleep: list[float]) -> None:
    """FR-026 — 기본값 `None`은 429 뒤 재시도·백오프가 014 전과 같다."""
    settings = _settings(stock_retry_max_attempts=2, stock_retry_base_delay_ms=1000)
    session = Session(_toyota_routes(first_429=True))
    async with YahooStockClient(settings, session=session, now=lambda: NOW) as yahoo:  # type: ignore[arg-type]
        fetched = await yahoo.fetch_chart("7203.T", *TOYOTA)
    assert session.calls == {"1d": 2, "1mo": 1}
    assert len(no_sleep) == 1 and 1.0 <= no_sleep[0] < 2.0  # 첫 재시도 백오프(지터 포함)
    assert fetched.data.prices


async def test_관문을_넘긴_주식_클라이언트는_429에_관문을_쉬게_한다(
    monkeypatch: pytest.MonkeyPatch, no_sleep: list[float]
) -> None:
    settings = _settings(stock_retry_max_attempts=2, stock_retry_base_delay_ms=1000)
    gate = YahooGate(2)
    paused: list[float] = []
    original = gate.pause

    async def spy(seconds: float) -> None:
        paused.append(seconds)
        await original(seconds)

    monkeypatch.setattr(gate, "pause", spy)
    session = Session(_toyota_routes(first_429=True))
    async with YahooStockClient(settings, session=session, now=lambda: NOW, gate=gate) as yahoo:  # type: ignore[arg-type]
        with_gate = await yahoo.fetch_chart("7203.T", *TOYOTA)
    assert len(paused) == 1 and 1.0 <= paused[0] < 2.0
    assert session.calls == {"1d": 2, "1mo": 1}

    plain = Session(_toyota_routes(first_429=False))
    async with YahooStockClient(settings, session=plain, now=lambda: NOW) as yahoo:  # type: ignore[arg-type]
        without = await yahoo.fetch_chart("7203.T", *TOYOTA)
    assert with_gate.data == without.data  # 값은 관문과 무관하다


async def test_관문을_넘겨도_재시도가_끝나면_한도_오류다(no_sleep: list[float]) -> None:
    settings = _settings(stock_retry_max_attempts=2)
    session = Session({"1d": [Resp("Too Many Requests", 429)], "1mo": [Resp("{}")]})
    async with YahooStockClient(
        settings, session=session, now=lambda: NOW, gate=YahooGate(1)
    ) as yahoo:  # type: ignore[arg-type]
        with pytest.raises(StockSourceRateLimited):
            await yahoo.fetch_chart("7203.T", *TOYOTA)
    assert session.calls["1d"] == 2
