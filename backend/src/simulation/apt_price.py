"""시세 창 (T035) — 009 FR-008, FR-016~FR-018, research R9-6.

아파트는 같은 단지·같은 평형이라도 거래가 없는 달이 흔하다. 시세는 **명시적으로 정의된 추정
규칙**이다(헌법 원칙 V — 임의 보간이 아니다):

    그 달 평균 = 그 달(계약일 기준 달력 월) 해제·사라짐이 아닌 거래 금액 합 ÷ 건수, 원 미만
    반올림(0.5 이상 올림) 적용 시세 = 창 1 → 3 → 6 → 12 → 24 → 36개월 중 거래가 있는 가장 짧은 창의
    평균
                (창 안 **모든 거래**의 평균 — 달별 평균의 평균이 아니다). 창은 기준 달을 끝으로
                거꾸로 센다
    36개월 안에도 거래가 없으면 시세 없음(None) — 0이나 다른 달 값으로 채우지 않는다

1개월 창은 실측, 넓은 창은 **추정**이다. 창 안에 잠정 달(최근 12개월 — 신고·해제가 더 들어온다)이
있으면 **잠정**이다. 추정·잠정은 결과에만 있고 저장하지 않는다 — 계산할 때마다 보관한 거래에서 다시
구한다(FR-017).

**기준 달 뒤의 거래는 쓰지 않는다** — 그때는 알 수 없던 미래 가격으로 과거를 평가하지
않는다(FR-016).

**순수 함수 모듈이다.** `repository`·`api`·`db`를 임포트하지 않는다(헌법 원칙 IV). 금액은 정수(원),
평균은 `Decimal`로 나눠 반올림한다(헌법 원칙 VI).
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, localcontext

from src.simulation.money import CALC_PRECISION

#: 시세를 정하는 창(개월). 거래가 있는 가장 짧은 창을 쓴다(FR-016).
WINDOWS: tuple[int, ...] = (1, 3, 6, 12, 24, 36)


@dataclass(frozen=True, slots=True)
class Trade:
    """계산에 쓰는 거래 하나 — 출처 형식이 아니다(헌법 원칙 II). 금액은 원 단위 정수다."""

    deal_date: dt.date
    amount: int
    cancelled: bool = False
    missing: bool = False


@dataclass(frozen=True, slots=True)
class MonthTotal:
    """한 달의 거래 건수와 금액 합."""

    count: int
    total: int


@dataclass(frozen=True, slots=True)
class MarketPrice:
    """기준 달의 적용 시세 — 쓴 창과 창 안 거래 수를 함께 보인다(FR-017)."""

    month: dt.date
    price: int
    window: int
    trades: int
    estimated: bool
    provisional: bool


def month_start(day: dt.date) -> dt.date:
    return day.replace(day=1)


def add_months(month: dt.date, months: int) -> dt.date:
    """달의 첫날에 개월을 더한다(음수면 뺀다)."""
    index = month.year * 12 + month.month - 1 + months
    return dt.date(index // 12, index % 12 + 1, 1)


def aggregate(trades: Iterable[Trade], *,
              include_cancelled: bool = False) -> dict[dt.date, MonthTotal]:
    """달별 건수와 합. 사라진 거래는 늘 빼고, 해제된 거래는 기본으로 뺀다(FR-008).

    `include_cancelled`는 헬리오시티 스프레드시트(해제를 넣은 값)와 맞대는 참조값 검증용이다(SC-003)
    — 화면 경로는 쓰지 않는다.
    """
    counts: dict[dt.date, int] = {}
    totals: dict[dt.date, int] = {}
    for trade in trades:
        if trade.missing or (trade.cancelled and not include_cancelled):
            continue
        month = month_start(trade.deal_date)
        counts[month] = counts.get(month, 0) + 1
        totals[month] = totals.get(month, 0) + trade.amount
    return {month: MonthTotal(counts[month], totals[month]) for month in sorted(counts)}


def _average(total: int, count: int) -> int:
    with localcontext() as ctx:
        ctx.prec = CALC_PRECISION
        return int((Decimal(total) / Decimal(count)).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def month_average(monthly: Mapping[dt.date, MonthTotal], month: dt.date) -> int | None:
    """그 달 평균(원 미만 반올림). 거래가 없으면 None — 0이 아니다."""
    found = monthly.get(month_start(month))
    if found is None or found.count == 0:
        return None
    return _average(found.total, found.count)


def market_price(monthly: Mapping[dt.date, MonthTotal], month: dt.date, *,
                 provisional_from: dt.date) -> MarketPrice | None:
    """기준 달의 적용 시세. 36개월 안에 거래가 없으면 None이다."""
    base = month_start(month)
    count = total = 0
    covered = 0  # 지금까지 더한 달 수
    for window in WINDOWS:
        while covered < window:
            found = monthly.get(add_months(base, -covered))
            if found is not None:
                count += found.count
                total += found.total
            covered += 1
        if count:
            # 창은 기준 달에서 끝나므로, 잠정 달(최근 N개월)을 덮는 것은 기준 달이 잠정 기간 안일
            # 때뿐이다.
            return MarketPrice(month=base, price=_average(total, count), window=window,
                               trades=count, estimated=window > 1,
                               provisional=base >= provisional_from)
    return None


def provisional_from(today: dt.date, months: int) -> dt.date:
    """잠정 기간의 첫 달 — 오늘(한국 시간)이 속한 달을 끝으로 거꾸로 센 `months`개월(FR-010)."""
    return add_months(month_start(today), -(months - 1))


def first_trade_month(monthly: Mapping[dt.date, MonthTotal]) -> dt.date | None:
    months = [month for month, found in monthly.items() if found.count]
    return min(months) if months else None
