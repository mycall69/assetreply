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

from src.api.main import create_app
from src.api.routes import dashboard_series
from src.api.services import indicator_intraday, market_quotes
from src.db.models import FxCoverage, FxRate
from src.db.session import get_session
from src.repository import market_daily
from src.simulation.indicator_range import range_start
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
    # 014 승인 2026-10-10(반복 2026-10-10c T132) — 1년은 처음 보이는 범위다. 점은 저장된
    # 일봉 전부이고 1년의 시작일은 `windows["1y"]`다(왼쪽으로 끌면 첫 날까지)
    await seed(session_factory)
    body = (await client.get("/api/dashboard/indicators/sp500/series?range=1y")).json()
    assert body["range"] == "1y" and "unit" not in body
    start = range_start(D(2026, 10, 9), "1y")
    assert start is not None and body["windows"]["1y"] == start.isoformat()
    dates = [p["date"] for p in body["points"]]
    assert dates == [d.isoformat() for d in DAYS] + ["2026-10-09"]  # 오늘 잠정 꼬리
    assert all("shifted" not in p and "ongoing" not in p for p in body["points"])


async def test_모두는_저장된_일봉_전부다(client: AsyncClient, session_factory) -> None:  # type: ignore[no-untyped-def]
    await seed(session_factory)
    body = (await client.get("/api/dashboard/indicators/sp500/series?range=all")).json()
    assert len(body["points"]) == len(DAYS) + 1
    assert body["points"][0]["date"] == DAYS[0].isoformat()


async def test_5년은_5년_전부터다(client: AsyncClient, session_factory) -> None:  # type: ignore[no-untyped-def]
    await seed(session_factory)
    # 014 승인 2026-10-10(반복 2026-10-10c T132) — 5년 앞이 첫 점이 아니라 처음 보이는
    # 범위의 시작일이다
    body = (await client.get("/api/dashboard/indicators/sp500/series?range=5y")).json()
    assert body["windows"]["5y"] == "2021-10-09"
    assert body["points"][0]["date"] == DAYS[0].isoformat()


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


async def test_기간만_읽어도_결측_판정은_모두와_같다(client: AsyncClient, session_factory) -> None:  # type: ignore[no-untyped-def]
    # T124 — 일봉 기간은 그 기간 앞의 마지막 날부터만 읽는다(약 2만 5천 점을 모두 읽지 않는다).
    # 같은 시장의 다른 지표로 가린 결측과 기간 시작을 가로지르는 긴 빈 구간이 "모두"에서 잘라 낸
    # 것과 같아야 한다
    # 014 승인 2026-10-10(반복 2026-10-10c T132) — 일봉 기간이 다시 일봉 전부를 싣는다(처음 보이는
    # 범위만 다르다). 결측 판정이 "모두"와 같다는 성질은 그대로 — 점·결측이 "모두"와 통째로 같다
    start = range_start(D(2026, 10, 9), "1y")
    assert start is not None
    sibling_only = next(d for d in DAYS if d > start + dt.timedelta(days=40))
    lo, hi = start - dt.timedelta(days=12), start + dt.timedelta(days=10)
    long_gap = [d for d in DAYS if lo <= d <= hi]
    own = [d for d in DAYS if d != sibling_only and d not in long_gap]
    await seed(session_factory, own)
    async with session_factory() as s:
        await market_daily.store_closes(s, "dow", [(d, Decimal(1)) for d in DAYS], detected_at=AT)
        await market_daily.record_coverage(s, "dow", DAYS[0], DAYS[-1])
        await s.commit()
    one = (await client.get("/api/dashboard/indicators/sp500/series?range=1y")).json()
    every = (await client.get("/api/dashboard/indicators/sp500/series?range=all")).json()
    assert one["gaps"] == every["gaps"]
    assert any(g["from"] <= sibling_only.isoformat() <= g["to"] for g in one["gaps"])
    assert any(g["from"] <= long_gap[-1].isoformat() <= g["to"] for g in one["gaps"])
    assert one["points"] == every["points"]


# 반복 2026-10-10c(T129) — 기간은 처음 보이는 범위다(spec FR-011, contracts A2). 일봉 기간은
# 저장된 일봉 전부를 싣고 `windows`(기간 → 시작일)로 처음 범위를 준다 — 왼쪽으로 끌면 첫 날까지,
# 월~모두 전환은 다시 받지 않는다
DAILY_RANGES = ("1m", "1y", "5y", "10y", "20y", "all")


def windows_of(today: dt.date) -> dict[str, str | None]:
    out: dict[str, str | None] = {}
    for key in DAILY_RANGES:
        start = range_start(today, key)  # type: ignore[arg-type]
        out[key] = None if start is None else start.isoformat()
    return out


async def test_일봉_기간은_일봉_전부와_기간마다_시작일이다(
    client: AsyncClient, session_factory
) -> None:  # type: ignore[no-untyped-def]
    await seed(session_factory)
    every = (await client.get("/api/dashboard/indicators/sp500/series?range=all")).json()
    for key in ("1m", "1y", "5y"):
        body = (await client.get(f"/api/dashboard/indicators/sp500/series?range={key}")).json()
        assert body["range"] == key
        assert body["points"] == every["points"]
        assert body["points"][0]["date"] == DAYS[0].isoformat()
        assert body["windows"] == windows_of(D(2026, 10, 9))
    assert every["sourcePointCount"] == len(DAYS) + 1
    assert every["windows"]["all"] is None


async def test_환율도_고시_이력_전부와_기간마다_시작일이다(
    client: AsyncClient, session_factory
) -> None:  # type: ignore[no-untyped-def]
    days = weekdays(D(2019, 1, 2), D(2026, 10, 8))
    async with session_factory() as s:
        for i, d in enumerate(days):
            s.add(
                FxRate(
                    currency_code="USD",
                    quote_date=d,
                    base_rate=Decimal("1100") + i,
                    quote_unit=1,
                    source="ecos",
                    is_provisional=False,
                )
            )
        s.add(FxCoverage(currency_code="USD", covered_from=days[0], covered_through=D(2026, 10, 9)))
        await s.commit()
    body = (await client.get("/api/dashboard/indicators/usd/series?range=1y")).json()
    assert body["range"] == "1y"
    assert body["points"][0]["date"] == days[0].isoformat()
    assert len(body["points"]) == len(days)
    assert body["history"]["firstDate"] == days[0].isoformat()
    # 환율의 오늘은 한국 날짜다(외환 고시)
    assert body["windows"] == windows_of(D(2026, 10, 9))
