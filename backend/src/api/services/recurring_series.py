"""적립식·적금 시계열 조립 (011 T026·T038·T048) — FR-015, FR-019, FR-032, research R11-12.

**계산하지 않는다.** 표가 쓰는 결과를 받아 차트가 먹을 모양으로 바꾼다 — 여기서 다시 계산하면 표와
차트가 어긋날 여지가 생긴다(005 SC-032와 같은 이유).

- 점
  - 주식은 표의 행 날짜다. 같은 날의 행이 여럿이면 **그 날의 마지막 상태** 하나다
    (005 `_one_per_day`)
  - 가상자산은 일봉마다다(007 일시금과 같다)
- `balance`는 **원화 총자산**(잔고 + 매수 대기금 + 배당 현금)이다. 일시금 시계열의 잔고(보유분만)와
  다르다 — 1주 미만이라 모은 돈이 선에서 빠지면
  누적 납입 원금 선보다 잔고가 늘 낮아 손실처럼 보인다
- `principal` = 그날까지의 원화 총 납입 원금 — 차트가 누적 납입 원금 점선을 그린다
- 다운샘플은 총자산 축으로 고르고 그 날짜의 점을 통째로 가져온다(005와 같다 — 따로 줄이면 한 점 안의
  값이 다른 날의 것이 된다)
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

from src.api.services.crypto_recurring import CryptoRecurringResult
from src.api.services.series_query import DEFAULT_MAX_POINTS, Gap, compute_gaps
from src.api.services.stock_recurring import RecurringResult
from src.simulation.downsample import Point, lttb
from src.simulation.installment_ladder import LadderOutcome
from src.simulation.split_adjust import split_restated_close


@dataclass(frozen=True, slots=True)
class RecurringPoint:
    date: dt.date
    balance: Decimal
    return_rate: Decimal
    principal: Decimal
    #: 주식은 그 날의 분할만 반영한 수정 종가(010 반복 1), 가상자산은 그 일봉의 시가 — 시세 통화.
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


def build_crypto_series(result: CryptoRecurringResult, *, start: dt.date, end: dt.date,
                        covered: tuple[dt.date, dt.date] | None,
                        max_points: int = DEFAULT_MAX_POINTS) -> RecurringSeries:
    """가상자산 적립식 결과를 시계열로. 점은 **일봉마다**다(표는 납입 행·그 달 첫 일봉 행 — 007
    일시금과 같다).

    커버리지 안의 빈 날은 출처 결측(`source_missing` — 끊는다)이다. 결측은 시작일부터 본다 — 첫 납입
    전에는 그릴 점이 없다.
    """
    points = [RecurringPoint(date=v.row.date, balance=v.total_krw, return_rate=v.return_rate,
                             principal=v.row.basis_krw, price=v.row.open_price)
              for v in result.daily]
    gaps = compute_gaps(start, end, set(result.quote_dates),
                        covered[0] if covered else None, covered[1] if covered else None,
                        inside_reason="source_missing")
    reduced = _downsample(points, max_points)
    return RecurringSeries(start=start, end=end, points=tuple(reduced), gaps=tuple(gaps),
                           downsampled=len(reduced) < len(points), source_point_count=len(points))


@dataclass(frozen=True, slots=True)
class InstallmentPoint:
    """적금 시계열의 점. 금리는 그 달 **발표된** 값이다 — 없으면 `None`이고 `price_missing`이
    사유다."""

    date: dt.date
    balance: Decimal
    return_rate: Decimal
    principal: Decimal
    price: Decimal | None
    price_missing: Literal["unpublished", "missing"] | None
    deposit_rate: Decimal | None


@dataclass(frozen=True, slots=True)
class InstallmentSeries:
    start: dt.date
    end: dt.date
    points: tuple[InstallmentPoint, ...]
    downsampled: bool
    source_point_count: int
    provisional_from: dt.date | None


def _published(rates: Mapping[dt.date, Decimal], latest: dt.date | None,
               day: dt.date) -> tuple[Decimal | None, Literal["unpublished", "missing"] | None]:
    """그 달 발표된 금리. 마지막 발표 달 뒤면 미발표, 발표 범위 안의 빈 달이면 결측이다.

    계산이 대신 쓴 금리(잠정)를 그 달 금리로 내지 않는다(헌법 원칙 V, 008 `deposit_series`와 같다).
    """
    month = day.replace(day=1)
    if latest is None or month > latest:
        return None, "unpublished"
    published = rates.get(month)
    return (None, "missing") if published is None else (published, None)


def build_installment_series(
    outcome: LadderOutcome, *, start: dt.date, installment_rates: Mapping[dt.date, Decimal],
    installment_latest: dt.date, deposit_rates: Mapping[dt.date, Decimal],
    deposit_latest: dt.date | None, max_points: int = DEFAULT_MAX_POINTS,
) -> InstallmentSeries:
    """적금 사다리 결과를 시계열로(FR-032).

    점은 표의 행 날짜에 계산 끝(보드의 기준일)을 더한 것이고, 같은 날의 행이 여럿이면 그 날의 마지막
    상태다. 금리 계열은 계산에 넘긴 바로 그 값이다 — 기본값이 없다(빠뜨리면 모든 점이 조용히
    "미발표"가 된다).
    """

    def point(day: dt.date, balance: Decimal, return_rate: Decimal,
              principal: Decimal) -> InstallmentPoint:
        price, missing = _published(installment_rates, installment_latest, day)
        held, _ = _published(deposit_rates, deposit_latest, day)
        return InstallmentPoint(day, balance, return_rate, principal, price, missing, held)

    by_date: dict[dt.date, InstallmentPoint] = {}
    for row in outcome.rows:  # 최신순 — 같은 날의 첫 행이 그 날의 마지막 상태다
        if row.date not in by_date:
            by_date[row.date] = point(row.date, row.balance, row.return_rate, row.contributed)
    summary = outcome.summary
    by_date.setdefault(summary.as_of, point(summary.as_of, summary.balance, summary.return_rate,
                                            summary.contributed))
    points = [by_date[d] for d in sorted(by_date)]
    source_count = len(points)
    downsampled = source_count > max_points
    if downsampled:
        picked = lttb([Point(p.date, p.balance) for p in points], target=max_points)
        points = [by_date[p.date] for p in picked]
    return InstallmentSeries(start=start, end=summary.as_of, points=tuple(points),
                             downsampled=downsampled, source_point_count=source_count,
                             provisional_from=summary.provisional_from)
