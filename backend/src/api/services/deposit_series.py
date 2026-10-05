"""예금 차트 시계열 조립 (T029) — 008 FR-036, SC-009, research R8-10.

**계산하지 않는다.** 표가 쓰는 계산 결과를 차트 모양으로 바꾸기만 한다 — 여기서 다시 계산하면 표와
차트가 어긋날 여지가 생긴다(005 SC-032와 같은 이유).

- 점은 **표의 행 날짜**(가입·매달 1일·만기·재예치)에 **계산 끝**(보드의 기준일)을 더한 것이고 값도
  그 행·보드의 값이다
- 같은 날의 만기·재예치는 점 하나다 — 잔고가 같다(재예치 원금 = 만기 원금 + 세후 이자)
- 결측은 계산을 멈추므로 점 사이에 빈 구간이 없다 — `gaps`는 늘 비어 있다
- 잔고 축으로 줄이고 그 날짜의 점을 통째로 가져온다 — 두 값을 따로 줄이면 한 점 안의 값이 서로 다른
  날의 것이 된다
- 010 — 점에 그 날짜의 달에 **발표된** 금리(`price`, 연 %)를 싣는다. 계산에 넘긴 바로 그
  `rates`다(research R10-5 — 그
  달 가입·재예치가 읽는 값과 같다, FR-002). 마지막 발표 달 뒤의 달은 `None` + `unpublished` — 계산이
  대신 쓴 금리(잠정)를 그 달 금리로 내지 않는다(헌법 원칙 V). 발표 기간 안인데 통계가 빈 달은 `None`
  + `missing`(만기 사이 달이라 계산이 이어진다). 가격만 없는 점이라 `gaps`(잔고 선이 끊기는 자리)에
  넣지 않는다
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

from src.api.services.series_query import DEFAULT_MAX_POINTS
from src.simulation.deposit_rollover import DepositOutcome
from src.simulation.downsample import Point, lttb


@dataclass(frozen=True, slots=True)
class SeriesPoint:
    date: dt.date
    balance: Decimal
    return_rate: Decimal
    #: 그 달 발표 금리(연 %). 없으면 `None`이고 `price_missing`이 사유다 — `price is None` ⇔
    #: `price_missing is not None`.
    price: Decimal | None
    price_missing: Literal["unpublished", "missing"] | None


@dataclass(frozen=True, slots=True)
class DepositSeries:
    start: dt.date
    end: dt.date
    points: tuple[SeriesPoint, ...]
    downsampled: bool
    source_point_count: int
    provisional_from: dt.date | None


def build_series(outcome: DepositOutcome, *, start: dt.date, rates: Mapping[dt.date, Decimal],
                 latest_month: dt.date, max_points: int = DEFAULT_MAX_POINTS) -> DepositSeries:
    """`rates`·`latest_month`는 기본값이 없다 — 있으면 경로가 넘기기를 잊어도 모든 점이 조용히
    "미발표"가 된다."""

    def point(day: dt.date, balance: Decimal, return_rate: Decimal) -> SeriesPoint:
        month = day.replace(day=1)
        if month > latest_month:
            return SeriesPoint(day, balance, return_rate, None, "unpublished")
        published = rates.get(month)
        if published is None:
            return SeriesPoint(day, balance, return_rate, None, "missing")
        return SeriesPoint(day, balance, return_rate, published, None)

    by_date: dict[dt.date, SeriesPoint] = {}
    for row in reversed(outcome.rows):  # 오름차순. 같은 날은 잔고가 같아 어느 행이든 같다
        by_date[row.date] = point(row.date, row.balance, row.return_rate)
    summary = outcome.summary
    by_date.setdefault(summary.as_of, point(summary.as_of, summary.balance, summary.return_rate))
    points = [by_date[d] for d in sorted(by_date)]
    source_count = len(points)
    downsampled = source_count > max_points
    if downsampled:
        picked = lttb([Point(p.date, p.balance) for p in points], target=max_points)
        points = [by_date[p.date] for p in picked]
    return DepositSeries(start=start, end=summary.as_of, points=tuple(points),
                         downsampled=downsampled, source_point_count=source_count,
                         provisional_from=summary.provisional_from)
