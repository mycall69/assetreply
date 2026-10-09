"""대시보드 지표 수집 워커 (014 T046) — FR-016, FR-017, FR-019, SC-006, research R14-2·R14-4·R14-11.

스텁 출처(네트워크 없음)와 시험 DB로 본다.

- 첫 바퀴는 12개 지표의 최근 청크와 첫 거래일이다. 다음 바퀴가 첫 날까지 과거 구간을 받는다
- 한 청크가 실패하면 그 지표만 실패로 남고(커버리지 없음 + 실패 기록) 다른 지표는 계속된다. 다음
  바퀴에 그 청크부터 받는다
- 겹쳐 받은 날의 값이 바뀌면 저장 값은 그대로 두고 개정 한 줄과 `market_close_revised` 사건을 남긴다
- 같은 현지 날짜에 다시 돌려도 원본이 늘지 않는다 — 할 일이 없다
- 깨우기 이벤트가 곧바로 한 바퀴를 돌린다
"""

from __future__ import annotations

import asyncio
import dataclasses
import datetime as dt
from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from src.worker.market_runner import run_round

from src.config.settings import Settings, load_settings
from src.db.models import MarketCloseRevision, MarketIndicatorRaw
from src.ingestion.yahoo.errors import StockSourceUnavailable
from src.ingestion.yahoo.market import DailyFetch
from src.ingestion.yahoo.market_parse import DailyChunk
from src.repository import market_daily
from src.simulation.market_indicators import market_indicators
from src.worker import market_runner, market_worker

D = dt.date
NOW = dt.datetime(
    2026, 10, 9, 14, 0, tzinfo=dt.UTC
)  # 한국 23:00, 뉴욕 10:00 — 모든 시장의 현지 날짜가 10-09
FIRST = D(2023, 1, 2)
IDS = [i.id for i in market_indicators()]


def value_of(day: dt.date) -> Decimal:
    return Decimal(100 + day.toordinal() % 17)


