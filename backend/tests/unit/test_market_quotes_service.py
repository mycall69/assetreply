"""현재 시세 서비스 (014 T022) — FR-008, FR-009, SC-007, research R14-6.

가짜 출처·가짜 이력·가짜 시계로 본다(네트워크·DB 없음).

- 30초 안의 두 요청은 출처 한 번이다. 동시에 온 두 요청도 한 번이다(단일 비행 — 탭이 여럿이어도)
- 출처 실패는 10초만 기억한다
- 마지막 성공 값이 있으면 그 지표는 `stale` + 실패, 없으면 `failed` + 값 없음이다
- 한 심볼이 빠지면 그 지표만 실패다
- **사건**(반복 2026-10-10 T089 — FR-009)
  - 응답 전체 실패는 `market_quotes_failed`, 일부 지표만 실패는 `market_quotes_partial` 한 줄이다
  - 실패 기억 안의 재요청은 출처를 부르지 않으므로 줄도 없다
  - 성공은 남기지 않는다(30초마다라 로그가 넘친다)
"""

from __future__ import annotations

import asyncio
import dataclasses
import datetime as dt
from collections.abc import Sequence
from decimal import Decimal

from _pytest.monkeypatch import MonkeyPatch

from src.api.services import market_quotes
from src.api.services.market_quotes import MarketQuoteService
from src.config.settings import load_settings
from src.ingestion.yahoo.errors import StockSourceRateLimited
from src.ingestion.yahoo.market import Failure, QuoteFetch
from src.simulation.market_indicators import INDICATORS
from src.simulation.market_quote import SourceQuote

T0 = dt.datetime(2026, 10, 9, 5, 30, tzinfo=dt.UTC)
IDS = [i.id for i in INDICATORS]


def quote(price: str = "100") -> SourceQuote:
    return SourceQuote(
        price=Decimal(price),
        market_time=T0 - dt.timedelta(minutes=1),
        full_day_change=Decimal("1"),
        chart_previous_close=Decimal("99"),
        session_start=None,
    )


class Clock:
    def __init__(self) -> None:
        self.now = T0

    def __call__(self) -> dt.datetime:
        return self.now


class Source:
    def __init__(self) -> None:
        self.calls = 0
        self.fail: Exception | None = None
        self.missing: set[str] = set()
        self.gate = asyncio.Event()
        self.gate.set()

    async def fetch_quotes(self, indicator_ids: Sequence[str]) -> QuoteFetch:
        self.calls += 1
        await self.gate.wait()
        if self.fail is not None:
            raise self.fail
        return QuoteFetch(
            {i: quote() for i in indicator_ids if i not in self.missing},
            {i: Failure("not_found", "없음") for i in self.missing},
        )


class History:
    def __init__(self) -> None:
        self.asked: list[tuple[str, dt.date]] = []

    async def previous_close(
        self, indicator_id: str, before: dt.date
    ) -> tuple[dt.date, Decimal] | None:
        self.asked.append((indicator_id, before))
        return (before - dt.timedelta(days=1), Decimal("98.000000"))

    async def coverage_through(self, indicator_id: str) -> dt.date | None:
        return T0.date()


def service(source: Source, clock: Clock, history: History | None = None) -> MarketQuoteService:
    settings = dataclasses.replace(
        load_settings(),
        market_quote_cache_seconds=30,
        market_quote_failure_cache_seconds=10,
        dashboard_refresh_seconds=60,
    )
    return MarketQuoteService(source, history or History(), settings, clock=clock)


def by_id(body: dict[str, object]) -> dict[str, dict[str, object]]:
    items = body["indicators"]
    assert isinstance(items, list)
    return {str(i["id"]): i for i in items}


async def test_30초_안의_두_요청은_출처_한_번() -> None:
    source, clock = Source(), Clock()
    svc = service(source, clock)
    await svc.quotes_body()
    clock.now += dt.timedelta(seconds=29)
    await svc.quotes_body()
    assert source.calls == 1
    clock.now += dt.timedelta(seconds=2)
    await svc.quotes_body()
    assert source.calls == 2


async def test_동시에_온_두_요청도_한_번() -> None:
    source, clock = Source(), Clock()
    source.gate.clear()
    svc = service(source, clock)
    first = asyncio.create_task(svc.quotes_body())
    second = asyncio.create_task(svc.quotes_body())
    await asyncio.sleep(0)
    source.gate.set()
    await asyncio.gather(first, second)
    assert source.calls == 1


