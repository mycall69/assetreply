"""시계열 조회와 결측 구간 산출 (T078).

FR-032: 미수집 구간과 고시 없는 날을 값으로 메우지 않고 비어 있음으로 표현한다.
두 종류를 구분하는 근거는 커버리지다 (research R8).
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from src.repository.coverage import get_coverage
from src.repository.fx_rate import series as fetch_series
from src.simulation.downsample import Point, lttb

DEFAULT_MAX_POINTS = 2000


@dataclass(frozen=True, slots=True)
class Gap:
    """값이 없는 구간. `reason`이 두 종류를 구분한다."""

    start: dt.date
    end: dt.date
    reason: str  # "no_quote" | "not_collected"


@dataclass(frozen=True, slots=True)
class SeriesResult:
    currency: str
    quote_unit: int
    start: dt.date
    end: dt.date
    points: tuple[Point, ...]
    gaps: tuple[Gap, ...]
    downsampled: bool
    source_point_count: int
    # 잠정으로 저장된 날짜 (FR-017a). 포인트 튜플에 필드를 더하면 다운샘플링 알고리즘의
    # 입력 형태가 바뀌므로, 날짜 집합으로 따로 전달해 직렬화 단계에서 합친다.
    provisional_dates: frozenset[dt.date] = frozenset()


def _merge_runs(days: list[dt.date], reason: str) -> list[Gap]:
    """연속한 날짜를 하나의 구간으로 묶는다."""
    if not days:
        return []
    gaps: list[Gap] = []
    run_start = prev = days[0]
    for day in days[1:]:
        if day == prev + dt.timedelta(days=1):
            prev = day
            continue
        gaps.append(Gap(run_start, prev, reason))
        run_start = prev = day
    gaps.append(Gap(run_start, prev, reason))
    return gaps


def compute_gaps(
    start: dt.date,
    end: dt.date,
    present: set[dt.date],
    covered_from: dt.date | None,
    covered_through: dt.date | None,
) -> list[Gap]:
    """값이 없는 날을 미수집과 고시 없음으로 나눈다.

    커버리지 안인데 값이 없으면 "고시 없음"(휴장), 커버리지 밖이면 "미수집"이다.
    별도의 휴장일 캘린더를 두지 않는 근거다 (research R8).
    """
    not_collected: list[dt.date] = []
    no_quote: list[dt.date] = []

    day = start
    while day <= end:
        if day not in present:
            inside = (covered_from is not None and covered_through is not None
                      and covered_from <= day <= covered_through)
            (no_quote if inside else not_collected).append(day)
        day += dt.timedelta(days=1)

    return _merge_runs(not_collected, "not_collected") + _merge_runs(no_quote, "no_quote")


async def query_series(
    session: AsyncSession,
    currency_code: str,
    start: dt.date,
    end: dt.date,
    *,
    max_points: int = DEFAULT_MAX_POINTS,
) -> SeriesResult:
    rows = await fetch_series(session, currency_code, start, end)
    provisional = frozenset(r.quote_date for r in rows if r.is_provisional)
    coverage = await get_coverage(session, currency_code)

    points = [Point(r.quote_date, r.base_rate) for r in rows]
    quote_unit = rows[0].quote_unit if rows else 1
    gaps = compute_gaps(
        start, end, {p.date for p in points},
        coverage.covered_from if coverage else None,
        coverage.covered_through if coverage else None)

    reduced = lttb(points, target=max_points) if len(points) > max_points else points

    return SeriesResult(
        currency=currency_code,
        quote_unit=quote_unit,
        start=start,
        end=end,
        points=tuple(reduced),
        gaps=tuple(gaps),
        downsampled=len(reduced) < len(points),
        source_point_count=len(points),
        provisional_dates=provisional,
    )


async def missing_days(
    session: AsyncSession, currency_code: str, start: dt.date, end: dt.date
) -> int:
    """요청 구간에서 커버리지 밖에 있는 일수 (FR-032a의 임계값 판정 입력)."""
    coverage = await get_coverage(session, currency_code)
    if coverage is None:
        return (end - start).days + 1
    missing = 0
    day = start
    while day <= end:
        if not (coverage.covered_from <= day <= coverage.covered_through):
            missing += 1
        day += dt.timedelta(days=1)
    return missing
