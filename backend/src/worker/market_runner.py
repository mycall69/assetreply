"""대시보드 지표 이력 수집 실행 (014 T054) — FR-017, FR-019, SC-006, research R14-2·R14-4·R14-11.

**할 일 계획은 순수 함수다**(`plan_round`) — 커버리지로 이번 바퀴에 받을 청크를 정한다:

- 커버리지가 없으면 **최근 청크**(그 시장 현지 어제에서 끝나는 2년) — 그 응답으로 출처의 첫 거래일을
  안다
- 첫 날까지 거꾸로 **과거 구간** 청크(첫 날에서 멈춘다)
- 커버리지 끝이 현지 어제보다 앞이면 **이어 받기** — 최근 며칠을 겹쳐 받는다(개정 확인). 오래 꺼져
  있었으면 같은 길이로 나눈다
- 차례는 최근 청크 → 이어 받기 → 과거 구간(지표마다 돌아가며) — 카드의 전일 종가가 곧 이력에서
  나온다

**청크마다 원본 → 종가(새 날만·개정) → 커버리지 순으로 저장하고 커밋한다**(007 `crypto_runner`와
같다). 중단되면 받은 데까지 남아
다음 바퀴가 그 뒤부터 받는다. 실패한 청크는 커버리지를 늘리지 않는다 — 받은 구간만
커버리지다(FR-019). 한 지표가 실패해도 다른
지표는 계속된다.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Collection, Sequence
from dataclasses import dataclass
from typing import Literal, Protocol

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.config.settings import Settings
from src.ingestion.yahoo.market import DailyFetch, failure_kind
from src.observability.events import mask_secrets
from src.observability.logging_config import collection_logger
from src.repository import market_daily
from src.simulation.market_indicators import market_indicators
from src.simulation.market_session import trading_date

ChunkKind = Literal["recent", "incremental", "older"]
_DAY = dt.timedelta(days=1)


class MarketSource(Protocol):
    """지표 일봉 출처. 어댑터를 교체할 수 있도록 Protocol에 의존한다(헌법 원칙 II·IV)."""

    async def fetch_daily(
        self, indicator_id: str, date_from: dt.date, date_to: dt.date, *, current_date: dt.date
    ) -> DailyFetch: ...

    async def delay_between_chunks(self) -> None: ...


@dataclass(frozen=True, slots=True)
class IndicatorState:
    indicator_id: str
    first_day: dt.date | None
    covered_from: dt.date | None
    covered_through: dt.date | None
    #: 그 시장의 현지 어제 — 확정 종가의 끝(오늘 봉은 확정이 아니다).
    yesterday: dt.date


@dataclass(frozen=True, slots=True)
class ChunkTask:
    indicator_id: str
    start: dt.date
    end: dt.date
    kind: ChunkKind


@dataclass(frozen=True, slots=True)
class RoundResult:
    planned: int
    succeeded: int
    failed: frozenset[str]


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def _event(name: str, **fields: object) -> None:
    collection_logger().info(name, extra={"event": name, **fields})


def _split(start: dt.date, end: dt.date, chunk_days: int) -> list[tuple[dt.date, dt.date]]:
    chunks: list[tuple[dt.date, dt.date]] = []
    cursor = start
    while cursor <= end:
        stop = min(end, cursor + dt.timedelta(days=chunk_days - 1))
        chunks.append((cursor, stop))
        cursor = stop + _DAY
    return chunks


def _older(state: IndicatorState, chunk_days: int) -> list[ChunkTask]:
    if (
        state.first_day is None
        or state.covered_from is None
        or state.covered_from <= state.first_day
    ):
        return []
    tasks: list[ChunkTask] = []
    end = state.covered_from - _DAY
    while end >= state.first_day:
        start = max(state.first_day, end - dt.timedelta(days=chunk_days - 1))
        tasks.append(ChunkTask(state.indicator_id, start, end, "older"))
        end = start - _DAY
    return tasks


def plan_round(
    states: Sequence[IndicatorState],
    *,
    chunk_days: int,
    overlap_days: int,
    skip: Collection[str] = (),
) -> list[ChunkTask]:
    """이번 바퀴의 청크(차례대로). 순수 함수다."""
    recent: list[ChunkTask] = []
    incremental: list[ChunkTask] = []
    older: list[list[ChunkTask]] = []
    for state in states:
        if state.indicator_id in skip:
            continue
        if state.covered_through is None:
            start = state.yesterday - dt.timedelta(days=chunk_days - 1)
            recent.append(ChunkTask(state.indicator_id, start, state.yesterday, "recent"))
            continue
        if state.covered_through < state.yesterday:
            start = state.covered_through - dt.timedelta(days=overlap_days - 1)
            incremental += [
                ChunkTask(state.indicator_id, s, e, "incremental")
                for s, e in _split(start, state.yesterday, chunk_days)
            ]
        older.append(_older(state, chunk_days))
    interleaved: list[ChunkTask] = []
    for k in range(max((len(o) for o in older), default=0)):
        interleaved += [o[k] for o in older if k < len(o)]
    return recent + incremental + interleaved


async def _states(
    factory: async_sessionmaker[AsyncSession], now: dt.datetime
) -> list[IndicatorState]:
    states: list[IndicatorState] = []
    async with factory() as session:
        for indicator in market_indicators():
            row = await market_daily.get_coverage(session, indicator.id)
            yesterday = trading_date(indicator.market, now) - _DAY
            states.append(
                IndicatorState(
                    indicator.id,
                    first_day=None if row is None else row.first_day,
                    covered_from=None if row is None else row.covered_from,
                    covered_through=None if row is None else row.covered_through,
                    yesterday=yesterday,
                )
            )
    return states


def _naive(instant: dt.datetime) -> dt.datetime:
    """저장용 — UTC, 시간대 없는 값(헌법 시계열 불변식)."""
    return instant.astimezone(dt.UTC).replace(tzinfo=None)


async def _run_chunk(
    session: AsyncSession,
    source: MarketSource,
    task: ChunkTask,
    *,
    current_date: dt.date,
    now: dt.datetime,
) -> None:
    fetched = await source.fetch_daily(
        task.indicator_id, task.start, task.end, current_date=current_date
    )
    received = _naive(now)
    # 원본을 먼저 남긴다 — 정규화와 따로, 본문 그대로(헌법 원칙 V)
    await market_daily.store_raw(
        session,
        task.indicator_id,
        requested_from=fetched.requested_from,
        requested_to=fetched.requested_to,
        status_code=fetched.status,
        body=fetched.raw,
        received_at=received,
    )
    stored = await market_daily.store_closes(
        session, task.indicator_id, fetched.chunk.closes, detected_at=received
    )
    await market_daily.record_coverage(session, task.indicator_id, task.start, task.end)
    if fetched.chunk.first_trade_date is not None:
        await market_daily.record_first_day(
            session, task.indicator_id, fetched.chunk.first_trade_date
        )
    elif task.kind == "older" and not fetched.chunk.closes:
        # 출처가 첫 거래일을 주지 않았고 이 과거 구간이 비었다 — 그 뒤가 출처의 시작이다(발견해
        # 기록)
        await market_daily.record_first_day(session, task.indicator_id, task.end + _DAY)
    await market_daily.record_success(session, task.indicator_id, at=received)
    # 청크마다 커밋한다. 중단되면 받은 데까지는 남아야 재개가 성립한다.
    await session.commit()
    _event(
        "market_chunk",
        indicator=task.indicator_id,
        kind=task.kind,
        start=task.start.isoformat(),
        end=task.end.isoformat(),
        rows=stored.inserted,
    )
    for revision in stored.revisions:
        _event(
            "market_close_revised",
            indicator=task.indicator_id,
            date=revision.trade_date.isoformat(),
            stored=format(revision.stored_close, "f"),
            source=format(revision.source_close, "f"),
        )


async def run_round(
    factory: async_sessionmaker[AsyncSession],
    source: MarketSource,
    *,
    settings: Settings,
    now: dt.datetime,
    skip: Collection[str] = frozenset(),
) -> RoundResult:
    """한 바퀴 — 계획을 세워 청크를 차례로 받는다. 실패한 지표는 이 바퀴의 남은 청크를 건너뛴다."""
    states = await _states(factory, now)
    tasks = plan_round(
        states,
        chunk_days=settings.market_chunk_days,
        overlap_days=settings.market_recheck_overlap_days,
        skip=skip,
    )
    markets = {i.id: i.market for i in market_indicators()}
    failed: set[str] = set()
    succeeded = 0
    for index, task in enumerate(tasks):
        if task.indicator_id in failed:
            continue
        if index > 0:
            await source.delay_between_chunks()
        current = trading_date(markets[task.indicator_id], now)
        async with factory() as session:
            try:
                await _run_chunk(session, source, task, current_date=current, now=now)
                succeeded += 1
            except (
                Exception
            ) as exc:  # 한 지표의 실패가 바퀴를 끝내지 않는다 — 까닭을 남기고 다음으로
                await session.rollback()
                message = mask_secrets(str(exc)) or "수집에 실패했습니다."
                await market_daily.record_failure(
                    session,
                    task.indicator_id,
                    at=_naive(now),
                    kind=failure_kind(exc),
                    message=message,
                )
                await session.commit()
                failed.add(task.indicator_id)
                _event(
                    "market_chunk_failed",
                    indicator=task.indicator_id,
                    kind=task.kind,
                    start=task.start.isoformat(),
                    end=task.end.isoformat(),
                    reason=failure_kind(exc),
                )
    return RoundResult(planned=len(tasks), succeeded=succeeded, failed=frozenset(failed))
