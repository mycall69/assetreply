"""부동산 차트 시계열 조립 (009 T047, FR-031, SC-009, contracts/rest-api `GET
/api/realestate/simulation/series`).

**계산하지 않는다.** 표가 쓰는 계산 결과(`HoldingResult`)를 차트 모양으로 바꾸기만 한다 — 여기서
다시 계산하면 표와 차트가 어긋날 여지가 생긴다(005~008과 같은 이유).

- 점은 표의 행마다 하나 — **첫 점의 날짜는 매입일**(그 달 1일이 매입일보다 앞서지 않게), 그 뒤는
  매달 1일. 끝점은
  계산 끝(오늘 한국 시간 — 보드)이고 값도 보드의 값이다
- 시세 없음 달은 점이 없고 `gaps`에 이어진 구간 하나(`no_price` — 화면이 끊는다). 구간의 양끝은 빈
  첫 달·마지막
  달의 점 날짜다
- 평가액 축으로 줄이고 그 날짜의 점을 통째로 가져온다(008과 같다)
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from decimal import Decimal

from src.api.services.series_query import DEFAULT_MAX_POINTS, Gap
from src.simulation.apt_holding import HoldingResult
from src.simulation.downsample import Point, lttb

NO_PRICE = "no_price"


@dataclass(frozen=True, slots=True)
class SeriesPoint:
    date: dt.date
    balance: int
    return_rate: Decimal
    estimated: bool
    provisional: bool


@dataclass(frozen=True, slots=True)
class RealEstateSeries:
    start: dt.date
    end: dt.date
    points: tuple[SeriesPoint, ...]
    gaps: tuple[Gap, ...]
    downsampled: bool
    source_point_count: int


def build_series(result: HoldingResult, *,
                 max_points: int = DEFAULT_MAX_POINTS) -> RealEstateSeries:
    buy_month = result.buy_date.replace(day=1)
    by_date: dict[dt.date, SeriesPoint] = {}
    gaps: list[Gap] = []
    missing: list[dt.date] = []
    for row in reversed(result.rows):  # 오름차순
        day = result.buy_date if row.month == buy_month else row.month
        if row.value is None or row.return_rate is None or row.price is None:
            missing.append(day)
            continue
        if missing:
            gaps.append(Gap(missing[0], missing[-1], NO_PRICE))
            missing = []
        by_date[day] = SeriesPoint(day, row.value, row.return_rate, row.price.estimated,
                                   row.price.provisional)
    if missing:
        gaps.append(Gap(missing[0], missing[-1], NO_PRICE))
    summary = result.summary
    if (summary.value is not None and summary.return_rate is not None
            and summary.value_price is not None and summary.as_of not in by_date):
        by_date[summary.as_of] = SeriesPoint(summary.as_of, summary.value, summary.return_rate,
                                             summary.estimated, summary.provisional)
    points = [by_date[d] for d in sorted(by_date)]
    source_count = len(points)
    downsampled = source_count > max_points
    if downsampled:
        picked = lttb([Point(p.date, Decimal(p.balance)) for p in points], target=max_points)
        points = [by_date[p.date] for p in picked]
    return RealEstateSeries(start=result.buy_date, end=summary.as_of, points=tuple(points),
                            gaps=tuple(gaps), downsampled=downsampled,
                            source_point_count=source_count)
