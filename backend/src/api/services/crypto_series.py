"""가상자산 차트 시계열 조립 (T041) — 007 FR-023, FR-043, FR-044, research R7-9.

**계산하지 않는다.** 표가 쓰는 `prepare`(일봉마다의 평가를 함께)를 거친 결과를 차트 모양으로
바꾸기만 한다 — 여기서 다시 계산하면 표와 차트가 어긋날 여지가 생긴다(005 SC-032와 같은 이유).

- 점은 **일봉마다**다. 잔고는 KRW 평가(`balance_krw`), 수익률은 KRW 기준이다(FR-044) — 표의
  잔고(시세 통화)를 그리면 수익률 선과
  다른 기준을 말한다
- 결측 판정은 001의 `compute_gaps`를 쓰되, 커버리지 안의 빈 날은 **출처 결측**(`source_missing` —
  끊는다)이다. 가상자산은 휴장이
  없다(FR-023)
- 잔고 축으로 줄이고 그 날짜의 점을 통째로 가져온다 — 두 값을 따로 줄이면 한 점 안의 값이 서로 다른
  날의 것이 된다(005와 같다)
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from decimal import Decimal

from src.api.services.crypto_simulation import CryptoResult
from src.api.services.series_query import DEFAULT_MAX_POINTS, Gap, compute_gaps
from src.simulation.downsample import Point, lttb


@dataclass(frozen=True, slots=True)
class SeriesPoint:
    date: dt.date
    balance: Decimal
    return_rate: Decimal


@dataclass(frozen=True, slots=True)
class CryptoSeries:
    start: dt.date
    end: dt.date
    points: tuple[SeriesPoint, ...]
    gaps: tuple[Gap, ...]
    downsampled: bool
    source_point_count: int


def _downsample(points: list[SeriesPoint], max_points: int) -> list[SeriesPoint]:
    if len(points) <= max_points:
        return points
    by_date = {p.date: p for p in points}
    picked = lttb([Point(p.date, p.balance) for p in points], target=max_points)
    return [by_date[p.date] for p in picked]


def build_series(
    result: CryptoResult,
    *,
    start: dt.date,
    end: dt.date,
    covered: tuple[dt.date, dt.date] | None,
    max_points: int = DEFAULT_MAX_POINTS,
) -> CryptoSeries:
    """일봉마다의 평가를 차트용 시계열로. 결측은 시작 월 1일(매수일이 속한 달)부터 본다."""
    points = [SeriesPoint(v.row.date,
                          v.balance_krw if v.balance_krw is not None else v.row.balance,
                          v.return_rate)
              for v in result.daily]
    gaps = compute_gaps(
        start.replace(day=1), end, set(result.quote_dates),
        covered[0] if covered else None, covered[1] if covered else None,
        inside_reason="source_missing")
    reduced = _downsample(points, max_points)
    return CryptoSeries(start=start, end=end, points=tuple(reduced), gaps=tuple(gaps),
                        downsampled=len(reduced) < len(points),
                        source_point_count=len(points))
