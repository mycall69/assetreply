"""예금 차트 시계열 조립 (T029) — 008 FR-036, SC-009, research R8-10.

**계산하지 않는다.** 표가 쓰는 계산 결과를 차트 모양으로 바꾸기만 한다 — 여기서 다시 계산하면 표와
차트가 어긋날 여지가 생긴다(005 SC-032와 같은 이유).

- 점은 **표의 행 날짜**(가입·매달 1일·만기·재예치)에 **계산 끝**(보드의 기준일)을 더한 것이고 값도
  그 행·보드의 값이다
- 같은 날의 만기·재예치는 점 하나다 — 잔고가 같다(재예치 원금 = 만기 원금 + 세후 이자)
- 결측은 계산을 멈추므로 점 사이에 빈 구간이 없다 — `gaps`는 늘 비어 있다
- 잔고 축으로 줄이고 그 날짜의 점을 통째로 가져온다 — 두 값을 따로 줄이면 한 점 안의 값이 서로 다른
  날의 것이 된다
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from decimal import Decimal

from src.api.services.series_query import DEFAULT_MAX_POINTS
from src.simulation.deposit_rollover import DepositOutcome
from src.simulation.downsample import Point, lttb


@dataclass(frozen=True, slots=True)
class SeriesPoint:
    date: dt.date
    balance: Decimal
    return_rate: Decimal


@dataclass(frozen=True, slots=True)
class DepositSeries:
    start: dt.date
    end: dt.date
    points: tuple[SeriesPoint, ...]
    downsampled: bool
    source_point_count: int
    provisional_from: dt.date | None


def build_series(outcome: DepositOutcome, *, start: dt.date,
                 max_points: int = DEFAULT_MAX_POINTS) -> DepositSeries:
    by_date: dict[dt.date, SeriesPoint] = {}
    for row in reversed(outcome.rows):  # 오름차순. 같은 날은 잔고가 같아 어느 행이든 같다
        by_date[row.date] = SeriesPoint(row.date, row.balance, row.return_rate)
    summary = outcome.summary
    by_date.setdefault(summary.as_of, SeriesPoint(summary.as_of, summary.balance,
                                                  summary.return_rate))
    points = [by_date[d] for d in sorted(by_date)]
    source_count = len(points)
    downsampled = source_count > max_points
    if downsampled:
        picked = lttb([Point(p.date, p.balance) for p in points], target=max_points)
        points = [by_date[p.date] for p in picked]
    return DepositSeries(start=start, end=summary.as_of, points=tuple(points),
                         downsampled=downsampled, source_point_count=source_count,
                         provisional_from=summary.provisional_from)
