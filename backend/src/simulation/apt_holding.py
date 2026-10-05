"""매입·보유 계산 (T037) — 009 FR-005, FR-006, FR-021, FR-022, FR-025~FR-027, research R9-7·R9-8.

그 단지·평형 구분의 달별 거래 집계(해제·사라짐 제외)와 매입 조건으로 매달 행과 요약을 만든다.
매도하지 않는 **보유 평가**다 — 매도 비용·양도세는 넣지 않는다(FR-026).

    행 = 매입 달 ~ 이번 달(한국 시간), 한 달에 한 줄, 최신순 평가액 = 그 달 적용
    시세(`apt_price.market_price`). 시세 없음 달은 평가액·수익·수익률을 비운다(0이 아니다) 누적 비용
    = 취득 비용(매입 행) + 그 달까지 낸 보유세 투자 수익 = 평가액 − 매입가 − 누적 비용, 수익률 =
    투자 수익 ÷ 투입 금액(매입가 + 취득 비용), 소수 6자리 보유세 = 매입일 ≤ 그해 6월
    1일(과세기준일)인 해마다. 기준 금액 = 그해 6월 적용 시세 × 보유세 기준 비율(기본
                0.6 — 공시가격 대용). 재산세는 7월·9월(일괄이면 7월), 종부세는 12월. 납부 달이 오지
                않은 세금은 넣지 않는다. 6월 시세가 없으면 그해 세금은 **계산 불가** — 0으로 두지
                않고 그 사실을 남긴다(FR-021)
    시작 가능 날짜 = 첫 거래 달 1일과 세법 표의 첫 날(2006-01-01) 중 늦은 날(FR-005)

**순수 함수 모듈이다.** `repository`·`api`·`db`를 임포트하지 않는다(헌법 원칙 IV). 결과는 저장하지
않는다 — 거래· 세법·설정의 함수다.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal, localcontext
from typing import Literal

from src.simulation.apt_area import AreaBucket
from src.simulation.apt_price import (
    MarketPrice,
    MonthTotal,
    add_months,
    first_trade_month,
    market_price,
    month_average,
    month_start,
    provisional_from,
)
from src.simulation.apt_tax import (
    AcquisitionCost,
    acquisition_cost,
    comprehensive_tax,
    floor1,
    property_tax,
)
from src.simulation.apt_tax_rules import TAX_RULES_FROM
from src.simulation.money import CALC_PRECISION, quantize_rate

StartableBasis = Literal["first_trade", "tax_rules"]
Installment = Literal["1/1", "1/2", "2/2"]


class NoTradesInArea(Exception):  # noqa: N818 — API `no_trades_in_area`
    """그 단지에 고른 평형 구분의 거래가 한 번도 없다."""


class BeforeStartable(Exception):  # noqa: N818 — API `before_first_trade`
    """매입일이 시작 가능 날짜보다 이르다(FR-005) — 조용히 옮기지 않는다."""

    def __init__(self, startable_from: dt.date, basis: StartableBasis) -> None:
        super().__init__(f"{startable_from.isoformat()}부터 시작할 수 있습니다({basis})")
        self.startable_from = startable_from
        self.basis = basis


class NoPriceAtPurchase(Exception):  # noqa: N818 — API `no_price_at_purchase`
    """매입 달의 시세가 없고 매입가도 넣지 않았다(FR-006)."""

    def __init__(self, month: dt.date) -> None:
        super().__init__(f"{month:%Y-%m}에는 시세가 없습니다")
        self.month = month


@dataclass(frozen=True, slots=True)
class TaxPayment:
    """그 달에 낸 보유세. `basis`는 기준 시세(그해 6월), `base_price`는 공시가격 대용이다."""

    amount: int
    installment: Installment
    rule_date: dt.date
    base_price: int
    basis: MarketPrice


@dataclass(frozen=True, slots=True)
class HoldingRow:
    month: dt.date
    trades: int
    month_average: int | None
    price: MarketPrice | None
    acquisition: AcquisitionCost | None
    property_tax: TaxPayment | None
    property_tax_gap: bool
    comprehensive_tax: TaxPayment | None
    comprehensive_tax_gap: bool
    cumulative_cost: int
    value: int | None
    profit: int | None
    return_rate: Decimal | None


@dataclass(frozen=True, slots=True)
class HoldingSummary:
    as_of: dt.date
    value: int | None
    value_month: dt.date | None
    value_price: MarketPrice | None
    estimated: bool
    provisional: bool
    profit: int | None
    return_rate: Decimal | None
    cumulative_cost: int
    property_tax_total: int
    comprehensive_tax_total: int
    holding_tax_total: int
    tax_gaps: tuple[int, ...]
    last_priced_month: dt.date | None


@dataclass(frozen=True, slots=True)
class HoldingResult:
    startable_from: dt.date
    startable_basis: StartableBasis
    buy_date: dt.date
    buy_price: int
    buy_price_source: Literal["market", "input"]
    buy_price_window: MarketPrice | None
    acquisition: AcquisitionCost
    invested: int
    rows: tuple[HoldingRow, ...]
    summary: HoldingSummary


def startable(monthly: Mapping[dt.date, MonthTotal]) -> tuple[dt.date, StartableBasis]:
    """시작 가능 날짜와 그 근거. 거래가 없으면 `NoTradesInArea`."""
    first = first_trade_month(monthly)
    if first is None:
        raise NoTradesInArea("그 평형 구분의 거래가 없습니다")
    if first < TAX_RULES_FROM:
        return TAX_RULES_FROM, "tax_rules"
    return first, "first_trade"


def _rate(profit: int, invested: int) -> Decimal:
    with localcontext() as ctx:
        ctx.prec = CALC_PRECISION
        return quantize_rate(Decimal(profit) / Decimal(invested))


def simulate_holding(monthly: Mapping[dt.date, MonthTotal], *, buy_date: dt.date,
                     buy_price: int | None, area: AreaBucket, today: dt.date,
                     holding_tax_base_ratio: Decimal, provisional_months: int) -> HoldingResult:
    """매달 행과 요약. 세법 표가 그해를 덮지 않으면 `RuleNotCovered`가 그대로 올라간다(FR-023)."""
    start, basis = startable(monthly)
    if buy_date < start:
        raise BeforeStartable(start, basis)
    first_month, current = month_start(buy_date), month_start(today)
    pending_from = provisional_from(today, provisional_months)

    buy_window = market_price(monthly, first_month, provisional_from=pending_from)
    source: Literal["market", "input"]
    if buy_price is None:
        if buy_window is None:
            raise NoPriceAtPurchase(first_month)
        price, source = buy_window.price, "market"
    else:
        price, source = buy_price, "input"
    acquisition = acquisition_cost(price, buy_date, exceeds_85=area.exceeds_85)
    invested = price + acquisition.total

    property_payments: dict[dt.date, TaxPayment] = {}
    comprehensive_payments: dict[dt.date, TaxPayment] = {}
    gap_years: list[int] = []
    for year in range(buy_date.year, today.year + 1):
        rule_date = dt.date(year, 6, 1)
        july = dt.date(year, 7, 1)
        if buy_date > rule_date or july > current:
            continue  # 과세기준일에 소유하지 않았거나, 아직 납부 달이 오지 않았다
        june = market_price(monthly, rule_date, provisional_from=pending_from)
        if june is None:
            gap_years.append(year)
            continue
        with localcontext() as ctx:
            ctx.prec = CALC_PRECISION
            base = floor1(june.price * holding_tax_base_ratio)
        levy = property_tax(year, base)
        if levy.lump:
            property_payments[july] = TaxPayment(levy.july, "1/1", rule_date, base, june)
        else:
            property_payments[july] = TaxPayment(levy.july, "1/2", rule_date, base, june)
            september = dt.date(year, 9, 1)
            if september <= current:
                property_payments[september] = TaxPayment(levy.september, "2/2", rule_date, base,
                                                          june)
        december = dt.date(year, 12, 1)
        if december <= current:
            comprehensive = comprehensive_tax(year, base)
            comprehensive_payments[december] = TaxPayment(comprehensive.total, "1/1", rule_date,
                                                          base, june)

    rows: list[HoldingRow] = []
    cumulative = 0
    property_total = comprehensive_total = 0
    month = first_month
    while month <= current:
        found = monthly.get(month)
        priced = market_price(monthly, month, provisional_from=pending_from)
        bought = acquisition if month == first_month else None
        property_paid = property_payments.get(month)
        comprehensive_paid = comprehensive_payments.get(month)
        gap = month.year in gap_years
        if bought is not None:
            cumulative += bought.total
        if property_paid is not None:
            cumulative += property_paid.amount
            property_total += property_paid.amount
        if comprehensive_paid is not None:
            cumulative += comprehensive_paid.amount
            comprehensive_total += comprehensive_paid.amount
        value = priced.price if priced is not None else None
        profit = value - price - cumulative if value is not None else None
        rows.append(HoldingRow(
            month=month,
            trades=found.count if found is not None else 0,
            month_average=month_average(monthly, month),
            price=priced,
            acquisition=bought,
            property_tax=property_paid,
            property_tax_gap=gap and month.month in (7, 9),
            comprehensive_tax=comprehensive_paid,
            comprehensive_tax_gap=gap and month.month == 12,
            cumulative_cost=cumulative,
            value=value,
            profit=profit,
            return_rate=_rate(profit, invested) if profit is not None else None,
        ))
        month = add_months(month, 1)

    rows.reverse()  # 최신순
    latest = rows[0]
    # 지금 시세가 없으면 마지막으로 시세가 있던 달까지의 결과다(FR-026)
    valued = next((r for r in rows if r.price is not None), None)
    summary = HoldingSummary(
        as_of=today,
        value=latest.value,
        value_month=latest.month if latest.price is not None else None,
        value_price=latest.price,
        estimated=latest.price.estimated if latest.price is not None else False,
        provisional=latest.price.provisional if latest.price is not None else False,
        profit=valued.profit if valued is not None else None,
        return_rate=valued.return_rate if valued is not None else None,
        cumulative_cost=latest.cumulative_cost,
        property_tax_total=property_total,
        comprehensive_tax_total=comprehensive_total,
        holding_tax_total=property_total + comprehensive_total,
        tax_gaps=tuple(gap_years),
        last_priced_month=valued.month if valued is not None and latest.price is None else None,
    )
    return HoldingResult(
        startable_from=start, startable_basis=basis, buy_date=buy_date, buy_price=price,
        buy_price_source=source, buy_price_window=buy_window, acquisition=acquisition,
        invested=invested,
        rows=tuple(rows), summary=summary,
    )
