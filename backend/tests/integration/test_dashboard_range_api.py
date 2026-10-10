"""지표 모달의 기간 8개 (014 반복 2026-10-10b T105) — FR-011, FR-012, FR-016, FR-018, FR-028,
contracts A2.

- `range`는 보는 기간이다. 월 이상은 그 기간의 **일봉 전부**다(점을 묶지 않는다). 틀리거나 없으면
  1년, 옛 `unit`은 무시한다
- 일·주(`1d`·`5d`)는 장중 시세 서비스의 본문이다 — 이력 수집과 무관하다(202가 없다)
- 환율의 장중은 시장 환율이고 그 사실을 밝힌다
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest
from httpx2 import ASGITransport, AsyncClient
from src.simulation.indicator_range import range_start

from src.api.main import create_app
from src.api.routes import dashboard_series
from src.api.services import indicator_intraday, market_quotes
from src.db.session import get_session
from src.repository import market_daily
from src.simulation.market_indicators import Indicator
from src.simulation.market_quote import MarketQuote, Previous

D = dt.date
NOW = dt.datetime(2026, 10, 9, 14, 0, tzinfo=dt.UTC)  # 뉴욕 10:00(장중)
AT = dt.datetime(2026, 10, 9, 5, 0)


def weekdays(start: dt.date, end: dt.date) -> list[dt.date]:
    out, day = [], start
    while day <= end:
        if day.weekday() < 5:
            out.append(day)
        day += dt.timedelta(days=1)
    return out


DAYS = weekdays(D(2014, 1, 2), D(2026, 10, 8))


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


class Intraday:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    async def body(self, indicator: Indicator, range_key: str) -> dict[str, object]:
        self.calls.append((indicator.id, range_key))
        return {
            "indicator": {"id": indicator.id},
            "range": range_key,
            "intraday": True,
            "status": "ok",
            "fetchedAt": "2026-10-09T14:00:00Z",
            "points": [],
            "notes": [],
            "failure": None,
        }


@pytest.fixture
def intraday() -> Intraday:
    return Intraday()


@pytest.fixture
async def client(session_factory, intraday, monkeypatch):  # type: ignore[no-untyped-def]
    market_quotes.set_shared_service(Quotes())  # type: ignore[arg-type]
    indicator_intraday.set_shared_service(intraday)  # type: ignore[arg-type]
    monkeypatch.setattr(dashboard_series, "utc_now", lambda: NOW)
    app = create_app()

    async def _session():  # type: ignore[no-untyped-def]
        async with session_factory() as s:
            yield s

    app.dependency_overrides[get_session] = _session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    market_quotes.set_shared_service(None)
    indicator_intraday.set_shared_service(None)


async def seed(factory, days=DAYS) -> None:  # type: ignore[no-untyped-def]
    async with factory() as s:
        await market_daily.store_closes(
            s, "sp500", [(d, Decimal(100 + i)) for i, d in enumerate(days)], detected_at=AT
        )
        await market_daily.record_coverage(s, "sp500", days[0], days[-1])
        await market_daily.record_first_day(s, "sp500", days[0])
        await market_daily.record_success(s, "sp500", at=AT)
        await s.commit()


async def test_1년은_그_기간의_일봉_전부다(client: AsyncClient, session_factory) -> None:  # type: ignore[no-untyped-def]
    await seed(session_factory)
    body = (await client.get("/api/dashboard/indicators/sp500/series?range=1y")).json()
    assert body["range"] == "1y" and "unit" not in body
    start = range_start(D(2026, 10, 9), "1y")
    stored = [d for d in DAYS if start is not None and d >= start]
    dates = [p["date"] for p in body["points"]]
    assert dates == [d.isoformat() for d in stored] + ["2026-10-09"]  # 오늘 잠정 꼬리
    assert all("shifted" not in p and "ongoing" not in p for p in body["points"])


async def test_모두는_저장된_일봉_전부다(client: AsyncClient, session_factory) -> None:  # type: ignore[no-untyped-def]
    await seed(session_factory)
    body = (await client.get("/api/dashboard/indicators/sp500/series?range=all")).json()
    assert len(body["points"]) == len(DAYS) + 1
    assert body["points"][0]["date"] == DAYS[0].isoformat()


async def test_5년은_5년_전부터다(client: AsyncClient, session_factory) -> None:  # type: ignore[no-untyped-def]
    await seed(session_factory)
    body = (await client.get("/api/dashboard/indicators/sp500/series?range=5y")).json()
    assert body["points"][0]["date"] >= "2021-10-09"
    assert body["points"][0]["date"] < "2021-10-14"


async def test_틀리거나_없거나_옛_unit이면_1년이다(client: AsyncClient, session_factory) -> None:  # type: ignore[no-untyped-def]
    await seed(session_factory)
    one = (await client.get("/api/dashboard/indicators/sp500/series?range=1y")).json()
    for query in ("", "?range=weekly", "?unit=monthly"):
        body = (await client.get(f"/api/dashboard/indicators/sp500/series{query}")).json()
        assert body["range"] == "1y"
        assert body["points"] == one["points"]


async def test_일_주는_장중_서비스이고_수집과_무관하다(
    client: AsyncClient, intraday: Intraday
) -> None:  # 이력이 하나도 없다 — 일봉 기간이면 202다
    for key in ("1d", "5d"):
        res = await client.get(f"/api/dashboard/indicators/sp500/series?range={key}")
        assert res.status_code == 200
        assert res.json()["intraday"] is True
    assert intraday.calls == [("sp500", "1d"), ("sp500", "5d")]
    assert (await client.get("/api/dashboard/indicators/sp500/series?range=1y")).status_code == 202


async def test_환율의_장중도_장중_서비스다(client: AsyncClient, intraday: Intraday) -> None:
    res = await client.get("/api/dashboard/indicators/usd/series?range=1d")
    assert res.status_code == 200 and res.json()["intraday"] is True
    assert intraday.calls == [("usd", "1d")]
