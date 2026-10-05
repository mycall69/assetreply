"""세법 표 (T030) — 009 FR-023, research R9-7·R9-7a,
`specs/009-real-estate-investment-simulation/tax-research/`.

표는 계산 로직이 없는 데이터다. 이 테스트가 지키는 것:

- 시행일 구간이 **2006-01-01부터 비거나 겹치지 않고** 마지막 규칙의 끝이 없다(현행) — 표가 덮지 않는
  날짜가 조용히 생기지 않는다
- 연도별 표(재산세·종부세)는 2006~2026년이 모두 있고 그 밖은 `RuleNotCovered` — 가까운 해로 대신하지
  않는다(FR-023)
- 규칙마다 근거(법령·조문·시행일)가 비어 있지 않다(헌법 원칙 VI — 가정을 숨기지 않는다)
- 누진표가 구간 경계에서 이어진다(누진공제가 틀리면 경계에서 세액이 뛴다)
- 비율·세율이 모두 `Decimal`이다(헌법 원칙 VI)
- 대표 시점의 값이 R9-7a 표와 같다
"""
from __future__ import annotations

import dataclasses
import datetime as dt
from decimal import Decimal

import pytest

from src.simulation.apt_tax_rules import (
    ACQUISITION_RULES,
    BROKERAGE_RULES,
    COMPREHENSIVE_TAX_YEARS,
    PROPERTY_TAX_YEARS,
    TAX_RULES_FROM,
    Bracket,
    RateAcquisitionRule,
    ReductionAcquisitionRule,
    RuleNotCovered,
    SplitAcquisitionRule,
    acquisition_rule,
    brokerage_rule,
    comprehensive_tax_year,
    property_tax_year,
)

D = dt.date.fromisoformat
P = Decimal
EOK = 100_000_000
ONE_DAY = dt.timedelta(days=1)


def test_표의_첫_날() -> None:
    assert TAX_RULES_FROM == D("2006-01-01")


@pytest.mark.parametrize("rules", [ACQUISITION_RULES, BROKERAGE_RULES], ids=["취득세", "중개보수"])
def test_시행일_구간이_빈틈없이_이어진다(rules: tuple) -> None:  # type: ignore[type-arg]
    assert rules[0].effective_from == TAX_RULES_FROM
    for before, after in zip(rules, rules[1:], strict=False):
        assert before.effective_to is not None
        assert before.effective_to >= before.effective_from
        assert after.effective_from == before.effective_to + ONE_DAY, after.effective_from
    assert rules[-1].effective_to is None
    assert all(rule.basis.strip() for rule in rules)


def test_연도별_표는_2006년부터_2026년까지() -> None:
    assert sorted(PROPERTY_TAX_YEARS) == list(range(2006, 2027))
    assert sorted(COMPREHENSIVE_TAX_YEARS) == list(range(2006, 2027))
    assert all(y.basis.strip() for y in PROPERTY_TAX_YEARS.values())
    assert all(y.basis.strip() for y in COMPREHENSIVE_TAX_YEARS.values())
    assert all(year == rule.year for year, rule in PROPERTY_TAX_YEARS.items())
    assert all(year == rule.year for year, rule in COMPREHENSIVE_TAX_YEARS.items())


class TestRuleNotCovered:
    def test_취득세_중개보수는_2006년_앞을_덮지_않는다(self) -> None:
        with pytest.raises(RuleNotCovered) as caught:
            acquisition_rule(D("2005-12-31"))
        assert (caught.value.tax, caught.value.on) == ("acquisition", D("2005-12-31"))
        with pytest.raises(RuleNotCovered) as caught:
            brokerage_rule(D("2005-12-20"))
        assert caught.value.tax == "brokerage"

    @pytest.mark.parametrize("year", [2005, 2027])
    def test_보유세는_표에_없는_해를_덮지_않는다(self, year: int) -> None:
        with pytest.raises(RuleNotCovered) as caught:
            property_tax_year(year)
        assert (caught.value.tax, caught.value.on) == ("property", dt.date(year, 6, 1))
        with pytest.raises(RuleNotCovered) as caught:
            comprehensive_tax_year(year)
        assert caught.value.tax == "comprehensive"


@pytest.mark.parametrize(("on", "effective_from", "kind"), [
    ("2006-01-01", "2006-01-01", SplitAcquisitionRule),
    ("2006-08-31", "2006-01-01", SplitAcquisitionRule),
    ("2006-09-01", "2006-09-01", SplitAcquisitionRule),
    ("2010-12-31", "2006-09-01", SplitAcquisitionRule),
    ("2011-01-01", "2011-01-01", ReductionAcquisitionRule),
    ("2011-03-22", "2011-03-22", ReductionAcquisitionRule),
    ("2012-01-01", "2012-01-01", ReductionAcquisitionRule),
    ("2012-09-24", "2012-09-24", ReductionAcquisitionRule),
    ("2013-01-01", "2013-01-01", ReductionAcquisitionRule),
    ("2013-07-01", "2013-07-01", ReductionAcquisitionRule),
    ("2013-08-27", "2013-07-01", ReductionAcquisitionRule),
    ("2013-08-28", "2013-08-28", RateAcquisitionRule),
    ("2019-12-31", "2013-08-28", RateAcquisitionRule),
    ("2020-01-01", "2020-01-01", RateAcquisitionRule),
    ("2026-10-05", "2020-01-01", RateAcquisitionRule),
])
def test_취득세_규칙_찾기(on: str, effective_from: str, kind: type) -> None:
    rule = acquisition_rule(D(on))
    assert rule.effective_from == D(effective_from)
    assert isinstance(rule, kind)