async def test_본문은_늘_15개이고_차례대로() -> None:
    body = await service(Source(), Clock()).quotes_body()
    items = body["indicators"]
    assert isinstance(items, list)
    assert [i["id"] for i in items] == IDS
    assert body["refreshAfterSeconds"] == 60 and body["source"] == "Yahoo Finance"
    assert body["fetchedAt"] == "2026-10-09T05:30:00Z"


async def test_이력의_전일을_세션_날짜로_찾는다() -> None:
    history = History()
    body = await service(Source(), Clock(), history).quotes_body()
    kospi = by_id(body)["kospi"]["quote"]
    assert isinstance(kospi, dict)
    previous = kospi["previous"]
    assert isinstance(previous, dict) and previous["from"] == "history"
    asked = dict(history.asked)
    assert "usd" not in asked  # 환율은 이력을 묻지 않는다(시장 환율 — 출처)
    assert asked["kospi"] == dt.date(2026, 10, 9)


async def test_출처_실패는_10초만_기억한다() -> None:
    source, clock = Source(), Clock()
    source.fail = StockSourceRateLimited("한도")
    svc = service(source, clock)
    body = await svc.quotes_body()
    kospi = by_id(body)["kospi"]
    assert (kospi["status"], kospi["quote"], kospi["stale"]) == ("failed", None, False)
    assert kospi["failure"] == {"kind": "rate_limited", "message": "한도"}
    clock.now += dt.timedelta(seconds=9)
    await svc.quotes_body()
    assert source.calls == 1
    clock.now += dt.timedelta(seconds=2)
    await svc.quotes_body()
    assert source.calls == 2


async def test_마지막_성공_값을_새로_받지_못함으로_보인다() -> None:
    source, clock = Source(), Clock()
    svc = service(source, clock)
    await svc.quotes_body()
    source.fail = StockSourceRateLimited("한도")
    clock.now += dt.timedelta(seconds=31)
    body = await svc.quotes_body()
    kospi = by_id(body)["kospi"]
    assert (kospi["status"], kospi["stale"]) == ("ok", True)
    assert isinstance(kospi["quote"], dict) and kospi["quote"]["value"] == "100.000000"
    assert kospi["failure"] == {"kind": "rate_limited", "message": "한도"}


async def test_한_심볼만_빠지면_그_지표만_실패() -> None:
    source = Source()
    source.missing = {"shanghai"}
    body = await service(source, Clock()).quotes_body()
    items = by_id(body)
    assert items["shanghai"]["status"] == "failed"
    assert items["shanghai"]["failure"] == {"kind": "not_found", "message": "없음"}
    assert {k for k, v in items.items() if v["status"] == "ok"} == set(IDS) - {"shanghai"}


async def test_한_지표의_값() -> None:
    svc = service(Source(), Clock())
    q = await svc.quote("sp500")
    assert q is not None and q.value == Decimal("100.000000")
    assert await svc.quote("kospii") is None


Events = list[tuple[str, dict[str, object]]]


def capture(monkeypatch: MonkeyPatch) -> Events:
    seen: Events = []
    monkeypatch.setattr(market_quotes, "_event", lambda name, **fields: seen.append((name, fields)))
    return seen


async def test_응답_전체_실패는_한_줄이고_기억_안은_없다(monkeypatch: MonkeyPatch) -> None:
    events = capture(monkeypatch)
    clock, source = Clock(), Source()
    source.fail = StockSourceRateLimited("시세 출처의 호출 한도를 소진했습니다.")
    quotes = service(source, clock)
    await quotes.quotes_body()
    clock.now += dt.timedelta(seconds=5)
    await quotes.quotes_body()
    assert events == [
        (
            "market_quotes_failed",
            {"kind": "rate_limited", "detail": "시세 출처의 호출 한도를 소진했습니다."},
        )
    ]


async def test_일부_지표만_실패는_한_줄이다(monkeypatch: MonkeyPatch) -> None:
    events = capture(monkeypatch)
    clock, source = Clock(), Source()
    source.missing = {"shanghai", "vix"}
    await service(source, clock).quotes_body()
    assert events == [
        ("market_quotes_partial", {"failed": {"shanghai": "not_found", "vix": "not_found"}})
    ]


async def test_성공만이면_남기지_않는다(monkeypatch: MonkeyPatch) -> None:
    events = capture(monkeypatch)
    clock, source = Clock(), Source()
    await service(source, clock).quotes_body()
    assert events == []


def test_실제_로거에_남겨도_예외가_없다() -> None:
    """`message` 같은 `LogRecord` 예약 이름을 칸으로 쓰면 로거가 예외를 낸다(대역은 모른다)."""
    market_quotes._event("market_quotes_failed", kind="connection", detail="연결 실패")
