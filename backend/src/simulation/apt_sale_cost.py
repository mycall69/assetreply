"""부동산 매도비용 — 매도 중개 보수 + 양도소득세 (010 반복 5, FR-031, research R10-21) — 순수
함수(DB·HTTP 없음, 헌법 원칙 IV).

기준일에 평가액으로 판다고 가정한다. **1세대 1주택, 부부 5:5 공동명의**다.

- 중개 보수: 매수와 같은 규칙(`apt_tax.brokerage_fee` — 서울 조례, 일방, 부가세 없음) — 기준일 규칙
- 양도차익 = 양도가액 − 매입가 − 취득 비용 합계 − 매도 중개 보수(보유세는 필요경비가 아니다)
- 보유 2년·거주 2년 이상이면 비과세 — 양도가액 12억 원 이하는 세금 없음, 넘으면 양도차익 × (양도가액
  − 12억)/양도가액만 과세
- 장기보유특별공제: 비과세 요건 안이고 보유 3년 이상이면 표2(보유 연 4% + 거주 연 4%, 각 최대 40%),
  요건 밖이면 보유 3년 이상에
  표1(연 2%, 최대 30%), 2년 미만 단기는 없음
- 양도소득금액을 부부가 반씩 — 각자 기본공제, 세율(기본세율 또는 단기 60%·70%), 지방소득세 10%를
  계산해 더한다
- 거주 기간 = 보유 일수 × 거주 기간 비율(설정). 연수는 매입일부터 꽉 찬 해(기념일 기준)
- 원화 금액은 원 미만을 버린다. 규칙 표 밖 기준일은 세금을 비운다(`outside_table` — 가까운 해
  규칙으로 메우지 않는다, 헌법 원칙 V)
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from decimal import ROUND_DOWN, Decimal
from typing import Final

from src.simulation.apt_tax import brokerage_fee, floor1
from src.simulation.apt_tax_rules import (
    Bracket,
    RuleNotCovered,
    TransferRule,
    YearlyRate,
    transfer_rule,
)

#: 부부 5:5 공동명의 — 소득금액을 둘로 나눠 각자 계산한다.
OWNERS: Final = 2
_ZERO = Decimal("0")


@dataclass(frozen=True, slots=True)
class AptSaleCost:
    """매도비용(원). 세금을 모르면(`outside_table`) `income_tax`·`local_tax`·`total`이 `None`이다 —
    0이 아니다."""

    brokerage: int
    income_tax: int | None
    local_tax: int | None
    total: int | None
    #: exempt | high_price | taxed | short_term | no_gain | outside_table
    kind: str
    gain: int | None
    taxable_gain: int | None
    ltsd_rate: Decimal | None
    holding_years: int
    residence_years: int
    #: 한 사람의 과세표준(기본공제 뒤).
    base_per_owner: int | None


def complete_years(start: dt.date, end: dt.date) -> int:
    """`start`부터 `end`까지 꽉 찬 해 — 기념일이 지나야 한 해다. 2월 29일은 2월 28일로 본다."""
    years = end.year - start.year
    try:
        anniversary = start.replace(year=end.year)
    except ValueError:
        anniversary = start.replace(year=end.year, day=28)
    return max(years - (1 if end < anniversary else 0), 0)


def residence_years(buy_date: dt.date, sale_date: dt.date, ratio: Decimal) -> int:
    """거주 연수 — 보유 일수 × 비율(일 미만 버림)만큼 산 날까지의 꽉 찬 해."""
    days = Decimal((sale_date - buy_date).days)
    lived = int((days * ratio).to_integral_value(rounding=ROUND_DOWN))
    return complete_years(buy_date, buy_date + dt.timedelta(days=lived))


def _yearly(rate: YearlyRate, years: int) -> Decimal:
    return min(rate.per_year * years, rate.cap) if years >= rate.from_years else _ZERO


def _bracket_tax(brackets: tuple[Bracket, ...], base: int) -> int:
    for bracket in brackets:
        if bracket.upper is None or base <= bracket.upper:
            return floor1(Decimal(base) * bracket.rate - bracket.deduction)
    raise AssertionError("누진표의 마지막 구간은 끝이 없어야 한다")


def _owner_tax(rule: TransferRule, base: int, holding: int) -> int:
    for under, rate in rule.short_term:
        if holding < under:
            return floor1(Decimal(base) * rate)
    return _bracket_tax(rule.brackets, base)


def sale_cost(*, sale_price: int, buy_price: int, acquisition_total: int, buy_date: dt.date,
              sale_date: dt.date, residence_ratio: Decimal) -> AptSaleCost:
    """기준일(`sale_date`)에 `sale_price`로 판다고 가정한 매도비용."""
    brokerage = brokerage_fee(sale_price, sale_date).fee
    holding = complete_years(buy_date, sale_date)
    residence = residence_years(buy_date, sale_date, residence_ratio)
    try:
        rule = transfer_rule(sale_date)
    except RuleNotCovered:
        return AptSaleCost(brokerage, None, None, None, "outside_table", None, None, None, holding,
                           residence, None)

    gain = sale_price - buy_price - acquisition_total - brokerage
    if gain <= 0:
        return AptSaleCost(brokerage, 0, 0, brokerage, "no_gain", gain, 0, _ZERO, holding,
                           residence, 0)

    short = holding < rule.exemption_holding_years
    eligible = not short and residence >= rule.exemption_residence_years
    if eligible and sale_price <= rule.exemption_ceiling:
        return AptSaleCost(brokerage, 0, 0, brokerage, "exempt", gain, 0, _ZERO, holding,
                           residence, 0)

    if eligible:
        kind = "high_price"
        taxable = floor1(Decimal(gain) * (sale_price - rule.exemption_ceiling) / sale_price)
        ltsd = (_yearly(rule.ltsd_home_holding, holding)
                + _yearly(rule.ltsd_home_residence, residence)
                if holding >= rule.ltsd_home_holding.from_years else _ZERO)
    else:
        kind = "short_term" if short else "taxed"
        taxable = gain
        ltsd = _ZERO if short else _yearly(rule.ltsd_general, holding)

    income = taxable - floor1(Decimal(taxable) * ltsd)
    base = max(floor1(Decimal(income) / OWNERS) - rule.basic_deduction, 0)
    tax = _owner_tax(rule, base, holding)
    local = floor1(Decimal(tax) * rule.local_rate)
    income_tax, local_tax = tax * OWNERS, local * OWNERS
    total = brokerage + income_tax + local_tax
    return AptSaleCost(brokerage, income_tax, local_tax, total, kind, gain, taxable, ltsd, holding,
                       residence, base)
