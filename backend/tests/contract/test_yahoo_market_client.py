"""대시보드 일봉 청크 계약 (014 T042) — FR-017, FR-019, research R14-2~R14-4, 헌법 원칙 II·III·V.

**네트워크를 쓰지 않는다**(원칙 III). 실측 본문(`fixtures/market/`)을 쓴다.

- **거래일은 `zoneinfo`다** — 겨울에 받은 응답(`gmtoffset` −18000)에서도 여름 자정 봉이 뉴욕 날짜다.
  고정 오프셋이면 하루 앞당겨진다
- 종가가 빈 행(휴일 자리 표시)은 버린다
- 오늘(현지) 봉은 확정으로 내지 않는다 — `today_bar`로 따로 둔다
- 첫 거래일을 읽는다. 1970년 이전은 음수 `period1`이다(날짜에서 계산 — 상수 없음)
- 숫자는 `Decimal`이다
"""

from __future__ import annotations

import dataclasses
import datetime as dt
from decimal import Decimal
from pathlib import Path
from typing import Self

from src.config.settings import load_settings
from src.ingestion.yahoo.gate import YahooGate
from src.ingestion.yahoo.market import YahooMarketClient

FIX = Path(__file__).parent / "fixtures" / "market"
D = dt.date


class Resp:
    def __init__(self, text: str, status: int = 200) -> None:
        self._text = text
        self.status = status

    async def text(self) -> str:
        return self._text

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *exc: object) -> None:
        return None


class Session:
    def __init__(self, name: str, status: int = 200) -> None:
        self.text = (FIX / name).read_text(encoding="utf-8") if status == 200 else name
        self.status = status
        self.requests: list[tuple[str, dict[str, str]]] = []

    def get(self, url: str, *, params: dict[str, str] | None = None, **_: object) -> Resp:
        self.requests.append((url.split(".com", 1)[1], dict(params or {})))
        return Resp(self.text, self.status)

    async def close(self) -> None:
        return None


def client(session: Session) -> YahooMarketClient:
    settings = dataclasses.replace(load_settings(), market_retry_max_attempts=1)
    return YahooMarketClient(settings, session=session, gate=YahooGate(2))  # type: ignore[arg-type]


def epoch(day: dt.date) -> int:
    return int(dt.datetime.combine(day, dt.time.min, dt.UTC).timestamp())


async def test_청크_요청은_period1_period2_1d() -> None:
    session = Session("chart_KS11_2024_2025.json")
    async with client(session) as yahoo:
        fetched = await yahoo.fetch_daily(
            "kospi", D(2024, 1, 1), D(2025, 12, 31), current_date=D(2026, 10, 9)
        )
    path, params = session.requests[0]
    assert path == "/v8/finance/chart/^KS11"
    assert params == {
        "period1": str(epoch(D(2024, 1, 1))),
        "period2": str(epoch(D(2025, 12, 31)) + 86_399),
        "interval": "1d",
    }
    assert (fetched.requested_from, fetched.requested_to, fetched.status) == (
        D(2024, 1, 1),
        D(2025, 12, 31),
        200,
    )
    assert fetched.raw == session.text
    assert len(fetched.chunk.closes) == 486
    assert fetched.chunk.first_trade_date == D(1996, 12, 11)


async def test_겨울에_받아도_여름_자정_봉은_뉴욕_날짜다() -> None:
    session = Session("chart_CL_F_2020_winter_fetch.json")
    async with client(session) as yahoo:
        fetched = await yahoo.fetch_daily(
            "wti", D(2020, 1, 1), D(2021, 3, 31), current_date=D(2026, 10, 9)
        )
    days = dict(fetched.chunk.closes)
    assert D(2020, 7, 1) in days and D(2020, 6, 30) in days
    assert days[D(2020, 7, 1)] == Decimal("39.820000")
    assert D(2020, 1, 2) in days
    # 음수 종가를 그대로 읽는다. 출처의 float32 잡음(−37.630001068…)은 소수 6자리까지 남는다 —
    # 주식과 같은 자릿수 규칙이고,
    # 출처의 `priceHint`(2)로 깎지 않는다(나스닥 전일 27538.691처럼 실제 값이 더 긴 자릿수를 갖는다)
    assert days[D(2020, 4, 20)] == Decimal("-37.630001")
    assert all(d.weekday() < 5 for d in days)  # 하루 밀려 주말이 생기지 않는다


async def test_종가가_빈_행은_버린다() -> None:
    session = Session("chart_KS11_1996.json")
    async with client(session) as yahoo:
        fetched = await yahoo.fetch_daily(
            "kospi", D(1996, 12, 1), D(1997, 12, 31), current_date=D(2026, 10, 9)
        )
    days = dict(fetched.chunk.closes)
    assert D(1996, 12, 25) not in days and D(1997, 1, 1) not in days
    assert len(days) == 276 - 21
    assert fetched.chunk.first_trade_date == D(1996, 12, 11)
    assert min(days) == D(1996, 12, 11)


async def test_1970년_이전은_음수_epoch이고_첫_거래일을_읽는다() -> None:
    session = Session("chart_GSPC_1927.json")
    async with client(session) as yahoo:
        fetched = await yahoo.fetch_daily(
            "sp500", D(1927, 12, 30), D(1929, 12, 31), current_date=D(2026, 10, 9)
        )
    assert int(session.requests[0][1]["period1"]) < 0
    assert fetched.chunk.first_trade_date == D(1927, 12, 30)
    assert fetched.chunk.closes[0] == (D(1927, 12, 30), Decimal("17.660000"))


async def test_오늘_봉은_확정으로_내지_않는다() -> None:
    session = Session("chart_GSPC_open_today.json")
    async with client(session) as yahoo:
        fetched = await yahoo.fetch_daily(
            "sp500", D(2026, 10, 5), D(2026, 10, 9), current_date=D(2026, 10, 9)
        )
    assert [d for d, _ in fetched.chunk.closes] == [
        D(2026, 10, 5),
        D(2026, 10, 6),
        D(2026, 10, 7),
        D(2026, 10, 8),
    ]
    assert fetched.chunk.today_bar is not None and fetched.chunk.today_bar[0] == D(2026, 10, 9)
    for _, value in fetched.chunk.closes:
        assert isinstance(value, Decimal)


async def test_구간에_시세가_없으면_빈_결과() -> None:
    body = (
        '{"chart": {"result": null, "error": {"code": "Bad Request", '
        '"description": "Data doesn\'t exist for startDate = 1, endDate = 2"}}}'
    )
    session = Session(body, status=400)
    async with client(session) as yahoo:
        fetched = await yahoo.fetch_daily(
            "sox", D(1980, 1, 1), D(1981, 12, 31), current_date=D(2026, 10, 9)
        )
    assert fetched.chunk.closes == [] and fetched.chunk.first_trade_date is None
