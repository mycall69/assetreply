"""차트용 시계열 조립 (T083) — 005 FR-033, FR-034, FR-041, SC-032.

**계산하지 않는다.** 표가 쓰는 `run_simulation`의 결과를 받아 차트가 먹을 모양으로
바꾸기만 한다. 여기서 한 줄이라도 다시 계산하면 표와 차트가 어긋날 여지가 생기고,
어긋나도 양쪽 다 그럴듯한 숫자라 알아챌 신호가 없다.

결측 구간 판정은 001의 `compute_gaps`를 그대로 쓴다 — 휴장일과 미수집을 나누는
기준(커버리지)이 자산군마다 달라지면 같은 화면 규칙이 자산군마다 다른 뜻이 된다.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from decimal import Decimal

from src.api.services.series_query import DEFAULT_MAX_POINTS, Gap, compute_gaps
from src.api.services.stock_simulation import SimulationResult
from src.simulation.downsample import Point, lttb


@dataclass(frozen=True, slots=True)
class SeriesPoint:
    """시계열 한 점. 금액·비율은 **원금 통화 기준**이다 (FR-041)."""

    date: dt.date
    balance: Decimal
    return_rate: Decimal


@dataclass(frozen=True, slots=True)
class StockSeries:
    start: dt.date
    end: dt.date
    points: tuple[SeriesPoint, ...]
    gaps: tuple[Gap, ...]
    downsampled: bool
    source_point_count: int


def _one_per_day(result: SimulationResult) -> list[SeriesPoint]:
    """날짜마다 **그 날의 마지막 상태**를 하나만 남긴다.

    배당락일이 그 달의 첫 거래일이면 같은 날짜에 행이 둘 생긴다(배당락 행과 월 행).
    둘 다 점으로 넣으면 한 x좌표에 값이 둘이라 선이 되돌아 그려지거나 차트
    라이브러리가 입력을 거부한다 — **표는 멀쩡한데 차트만 깨진다.**

    시뮬레이터는 배당을 먼저 덧붙이고 월 행을 뒤에 덧붙이므로, 같은 날짜 중 **나중
    것**이 그 날의 최종 상태다.
    """
    latest: dict[dt.date, SeriesPoint] = {}
    for converted in sorted(result.rows, key=lambda c: c.row.date):
        row = converted.row
        latest[row.date] = SeriesPoint(row.date, row.balance, row.return_rate)
    return [latest[day] for day in sorted(latest)]


def _downsample(points: list[SeriesPoint], max_points: int) -> list[SeriesPoint]:
    """**잔고 축으로 고르고 그 날짜의 점을 통째로 가져온다.**

    잔고와 수익률을 따로 줄이면 고른 날짜가 달라져, 한 점 안의 두 값이 서로 다른
    날의 것이 된다. 숫자는 그럴듯한데 짝이 어긋난다.
    """
    if len(points) <= max_points:
        return points
    by_date = {p.date: p for p in points}
    picked = lttb([Point(p.date, p.balance) for p in points], target=max_points)
    return [by_date[p.date] for p in picked]


def build_series(
    result: SimulationResult,
    *,
    start: dt.date,
    end: dt.date,
    covered: tuple[dt.date, dt.date] | None,
    max_points: int = DEFAULT_MAX_POINTS,
) -> StockSeries:
    """시뮬레이션 결과를 차트용 시계열로 바꾼다.

    `covered`는 그 종목의 수집 구간이다. 커버리지 안인데 시세가 없으면 휴장
    (`no_quote` — 이어 그린다), 밖이면 미수집(`not_collected` — 끊는다)이다
    (FR-034, 001 FR-032).
    """
    points = _one_per_day(result)
    gaps = compute_gaps(
        start, end, set(result.quote_dates),
        covered[0] if covered else None,
        covered[1] if covered else None)
    reduced = _downsample(points, max_points)

    return StockSeries(
        start=start,
        end=end,
        points=tuple(reduced),
        gaps=tuple(gaps),
        downsampled=len(reduced) < len(points),
        source_point_count=len(points),
    )
