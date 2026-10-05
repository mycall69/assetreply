"""취득 비용·보유세 계산 (T036) — 009 FR-020~FR-024, research R9-7·R9-7a.

`apt_tax_rules.py`의 표를 읽어 세액을 낸다. 끝수 처리(FR-024, 국고금 관리법 제47조 준용):

- 세액·수수료는 **세목마다 10원 미만 버림**, 중간 과세표준은 1원 미만 버림
- 취득세 감면기(2006 ~ 2013-08-27)는 산출세액과 감면세액을 각각 10원 미만 버린 뒤 뺀다(모델 규약 —
  신고서 서식)
- 재산세 분납은 세목마다 9월분 = 연세액 ÷ 2의 10원 미만 버림, 7월분 = 나머지(끝수는 최초 수입금 —
  지방회계법 시행령
  제67조). 7월 일괄 여부는 **지분별(½)** 세액으로 판단한다(research R9-7a 결정 3)

재산세는 주택 전체 기준(공동 소유여도 주택 하나의 세액), 종부세는 부부 각자(인별)로 계산해 둘을
합한다.

**순수 함수 모듈이다.** `repository`·`api`·`db`를 임포트하지 않는다(헌법 원칙 IV). 계산은
`Decimal`이다(헌법 원칙 VI).
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from decimal import ROUND_DOWN, ROUND_HALF_UP, Decimal, localcontext

from src.simulation.apt_tax_rules import (
    Bracket,
    RateAcquisitionRule,
    ReductionAcquisitionRule,
    SplitAcquisitionRule,
    acquisition_rule,
    brokerage_rule,
    comprehensive_tax_year,
    property_tax_year,
)
from src.simulation.money import CALC_PRECISION

_TEN = Decimal(10)
_HUNDRED = Decimal(100)


def floor10(amount: Decimal | int) -> int:
    """10원 미만 버림(음수는 오지 않는다)."""
    value = Decimal(amount)
    return int((value / _TEN).to_integral_value(rounding=ROUND_DOWN)) * 10


def floor1(amount: Decimal | int) -> int:
    """원 미만 버림 — 과세표준·중간값."""
    return int(Decimal(amount).to_integral_value(rounding=ROUND_DOWN))


def _bracket_tax(table: tuple[Bracket, ...], amount: int) -> Decimal:
    """누진표의 세액(끝수 처리 전). 금액이 `upper` 이하인 첫 구간을 쓴다."""
    for bracket in table:
        if bracket.upper is None or amount <= bracket.upper:
            return Decimal(amount) * bracket.rate - bracket.deduction
    raise AssertionError("누진표의 마지막 구간은 끝이 없어야 한다")


# ── 취득세 ──────────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class AcquisitionTax:
    """취득세 본세(2010년까지는 취득세 + 등록세), 지방교육세, 농어촌특별세."""

    main: int
    education: int
    rural: int
    rule_from: dt.date

    @property
    def total(self) -> int:
        return self.main + self.education + self.rural


@dataclass(frozen=True, slots=True)
class BrokerageFee:
    fee: int
    rule_from: dt.date


@dataclass(frozen=True, slots=True)
class AcquisitionCost:
    """매입 때 한 번 내는 비용 — 표의 매입 행에 항목별로 보인다(FR-020)."""

    acquisition_tax: int
    education_tax: int
    rural_tax: int
    brokerage_fee: int
    acquisition_rule_from: dt.date
    brokerage_rule_from: dt.date

    @property
    def total(self) -> int:
        return self.acquisition_tax + self.education_tax + self.rural_tax + self.brokerage_fee


def _split_tax(rule: SplitAcquisitionRule, price: int, exceeds_85: bool) -> AcquisitionTax:
    acq_calc = floor10(price * rule.acquisition_rate)
    acq_cut = floor10(acq_calc * rule.acquisition_reduction)
    reg_calc = floor10(price * rule.registration_rate)
    reg_cut = floor10(reg_calc * rule.registration_reduction)
    acquisition, registration = acq_calc - acq_cut, reg_calc - reg_cut
    rural = 0
    if exceeds_85:
        rural = floor10(acquisition * rule.rural_acquisition_rate) + floor10(
            (acq_cut + reg_cut) * rule.rural_reduction_rate)
    education = floor10(registration * rule.education_rate)
    return AcquisitionTax(acquisition + registration, education, rural, rule.effective_from)


def _reduction_tax(rule: ReductionAcquisitionRule, price: int, exceeds_85: bool) -> AcquisitionTax:
    reduction = next(t.reduction for t in rule.tiers if t.upper is None or price <= t.upper)
    calc = floor10(price * rule.standard_rate)
    cut = floor10(calc * reduction)
    education_calc = floor10(price * rule.education_base_rate * rule.education_rate)
    education = education_calc - floor10(education_calc * reduction)
    rural = 0
    if exceeds_85:
        # 표준세율 2%로 산출한 취득세(지특법 감면 뒤) × 10% + 취득세 감면세액 × 20%
        base_calc = floor10(price * rule.rural_base_rate)
        base = base_calc - floor10(base_calc * reduction)
        rural = (floor10(base * rule.rural_acquisition_rate)
                 + floor10(cut * rule.rural_reduction_rate))
    return AcquisitionTax(calc - cut, education, rural, rule.effective_from)


def _progressive_rate(rule: RateAcquisitionRule, price: int) -> Decimal:
    """(V × 2/3억 − 3) × 1/100 — 비율 기준 소수 넷째 자리에서 사사오입(위택스·서울 ETAX와 같다)."""
    with localcontext() as ctx:
        ctx.prec = CALC_PRECISION
        raw = (Decimal(price) * rule.progressive_numerator / rule.progressive_denominator
               - rule.progressive_offset) / _HUNDRED
        return raw.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


def _rate_tax(rule: RateAcquisitionRule, price: int, exceeds_85: bool) -> AcquisitionTax:
    tier = next(t for t in rule.tiers if t.upper is None or price <= t.upper)
    rate = tier.rate if tier.rate is not None else _progressive_rate(rule, price)
    main = floor10(price * rate)
    education = floor10(floor1(price * rate * rule.education_share) * rule.education_rate)
    rural = floor10(floor1(price * rule.rural_base_rate) * rule.rural_rate) if exceeds_85 else 0
    return AcquisitionTax(main, education, rural, rule.effective_from)


def acquisition_tax(price: int, on: dt.date, *, exceeds_85: bool) -> AcquisitionTax:
    """매입일에 시행 중인 규칙의 취득세(FR-020). 표 밖의 날짜는 `RuleNotCovered`."""
    rule = acquisition_rule(on)
    with localcontext() as ctx:
        ctx.prec = CALC_PRECISION
        if isinstance(rule, SplitAcquisitionRule):
            return _split_tax(rule, price, exceeds_85)
        if isinstance(rule, ReductionAcquisitionRule):
            return _reduction_tax(rule, price, exceeds_85)
        return _rate_tax(rule, price, exceeds_85)


def brokerage_fee(price: int, on: dt.date) -> BrokerageFee:
    """매입일의 법정 상한 중개 보수(서울, 매수인 일방, 부가세 없음). 한도액이 있으면 그 이하."""
    rule = brokerage_rule(on)
    tier = next(t for t in rule.tiers if t.upper is None or price < t.upper)
    with localcontext() as ctx:
        ctx.prec = CALC_PRECISION
        fee = floor10(price * tier.rate)
    if tier.cap is not None:
        fee = min(fee, tier.cap)
    return BrokerageFee(fee, rule.effective_from)


def acquisition_cost(price: int, on: dt.date, *, exceeds_85: bool) -> AcquisitionCost:
    tax = acquisition_tax(price, on, exceeds_85=exceeds_85)
    fee = brokerage_fee(price, on)
    return AcquisitionCost(tax.main, tax.education, tax.rural, fee.fee, tax.rule_from,
                           fee.rule_from)


# ── 재산세 ──────────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class PropertyTax:
    """한 해의 주택분 재산세(주택 전체). `september`가 0이면 7월에 전부 낸다."""

    year: int
    base_price: int
    tax_base: int
    main: int
    urban: int
    education: int
    july: int
    september: int

    @property
    def total(self) -> int:
        return self.main + self.urban + self.education

    @property
    def lump(self) -> bool:
        return self.september == 0


def _property_ratio(year: int, base_price: int) -> Decimal:
    rule = property_tax_year(year)
    return next(t.ratio for t in rule.ratio_tiers if t.upper is None or base_price <= t.upper)


def _property_main(year: int, base_price: int) -> tuple[int, int]:
    """(과세표준, 본세). 1세대 1주택 특례는 시가표준액이 기준 이하일 때만이다."""
    rule = property_tax_year(year)
    tax_base = floor1(base_price * _property_ratio(year, base_price))
    table = rule.table
    special_max = rule.special_max
    if rule.special_table is not None and special_max is not None and base_price <= special_max:
        table = rule.special_table
    return tax_base, floor10(_bracket_tax(table, tax_base))


def _halves(amount: int) -> tuple[int, int]:
    september = floor10(Decimal(amount) / 2)
    return amount - september, september


def property_tax(year: int, base_price: int) -> PropertyTax:
    """그해 과세기준일의 재산세. `base_price`는 공시가격 대용(6월 시세 × 기준 비율)이다(FR-021)."""
    rule = property_tax_year(year)
    with localcontext() as ctx:
        ctx.prec = CALC_PRECISION
        tax_base, main = _property_main(year, base_price)
        urban = floor10(tax_base * rule.urban_rate)
        education = floor10(main * rule.education_rate)
    threshold = 2 * rule.lump_threshold  # 지분별(½) 세액 ≤ 기준 ⇔ 주택 전체 ≤ 기준 × 2
    if rule.urban_separate:
        # 2010년까지 — 재산세(지방교육세는 재산세를 따른다)와 도시계획세를 따로 판단한다
        main_lump, urban_lump = main <= threshold, urban <= threshold
    else:
        main_lump = urban_lump = main + urban <= threshold
    july = september = 0
    for amount, lump in ((main, main_lump), (education, main_lump), (urban, urban_lump)):
        if lump:
            july += amount
        else:
            first, second = _halves(amount)
            july, september = july + first, september + second
    return PropertyTax(year, base_price, tax_base, main, urban, education, july, september)


# ── 종합부동산세 ────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class ComprehensiveTax:
    """한 해의 주택분 종합부동산세 — 부부 각자의 세액과 농어촌특별세, 둘의 합."""

    year: int
    base_price: int
    per_person_tax: int
    per_person_rural: int

    @property
    def tax(self) -> int:
        return 2 * self.per_person_tax

    @property
    def rural(self) -> int:
        return 2 * self.per_person_rural

    @property
    def total(self) -> int:
        return self.tax + self.rural


def comprehensive_tax(year: int, base_price: int) -> ComprehensiveTax:
    """그해 12월에 내는 종부세(FR-022). 부부 5:5 — 1인 지분 = 기준 금액 ÷ 2, 1인 공제, 두 사람
    합."""
    rule = comprehensive_tax_year(year)
    property_rule = property_tax_year(year)
    with localcontext() as ctx:
        ctx.prec = CALC_PRECISION
        share = floor1(Decimal(base_price) / 2)
        if share <= rule.deduction:
            return ComprehensiveTax(year, base_price, 0, 0)
        if rule.ratio_on_tax:  # 2006~2008 — 과세표준은 공제 뒤 금액, 적용비율은 세액에 곱한다
            tax_base = share - rule.deduction
            computed = floor10(_bracket_tax(rule.table, tax_base) * rule.ratio)
        else:
            tax_base = floor1((share - rule.deduction) * rule.ratio)
            computed = floor10(_bracket_tax(rule.table, tax_base))
        # 재산세 중복분 공제: ⑥ 지분 재산세 × ⑦ 과세표준분 표준세율 재산세 ÷ ⑧ 지분 재산세 표준세액
        property_ratio = _property_ratio(year, base_price)
        top_rate = property_rule.table[-1].rate
        _, house_main = _property_main(year, base_price)
        share_property = floor10(Decimal(house_main) / 2)
        overlap_base = floor10(tax_base * property_ratio * top_rate)
        share_standard = floor10(_bracket_tax(property_rule.table, floor1(share * property_ratio)))
        deduction = 0
        if share_standard:
            deduction = floor10(Decimal(share_property) * overlap_base / share_standard)
        tax = max(0, computed - deduction)
        tax -= floor10(tax * rule.filing_credit)
        rural = floor10(tax * rule.rural_rate)
    return ComprehensiveTax(year, base_price, tax, rural)