def test_취득세_시기별_값() -> None:
    first = acquisition_rule(D("2006-03-15"))
    assert isinstance(first, SplitAcquisitionRule)
    assert (first.acquisition_reduction, first.registration_reduction) == (P("0.25"), P("0.5"))
    second = acquisition_rule(D("2010-06-15"))
    assert isinstance(second, SplitAcquisitionRule)
    assert (second.acquisition_reduction, second.registration_reduction) == (P("0.5"), P("0.5"))
    extra = acquisition_rule(D("2012-10-15"))
    assert isinstance(extra, ReductionAcquisitionRule)
    assert [(t.upper, t.reduction) for t in extra.tiers] == [
        (9 * EOK, P("0.75")), (12 * EOK, P("0.5")), (None, P("0.25"))]
    gap = acquisition_rule(D("2013-08-27"))
    assert isinstance(gap, ReductionAcquisitionRule)
    assert [(t.upper, t.reduction) for t in gap.tiers] == [(9 * EOK, P("0.5")), (None, P(0))]
    cut = acquisition_rule(D("2016-05-20"))
    assert isinstance(cut, RateAcquisitionRule)
    assert [(t.upper, t.rate) for t in cut.tiers] == [
        (6 * EOK, P("0.01")), (9 * EOK, P("0.02")), (None, P("0.03"))]
    progressive = acquisition_rule(D("2020-01-01"))
    assert isinstance(progressive, RateAcquisitionRule)
    assert [(t.upper, t.rate) for t in progressive.tiers] == [
        (6 * EOK, P("0.01")), (9 * EOK, None), (None, P("0.03"))]


@pytest.mark.parametrize(("on", "effective_from", "tiers"), [
    ("2015-04-13", "2006-01-01",
     [(50_000_000, "0.006", 250_000), (200_000_000, "0.005", 800_000), (600_000_000, "0.004", None),
      (None, "0.009", None)]),
    ("2015-04-14", "2015-04-14",
     [(50_000_000, "0.006", 250_000), (200_000_000, "0.005", 800_000), (600_000_000, "0.004", None),
      (900_000_000, "0.005", None), (None, "0.009", None)]),
    ("2021-10-18", "2015-04-14", None),
    ("2021-10-19", "2021-10-19",
     [(50_000_000, "0.006", 250_000), (200_000_000, "0.005", 800_000), (900_000_000, "0.004", None),
      (1_200_000_000, "0.005", None), (1_500_000_000, "0.006", None), (None, "0.007", None)]),
    ("2026-10-05", "2021-10-19", None),
])
def test_중개보수_규칙(on: str, effective_from: str,
                 tiers: list[tuple[int | None, str, int | None]] | None) -> None:
    rule = brokerage_rule(D(on))
    assert rule.effective_from == D(effective_from)
    if tiers is not None:
        assert [(t.upper, t.rate, t.cap) for t in rule.tiers] == [(u, P(r), c) for u, r, c in tiers]


class TestPropertyYears:
    def test_과세표준_비율(self) -> None:
        def ratios(year: int) -> list[tuple[int | None, Decimal]]:
            return [(t.upper, t.ratio) for t in property_tax_year(year).ratio_tiers]

        assert ratios(2006) == ratios(2007) == ratios(2008) == [(None, P("0.5"))]
        assert ratios(2009) == ratios(2021) == [(None, P("0.6"))]
        assert ratios(2022) == [(None, P("0.45"))]
        assert ratios(2023) == ratios(2026) == [
            (3 * EOK, P("0.43")), (6 * EOK, P("0.44")), (None, P("0.45"))]

    def test_세율표(self) -> None:
        table_a = [(40_000_000, P("0.0015"), 0), (100_000_000, P("0.003"), 60_000),
                   (None, P("0.005"), 260_000)]
        table_b = [(60_000_000, P("0.001"), 0), (150_000_000, P("0.0015"), 30_000),
                   (300_000_000, P("0.0025"), 180_000), (None, P("0.004"), 630_000)]
        table_c = [(60_000_000, P("0.0005"), 0), (150_000_000, P("0.001"), 30_000),
                   (300_000_000, P("0.002"), 180_000), (None, P("0.0035"), 630_000)]

        def rows(table: tuple[Bracket, ...]) -> list[tuple[int | None, Decimal, int]]:
            return [(b.upper, b.rate, b.deduction) for b in table]

        assert rows(property_tax_year(2008).table) == table_a
        assert rows(property_tax_year(2009).table) == table_b
        assert property_tax_year(2020).special_table is None
        for year in range(2021, 2027):
            rule = property_tax_year(year)
            assert rule.special_table is not None and rows(rule.special_table) == table_c
            assert rule.special_max == 9 * EOK

    def test_도시지역분과_7월_일괄_기준(self) -> None:
        y2010, y2011 = property_tax_year(2010), property_tax_year(2011)
        assert (y2010.urban_rate, y2010.urban_separate) == (P("0.0015"), True)
        assert (y2011.urban_rate, y2011.urban_separate) == (P("0.0014"), False)
        years = (2006, 2012, 2013, 2017, 2018, 2026)
        assert [property_tax_year(y).lump_threshold for y in years] == [
            50_000, 50_000, 100_000, 100_000, 200_000, 200_000]
        assert all(y.education_rate == P("0.2") for y in PROPERTY_TAX_YEARS.values())