class Source:
    """요청 구간의 평일 종가를 만들어 돌려준다. `current_date` 이후는 내지 않는다(어댑터와 같은
    규칙)."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dt.date, dt.date]] = []
        self.fail_on: set[int] = set()
        self.override: dict[tuple[str, dt.date], Decimal] = {}

    async def fetch_daily(
        self, indicator_id: str, date_from: dt.date, date_to: dt.date, *, current_date: dt.date
    ) -> DailyFetch:
        self.calls.append((indicator_id, date_from, date_to))
        if len(self.calls) in self.fail_on:
            raise StockSourceUnavailable("시세 출처가 응답하지 않습니다.")
        closes = []
        day = max(date_from, FIRST)
        while day <= date_to and day < current_date:
            if day.weekday() < 5:
                closes.append((day, self.override.get((indicator_id, day), value_of(day))))
            day += dt.timedelta(days=1)
        return DailyFetch(DailyChunk(closes, None, FIRST), '{"chart": {}}', 200, date_from, date_to)

    async def delay_between_chunks(self) -> None:
        return None


@pytest.fixture
def settings() -> Settings:
    return dataclasses.replace(
        load_settings(),
        market_chunk_days=730,
        market_recheck_overlap_days=5,
        market_collect_interval_seconds=3600,
    )


@pytest.fixture
def events(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, dict[str, object]]]:
    seen: list[tuple[str, dict[str, object]]] = []
    monkeypatch.setattr(market_runner, "_event", lambda name, **fields: seen.append((name, fields)))
    return seen


async def _count(factory: async_sessionmaker[AsyncSession], model: type) -> int:
    async with factory() as s:
        return int((await s.execute(select(func.count()).select_from(model))).scalar_one())


async def test_첫_바퀴는_최근_청크와_첫_거래일(session_factory, settings, events) -> None:  # type: ignore[no-untyped-def]
    source = Source()
    result = await run_round(session_factory, source, settings=settings, now=NOW)
    assert [c[0] for c in source.calls] == IDS
    assert result.succeeded == 12 and result.failed == frozenset()
    async with session_factory() as s:
        cov = await market_daily.get_coverage(s, "kospi")
        assert cov is not None
        assert (cov.first_day, cov.covered_through) == (FIRST, D(2026, 10, 8))
        assert cov.covered_from == D(2026, 10, 8) - dt.timedelta(days=729)
        assert cov.last_success_at is not None
    second = await run_round(session_factory, source, settings=settings, now=NOW)
    assert second.succeeded == 12
    async with session_factory() as s:
        cov = await market_daily.get_coverage(s, "kospi")
        assert cov is not None and cov.covered_from == FIRST
        closes = await market_daily.closes(s, "kospi")
        assert closes[0][0] == FIRST and closes[-1][0] == D(2026, 10, 8)
    assert any(name == "market_chunk" for name, _ in events)


async def test_한_청크가_실패하면_그_지표만_실패하고_다음_바퀴에_받는다(
    session_factory, settings, events
) -> None:  # type: ignore[no-untyped-def]
    source = Source()
    source.fail_on = {2}  # 두 번째 지표(kosdaq)의 최근 청크
    result = await run_round(session_factory, source, settings=settings, now=NOW)
    assert result.failed == frozenset({"kosdaq"}) and result.succeeded == 11
    async with session_factory() as s:
        cov = await market_daily.get_coverage(s, "kosdaq")
        assert cov is not None
        assert (cov.covered_from, cov.covered_through) == (None, None)
        assert (cov.last_failure_kind, cov.last_failure_message) == (
            "connection",
            "시세 출처가 응답하지 않습니다.",
        )
        assert await market_daily.closes(s, "kosdaq") == []
    assert any(name == "market_chunk_failed" and f["indicator"] == "kosdaq" for name, f in events)
    source.calls.clear()
    await run_round(session_factory, source, settings=settings, now=NOW)
    assert source.calls[0][0] == "kosdaq"  # 최근 청크부터 다시


async def test_겹친_날의_값이_바뀌면_개정만_남긴다(session_factory, settings, events) -> None:  # type: ignore[no-untyped-def]
    source = Source()
    await run_round(session_factory, source, settings=settings, now=NOW)
    await run_round(session_factory, source, settings=settings, now=NOW)
    changed_day = D(2026, 10, 7)
    source.override[("kospi", changed_day)] = Decimal("12345.67")
    monday = NOW + dt.timedelta(days=3)  # 월요일 — 선물(cme)도 새 거래일이다
    await run_round(session_factory, source, settings=settings, now=monday)
    async with session_factory() as s:
        revision = (await s.execute(select(MarketCloseRevision))).scalar_one()
        assert (revision.indicator_id, revision.trade_date) == ("kospi", changed_day)
        assert revision.source_close == Decimal("12345.670000")
        stored = dict(await market_daily.closes(s, "kospi"))
        assert stored[changed_day] == value_of(changed_day)
        assert stored[D(2026, 10, 9)] == value_of(D(2026, 10, 9))  # 이어 받은 새 날
    assert any(name == "market_close_revised" for name, _ in events)


async def test_같은_현지_날짜에는_다시_받지_않는다(session_factory, settings, events) -> None:  # type: ignore[no-untyped-def]
    source = Source()
    await run_round(session_factory, source, settings=settings, now=NOW)
    await run_round(session_factory, source, settings=settings, now=NOW)
    raws = await _count(session_factory, MarketIndicatorRaw)
    again = await run_round(
        session_factory, source, settings=settings, now=NOW + dt.timedelta(hours=1)
    )
    assert (again.succeeded, again.planned) == (0, 0)
    assert await _count(session_factory, MarketIndicatorRaw) == raws


async def test_깨우기가_곧바로_한_바퀴를_돌린다(session_factory, settings, events) -> None:  # type: ignore[no-untyped-def]
    source = Source()
    clock = {"now": NOW}
    task = asyncio.create_task(
        market_worker.market_worker_loop(
            session_factory, source, settings=settings, clock=lambda: clock["now"]
        )
    )
    for _ in range(1000):
        await asyncio.sleep(0.01)
        if len(source.calls) >= 24:
            break
    assert len(source.calls) == 24  # 최근 청크 12 + 과거 구간 12, 그 뒤 할 일이 없어 기다린다
    clock["now"] = NOW + dt.timedelta(days=3)  # 월요일
    market_worker.wake()
    for _ in range(1000):
        await asyncio.sleep(0.01)
        if len(source.calls) >= 36:
            break
    assert len(source.calls) == 36  # 이어 받기 12
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
