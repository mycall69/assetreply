"""지표 모달의 일자별 표 (014 반복 2026-10-10b T105) — FR-013, FR-014, FR-016, FR-018, FR-029,
SC-012, contracts A7.

- 주식 일자별 표(012)와 같은 꼴·쪽 넘기기다(`kind`·`shiftedFrom`·`isOngoing`,
  `before`·`limit`·`hasMore`·`oldestReturned`)
- 칸: 시가·고가·저가·종가·대비·등락률(문자열, 없으면 `null`). 오늘(현지) 잠정 행은 카드 값이고
  시가·고가·저가가 `null`이다
- 과거 구간이 다 받아지지 않았으면 그래프와 같은 202다. 틀린 `period`는 400 `invalid_query`, 없는
  지표는 404다
- 환율은 고시 이력이고 시가·고가·저가가 `null`, `seriesNote: "fx_fixing"`이다
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest
from httpx2 import ASGITransport, AsyncClient

from src.api.main import create_app
from src.api.routes import dashboard_table
from src.api.services import market_quotes
from src.db.models import FxCoverage, FxRate
from src.db.session import get_session
from src.repository import market_daily
from src.simulation.market_quote import MarketQuote, Previous

D = dt.date
NOW = dt.datetime(2026, 10, 9, 14, 0, tzinfo=dt.UTC)
AT = dt.datetime(2026, 10, 9, 5, 0)


def weekdays(start: dt.date, end: dt.date) -> list[dt.date]:
    out, day = [], start
    while day <= end:
        if day.weekday() < 5:
            out.append(day)
        day += dt.timedelta(days=1)
    return out


DAYS = weekdays(D(2026, 8, 3), D(2026, 10, 8))


class Quotes:
    async def quote(self, indicator_id: str) -> MarketQuote | None:
        return MarketQuote(
            value=Decimal("7800.000000"),
            value_time=NOW,
            session_date=D(2026, 10, 9),
            state="open",
            provisional=True,
            delay_minutes=None,
            previous=Previous(Decimal("7765.360000"), D(2026, 10, 8), "history"),
            change=Decimal("34.640000"),
            change_rate=Decimal("0.004461"),
            change_rate_blank=None,
            direction="up",
        )


@pytest.fixture
async def client(session_factory, monkeypatch):  # type: ignore[no-untyped-def]
    market_quotes.set_shared_service(Quotes())  # type: ignore[arg-type]
    monkeypatch.setattr(dashboard_table, "utc_now", lambda: NOW)
    app = create_app()

    async def _session():  # type: ignore[no-untyped-def]
        async with session_factory() as s:
            yield s

    app.dependency_overrides[get_session] = _session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    market_quotes.set_shared_service(None)


def ohlc_of(i: int) -> tuple[Decimal, Decimal, Decimal]:
    return (Decimal(100 + i) - 1, Decimal(100 + i) + 5, Decimal(100 + i) - 5)


async def seed(factory, days=DAYS, *, first=None) -> None:  # type: ignore[no-untyped-def]
    async with factory() as s:
        await market_daily.store_closes(
            s,
            "sp500",
            [(d, Decimal(100 + i)) for i, d in enumerate(days)],
            detected_at=AT,
            ohlc={d: ohlc_of(i) for i, d in enumerate(days)},
        )
        await market_daily.record_coverage(s, "sp500", days[0], days[-1])
        await market_daily.record_first_day(s, "sp500", first or days[0])
        await market_daily.record_success(s, "sp500", at=AT)
        await s.commit()


async def test_일_표는_최신부터이고_오늘_잠정_행이_먼저다(
    client: AsyncClient, session_factory
) -> None:  # type: ignore[no-untyped-def]
    await seed(session_factory)
    body = (await client.get("/api/dashboard/indicators/sp500/table?period=daily&limit=3")).json()
    assert body["period"] == "daily" and body["seriesNote"] is None
    today, last, before = body["rows"]
    assert today == {
        "kind": "period",
        "date": "2026-10-09",
        "open": None,
        "high": None,
        "low": None,
        "close": "7800.000000",
        "change": str(Decimal("7800") - Decimal(100 + len(DAYS) - 1)) + ".000000",
        "changeRate": today["changeRate"],
        "provisional": True,
    }
    i = len(DAYS) - 1
    o, h, low = ohlc_of(i)
    assert (last["date"], last["open"], last["high"], last["low"], last["close"]) == (
        "2026-10-08",
        f"{o}.000000",
        f"{h}.000000",
        f"{low}.000000",
        f"{100 + i}.000000",
    )
    assert last["change"] == "1.000000" and last["provisional"] is False
    assert before["date"] == "2026-10-07"
    assert body["hasMore"] is True and body["oldestReturned"] == "2026-10-07"


async def test_더_받기는_before_앞이다(client: AsyncClient, session_factory) -> None:  # type: ignore[no-untyped-def]
    await seed(session_factory)
    page = (
        await client.get("/api/dashboard/indicators/sp500/table?limit=3&before=2026-10-07")
    ).json()
    assert [r["date"] for r in page["rows"]] == ["2026-10-06", "2026-10-05", "2026-10-02"]


async def test_주_표는_대표일과_진행_중_표시다(client: AsyncClient, session_factory) -> None:  # type: ignore[no-untyped-def]
    await seed(session_factory)
    body = (await client.get("/api/dashboard/indicators/sp500/table?period=weekly&limit=2")).json()
    this_week, last_week = body["rows"]
    assert this_week["date"] == "2026-10-09" and this_week["isOngoing"] is True
    assert last_week["date"] == "2026-10-02" and "shiftedFrom" not in last_week
    # 지난주 행의 시가 = 그 주 첫 거래일(09-28) 시가
    i = DAYS.index(D(2026, 9, 28))
    assert last_week["open"] == f"{ohlc_of(i)[0]}.000000"


async def test_틀린_period는_400이다(client: AsyncClient, session_factory) -> None:  # type: ignore[no-untyped-def]
    await seed(session_factory)
    res = await client.get("/api/dashboard/indicators/sp500/table?period=yearly")
    assert res.status_code == 400 and res.json()["status"] == "invalid_query"


async def test_과거_구간이_남았으면_202다(client: AsyncClient, session_factory) -> None:  # type: ignore[no-untyped-def]
    await seed(session_factory, first=D(1927, 12, 30))
    res = await client.get("/api/dashboard/indicators/sp500/table")
    assert res.status_code == 202 and res.json()["status"] == "collecting"


async def test_없는_지표는_404다(client: AsyncClient) -> None:
    assert (await client.get("/api/dashboard/indicators/nope/table")).status_code == 404


async def test_환율은_고시_이력이고_시가가_없다(client: AsyncClient, session_factory) -> None:  # type: ignore[no-untyped-def]
    days = weekdays(D(2026, 9, 1), D(2026, 10, 8))
    async with session_factory() as s:
        for i, d in enumerate(days):
            s.add(
                FxRate(
                    currency_code="USD",
                    quote_date=d,
                    base_rate=Decimal("1300") + i,
                    quote_unit=1,
                    source="ecos",
                    is_provisional=d == days[-1],
                )
            )
        s.add(FxCoverage(currency_code="USD", covered_from=days[0], covered_through=D(2026, 10, 9)))
        await s.commit()
    body = (await client.get("/api/dashboard/indicators/usd/table?limit=2")).json()
    assert body["seriesNote"] == "fx_fixing"
    first = body["rows"][0]
    assert first["date"] == days[-1].isoformat()
    assert (first["open"], first["high"], first["low"]) == (None, None, None)
    assert first["provisional"] is True  # 외환 잠정 고시