class TestComprehensiveYears:
    def test_공제와_비율(self) -> None:
        rows = {y: (r.deduction, r.ratio, r.ratio_on_tax)
                for y, r in COMPREHENSIVE_TAX_YEARS.items()}
        assert rows[2006] == (6 * EOK, P("0.7"), True)
        assert rows[2007] == rows[2008] == (6 * EOK, P("0.8"), True)
        assert rows[2009] == rows[2018] == (6 * EOK, P("0.8"), False)
        assert rows[2019] == (6 * EOK, P("0.85"), False)
        assert rows[2020] == (6 * EOK, P("0.9"), False)
        assert rows[2021] == (6 * EOK, P("0.95"), False)
        assert rows[2022] == (6 * EOK, P("0.6"), False)
        assert rows[2023] == rows[2026] == (9 * EOK, P("0.6"), False)

    def test_신고납부_세액공제는_2006_2007만(self) -> None:
        """research R9-7a 결정 2 — 당시 기한 내 신고·납부 3% 세액공제를 넣는다."""
        assert {y for y, r in COMPREHENSIVE_TAX_YEARS.items() if r.filing_credit} == {2006, 2007}
        assert comprehensive_tax_year(2006).filing_credit == P("0.03")

    def test_세율표(self) -> None:
        def rates(year: int) -> list[Decimal]:
            return [b.rate for b in comprehensive_tax_year(year).table]

        assert rates(2006) == rates(2008) == [P("0.01"), P("0.015"), P("0.02"), P("0.03")]
        def pct(*values: str) -> list[Decimal]:
            return [P(v) for v in values]

        assert rates(2009) == rates(2018) == pct("0.005", "0.0075", "0.01", "0.015", "0.02")
        assert rates(2019) == rates(2020) == pct("0.005", "0.007", "0.01", "0.014", "0.02", "0.027")
        assert rates(2021) == rates(2022) == pct("0.006", "0.008", "0.012", "0.016", "0.022",
                                                 "0.03")
        assert rates(2023) == rates(2026) == pct("0.005", "0.007", "0.01", "0.013", "0.015", "0.02",
                                                 "0.027")
        assert all(r.rural_rate == P("0.2") for r in COMPREHENSIVE_TAX_YEARS.values())


def _tables() -> list[tuple[str, tuple[Bracket, ...]]]:
    tables: list[tuple[str, tuple[Bracket, ...]]] = []
    for year, rule in PROPERTY_TAX_YEARS.items():
        tables.append((f"재산세 {year}", rule.table))
        if rule.special_table is not None:
            tables.append((f"재산세 특례 {year}", rule.special_table))
    tables += [(f"종부세 {year}", rule.table) for year, rule in COMPREHENSIVE_TAX_YEARS.items()]
    return tables


@pytest.mark.parametrize(("name", "table"), _tables(), ids=[name for name, _ in _tables()])
def test_누진표가_경계에서_이어진다(name: str, table: tuple[Bracket, ...]) -> None:
    assert table[0].deduction == 0
    assert table[-1].upper is None
    uppers = [b.upper for b in table[:-1]]
    assert all(u is not None for u in uppers)
    assert uppers == sorted(uppers)  # type: ignore[type-var]
    for below, above in zip(table, table[1:], strict=False):
        assert below.upper is not None
        edge = Decimal(below.upper)
        left = edge * below.rate - below.deduction
        assert left == edge * above.rate - above.deduction, (name, below.upper)


def _numbers(obj: object) -> list[object]:
    """데이터 클래스 안의 숫자 값을 모두 모은다(중첩 튜플 포함)."""
    found: list[object] = []
    if dataclasses.is_dataclass(obj):
        for field in dataclasses.fields(obj):
            found += _numbers(getattr(obj, field.name))
    elif isinstance(obj, tuple):
        for item in obj:
            found += _numbers(item)
    elif isinstance(obj, (int, float, Decimal)) and not isinstance(obj, bool):
        found.append(obj)
    return found


def test_비율과_세율은_float가_아니다() -> None:
    rules: list[object] = [*ACQUISITION_RULES, *BROKERAGE_RULES, *PROPERTY_TAX_YEARS.values(),
                           *COMPREHENSIVE_TAX_YEARS.values()]
    numbers = [n for rule in rules for n in _numbers(rule)]
    assert numbers and not [n for n in numbers if isinstance(n, float)]
