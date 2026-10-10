"""장중 시세 서비스 (014 반복 2026-10-10b T104) — FR-028, research R14-19.

가짜 출처·가짜 시계를 쓴다(네트워크 없음). 저장하지 않는다 — 메모리에 일 60초·주 300초, 실패는
짧게(10초) 기억한다.
같은 순간의 요청은 출처를 한 번 부른다.
"""

from __future__ import annotations

import asyncio
import dataclasses
import datetime as dt
from decimal import Decimal

from src.api.services.indicator_intraday import IntradayService
from src.config.settings import load_settings
from src.ingestion.yahoo.errors import StockSourceRateLimited
from src.ingestion.yahoo.market import IntradayFetch
from src.simulation.market_indicators import get

T0 = dt.datetime(2026, 10, 9, 14, 0, tzinfo=dt.UTC)


class Clock:
    def __init__(self) -> None:
        self.now = T0

    def __call__(self) -> dt.datetime:
        return self.now


class Source:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []
        self.fail: Exception | None = None
        self.hold: asyncio.Event | None = None

    async def fetch_intraday(self, indicator_id: str, range_key: str) -> IntradayFetch:
        self.calls.append((indicator_id, range_key))
        if self.hold is not None:
            await self.hold.wait()
        if self.fail is not None:
            raise self.fail
        return IntradayFetch(
            [(T0 - dt.timedelta(minutes=5), Decimal("7801.250000")), (T0, Decimal("7802.000000"))],
            200,
        )


def service(source: Source, clock: Clock) -> IntradayService:
    settings = dataclasses.replace(
        load_settings(),
        dashboard_intraday_day_cache_seconds=60,
        dashboard_intraday_week_cache_seconds=300,
        market_quote_failure_cache_seconds=10,
    )
    return IntradayService(source, settings, clock=clock)


async def test_본문() -> None:
    clock, source = Clock(), Source()
    body = await service(source, clock).body(get("sp500"), "1d")  # type: ignore[arg-type]
    assert body["range"] == "1d" and body["intraday"] is True and body["status"] == "ok"
    assert body["fetchedAt"] == "2026-10-09T14:00:00Z"
    assert body["points"] == [
        {"time": "2026-10-09T13:55:00Z", "value": "7801.250000", "provisional": True},
        {"time": "2026-10-09T14:00:00Z", "value": "7802.000000", "provisional": True},
    ]
    assert body["failure"] is None


async def test_일은_60초_주는_300초_둔다() -> None:
    clock, source = Clock(), Source()
    intraday = service(source, clock)
    sp500 = get("sp500")
    await intraday.body(sp500, "1d")  # type: ignore[arg-type]
    await intraday.body(sp500, "5d")  # type: ignore[arg-type]
    clock.now += dt.timedelta(seconds=59)
    await intraday.body(sp500, "1d")  # type: ignore[arg-type]
    clock.now += dt.timedelta(seconds=2)
    await intraday.body(sp500, "1d")  # type: ignore[arg-type]
    await intraday.body(sp500, "5d")  # type: ignore[arg-type]
    assert source.calls == [("sp500", "1d"), ("sp500", "5d"), ("sp500", "1d")]


async def test_실패는_10초_기억하고_본문에_싣는다() -> None:
    clock, source = Clock(), Source()
    source.fail = StockSourceRateLimited("시세 출처의 호출 한도를 소진했습니다.")
    intraday = service(source, clock)
    body = await intraday.body(get("sp500"), "1d")  # type: ignore[arg-type]
    assert (body["status"], body["points"]) == ("failed", [])
    assert body["failure"]["reason"] == "rate_limited"  # type: ignore[index]
    clock.now += dt.timedelta(seconds=5)
    await intraday.body(get("sp500"), "1d")  # type: ignore[arg-type]
    assert len(source.calls) == 1
    clock.now += dt.timedelta(seconds=6)
    await intraday.body(get("sp500"), "1d")  # type: ignore[arg-type]
    assert len(source.calls) == 2


async def test_동시_요청은_한_번이다() -> None:
    clock, source = Clock(), Source()
    source.hold = asyncio.Event()
    intraday = service(source, clock)
    first = asyncio.create_task(intraday.body(get("sp500"), "1d"))  # type: ignore[arg-type]
    second = asyncio.create_task(intraday.body(get("sp500"), "1d"))  # type: ignore[arg-type]
    await asyncio.sleep(0)
    source.hold.set()
    await asyncio.gather(first, second)
    assert len(source.calls) == 1


async def test_환율은_시장_환율임을_밝힌다() -> None:
    clock, source = Clock(), Source()
    body = await service(source, clock).body(get("usd"), "5d")  # type: ignore[arg-type]
    assert "market_fx" in body["notes"]  # type: ignore[operator]


class TwoDays(Source):
    """뉴욕 10-08·10-09 두 세션의 점."""

    async def fetch_intraday(self, indicator_id: str, range_key: str) -> IntradayFetch:
        self.calls.append((indicator_id, range_key))
        first = dt.datetime(2026, 10, 8, 13, 30, tzinfo=dt.UTC)
        second = dt.datetime(2026, 10, 9, 13, 30, tzinfo=dt.UTC)
        points = [
            (first, Decimal("7700.000000")),
            (first + dt.timedelta(hours=6, minutes=30), Decimal("7710.000000")),
            (second, Decimal("7790.000000")),
            (second + dt.timedelta(hours=6, minutes=30), Decimal("7801.000000")),
        ]
        return IntradayFetch(points, 200)


async def test_처음_보이는_범위는_일이_마지막_세션_주가_최근_5세션이다() -> None:
    # 반복 2026-10-10c(T129) — 받은 점 전부를 싣고 `window`로 처음 범위를 준다(왼쪽으로 끌면
    # 앞 세션)
    clock, source = Clock(), TwoDays()
    intraday = service(source, clock)
    day = await intraday.body(get("sp500"), "1d")  # type: ignore[arg-type]
    assert len(day["points"]) == 4  # type: ignore[arg-type]
    assert day["window"] == {"from": "2026-10-09T13:30:00Z", "to": "2026-10-09T20:00:00Z"}
    week = await intraday.body(get("sp500"), "5d")  # type: ignore[arg-type]
    assert week["window"] == {"from": "2026-10-08T13:30:00Z", "to": "2026-10-09T20:00:00Z"}


async def test_실패면_window가_없다() -> None:
    clock, source = Clock(), Source()
    source.fail = StockSourceRateLimited("한도")
    body = await service(source, clock).body(get("sp500"), "1d")  # type: ignore[arg-type]
    assert body["window"] is None
