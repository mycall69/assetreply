"""적립식·적금 시계열 조립 (011 T026·T038·T048) — FR-015, FR-019, FR-032, research R11-12.

**계산하지 않는다.** 표가 쓰는 결과를 받아 차트가 먹을 모양으로 바꾼다 — 여기서 다시 계산하면 표와
차트가 어긋날 여지가 생긴다(005 SC-032와 같은 이유).

- 점은 표의 행 날짜이고, 같은 날의 행이 여럿이면 **그 날의 마지막 상태** 하나다(005 `_one_per_day`)
- `balance`는 **원화 총자산**(잔고 + 매수 대기금 + 배당 현금)이다. 일시금 시계열의 잔고(보유분만)와
  다르다 — 1주 미만이라 모은 돈이 선에서 빠지면
  누적 납입 원금 선보다 잔고가 늘 낮아 손실처럼 보인다
- `principal` = 그날까지의 원화 총 납입 원금 — 차트가 누적 납입 원금 점선을 그린다
- 다운샘플은 총자산 축으로 고르고 그 날짜의 점을 통째로 가져온다(005와 같다 — 따로 줄이면 한 점 안의
  값이 다른 날의 것이 된다)
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from decimal import Decimal

from src.api.services.series_query import DEFAULT_MAX_POINTS, Gap, compute_gaps
from src.api.services.stock_recurring import RecurringResult
from src.simulation.downsample import Point, lttb
from src.simulation.split_adjust import split_restated_close


@dataclass(frozen=True, slots=True)
class RecurringPoint:
    date: dt.date
    balance: Decimal
    return_rate: Decimal
    principal: Decimal
    #: 그 날의 분할만 반영한 수정 종가(010 반복 1) — 종목 통화.
    price: Decimal


@dataclass(frozen=True, slots=True)
class RecurringSeries:
    start: dt.date
    end: dt.date
    points: tuple[RecurringPoint, ...]
    gaps: tuple[Gap, ...]
    downsampled: bool
    source_point_count: int


def _downsample(points: list[RecurringPoint], max_points: int) -> list[RecurringPoint]:
    if len(points) <= max_points:
        return points
    by_date = {p.date: p for p in points}
    picked = lttb([Point(p.date, p.balance) for p in points], target=max_points)
    return [by_date[p.date] for p in picked]


def build_stock_series(result: RecurringResult, *, start: dt.date, end: dt.date,
                       covered: tuple[dt.date, dt.date] | None,
                       max_points: int = DEFAULT_MAX_POINTS) -> RecurringSeries:
    """주식 적립식 결과를 시계열로. `covered`는 그 종목의 수집 구간이다(휴장 `no_quote`와 미수집
    `not_collected`를 가른다)."""
    last: dict[dt.date, RecurringPoint] = {}
    # 표는 최신순이고 같은 날 안에서도 나중 사건이 위다 — 거꾸로(오래된 순) 훑으면 그 날의 마지막
    # 상태가 남는다.
    for v in reversed(result.views):
        row = v.row
        last[row.date] = RecurringPoint(
            date=row.date, balance=v.total_krw, return_rate=v.return_rate, principal=row.basis_krw,
            price=split_restated_close(row.close_price, row.date, result.splits))
    points = [last[day] for day in sorted(last)]
    gaps = compute_gaps(start, end, set(result.quote_dates),
                        covered[0] if covered else None, covered[1] if covered else None)
    reduced = _downsample(points, max_points)
    return RecurringSeries(start=start, end=end, points=tuple(reduced), gaps=tuple(gaps),
                           downsampled=len(reduced) < len(points), source_point_count=len(points))
