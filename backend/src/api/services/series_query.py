"""시계열 조회와 결측 구간 산출 (T078).

FR-032: 미수집 구간과 고시 없는 날을 값으로 메우지 않고 비어 있음으로 표현한다.
두 종류를 구분하는 근거는 커버리지다 (research R8).
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from src.api.errors import InvalidQuery
from src.repository.coverage import get_coverage
from src.repository.fx_rate import series as fetch_series
from src.simulation.downsample import Point, lttb

DEFAULT_MAX_POINTS = 2000


@dataclass(frozen=True, slots=True)
class Gap:
    """값이 없는 구간. `reason`이 두 종류를 구분한다."""

    start: dt.date
    end: dt.date
    reason: str  # "no_quote" | "not_collected" | "source_missing"(007)


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
    *,
    inside_reason: str = "no_quote",
) -> list[Gap]:
    """값이 없는 날을 미수집과 고시 없음으로 나눈다.

    커버리지 안인데 값이 없으면 "고시 없음"(휴장), 커버리지 밖이면 "미수집"이다.
    별도의 휴장일 캘린더를 두지 않는 근거다 (research R8).

    가상자산은 휴장이 없어 커버리지 안의 빈 날이 **출처 결측**(`source_missing`)이다 — 이어 그리지
    않고 끊는다(007 FR-023, research R7-9). 계산은 같고 사유만 받는다.
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

    return _merge_runs(not_collected, "not_collected") + _merge_runs(no_quote, inside_reason)


@dataclass(frozen=True, slots=True)
class ViewWindow:
    """보기 구간 (014 반복 2026-10-11c — FR-038, contracts A13). 계산 구간으로 자른 뒤라 시작이
    끝보다 늦으면 빈 구간이다(점이 없다). 계산(시작일·기준일)은 바꾸지 않는다 — 점만 고른다."""

    start: dt.date
    end: dt.date

    @property
    def empty(self) -> bool:
        return self.start > self.end

    def contains(self, day: dt.date) -> bool:
        return self.start <= day <= self.end


def view_window(view_from: dt.date | None, view_to: dt.date | None, *, start: dt.date,
                end: dt.date) -> ViewWindow | None:
    """질의 `viewFrom`·`viewTo`를 검증하고 계산 구간 [start, end]로 자른다.

    둘 다 없으면 `None`이다 — 응답이 지금과 같다. 하나만이거나 차례가 거꾸로면 400이다(경로가 다른
    검증보다 먼저 부른다 — 수집·계산 전에 거절한다).
    """
    if view_from is None and view_to is None:
        return None
    if view_from is None or view_to is None:
        raise InvalidQuery("viewFrom과 viewTo는 함께 보내야 합니다.")
    if view_from > view_to:
        raise InvalidQuery("viewFrom이 viewTo보다 늦습니다.")
    return ViewWindow(max(view_from, start), min(view_to, end))


def window_gaps(window: ViewWindow, present: set[dt.date], covered_from: dt.date | None,
                covered_through: dt.date | None, *, inside_reason: str = "no_quote") -> list[Gap]:
    """보기 구간에서 다시 판정한 결측 구간 — 규칙은 `compute_gaps` 그대로다. 빈 구간이면 없다."""
    if window.empty:
        return []
    return compute_gaps(window.start, window.end, present, covered_from, covered_through,
                        inside_reason=inside_reason)


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
