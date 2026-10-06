"""세법 표 (T036) — 009 FR-020~FR-024, research R9-7·R9-7a.

**계산 로직이 없는 데이터 모듈이다.** 시행일 구간마다 세목별 규칙 하나를 두고, 규칙마다
근거(법령·조문·시행일)를 적는다. 세액 계산은 `apt_tax.py`가 이 표를 읽어 한다. 값과 근거의 원문·참조
사례는 `specs/009-real-estate-investment-simulation/ tax-research/`의 네
문서(acquisition·brokerage·property·comprehensive)에 있다 — 표를 고치면 그 문서와 테스트의 참조값을
함께 고친다.

- 취득세·중개 보수는 **매입일**에 시행 중인 규칙, 재산세·종부세는 그해 **과세기준일(6월 1일)**의
  규칙이다
- 표는 **2006-01-01부터**다(실거래가 과세 시작). 표가 덮지 않는 날짜·해는 `RuleNotCovered` — 가까운
  해의 규칙으로
  대신하지 않는다(FR-023). 재산세 1세대 1주택 특례와 특례 비율이 2026년분까지만 법령에 있어 보유세
  표는 2026년에서 끝난다
- 세법이 바뀌면(새 시행일) 규칙을 더하고 현행 규칙의 끝을 닫는다. 근거와 참조 사례를 함께 더한다
- 비율·세율은 모두 `Decimal`이다(헌법 원칙 VI)

모델 규약과 결정(research R9-7a): 1세대 1주택 매수, 부부 5:5 공동명의, 중개 보수는 서울특별시 조례
기준, 종부세는 인별 기본공제, 2009~2015 종부세의 재산세 중복분 공제는 당시 고지 서식, 2006·2007
종부세는 기한 내 신고·납부 3% 세액공제, 재산세 7월 일괄은 지분별 판단, 세부담
상한·과세표준상한제·서민주택 취득세 면제는 넣지 않는다.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from decimal import Decimal

#: 세법 표의 첫 날 — 실거래가 과세 시작(research R9-7a). 출처는 2005-12 계약분부터 주지만 그
#: 매입일은 계산하지 않는다.
TAX_RULES_FROM = dt.date(2006, 1, 1)

_EOK = 100_000_000
P = Decimal


class RuleNotCovered(Exception):  # noqa: N818 — API `tax_rule_not_covered`
    """세법 표가 그 날짜(또는 그해 과세기준일)를 덮지 않는다(FR-023)."""

    def __init__(self, tax: str, on: dt.date) -> None:
        super().__init__(f"{tax} 세법 표가 {on.isoformat()}을 덮지 않습니다")
        self.tax = tax
        self.on = on


# ── 공통 형식 ───────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class Bracket:
    """누진 구간 — 금액이 `upper` 이하(마지막은 끝 없음)이면 세액 = 금액 × rate −
    deduction(누진공제)."""

    upper: int | None
    rate: Decimal
    deduction: int


# ── 취득세 ──────────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class SplitAcquisitionRule:
    """2006-01-01 ~ 2010-12-31 — 취득세·등록세가 따로였다. 둘을 합쳐 "취득세 본세"로 보인다.

    납부할 취득세 = 산출(V × acquisition_rate) − 감면(산출 × acquisition_reduction), 등록세도 같다.
    지방교육세 = 납부할 등록세 × education_rate. 농어촌특별세(85㎡ 초과) = 납부할 취득세 ×
    rural_acquisition_rate + (취득세·등록세 감면세액) × rural_reduction_rate.
    """

    effective_from: dt.date
    effective_to: dt.date | None
    acquisition_rate: Decimal
    acquisition_reduction: Decimal
    registration_rate: Decimal
    registration_reduction: Decimal
    education_rate: Decimal
    rural_acquisition_rate: Decimal
    rural_reduction_rate: Decimal
    basis: str


@dataclass(frozen=True, slots=True)
class ReductionTier:
    """감면 구간 — 매입가가 `upper` 이하(마지막은 끝 없음)이면 표준세율 세액에서 `reduction`만큼
    경감한다."""

    upper: int | None
    reduction: Decimal


@dataclass(frozen=True, slots=True)
class ReductionAcquisitionRule:
    """2011-01-01 ~ 2013-08-27 — 취득세 표준세율 4%에 지방세특례제한법 제40조의2 감면.

    취득세 = 산출(V × standard_rate) − 감면(산출 × 경감률). 지방교육세 = V × education_base_rate ×
    education_rate × (1 − 경감률) — 산출과 감면을 따로 끝수 처리한다. 농어촌특별세(85㎡ 초과) = V ×
    rural_base_rate × (1 − 경감률) × rural_acquisition_rate
                              + 취득세 감면세액 × rural_reduction_rate.
    """

    effective_from: dt.date
    effective_to: dt.date | None
    standard_rate: Decimal
    education_base_rate: Decimal
    education_rate: Decimal
    rural_base_rate: Decimal
    rural_acquisition_rate: Decimal
    rural_reduction_rate: Decimal
    tiers: tuple[ReductionTier, ...]
    basis: str


@dataclass(frozen=True, slots=True)
class RateTier:
    """세율 구간 — 매입가가 `upper` 이하(마지막은 끝 없음)이면 `rate`. `rate`가 None이면 누진
    산식(2020~ 6~9억)."""

    upper: int | None
    rate: Decimal | None


@dataclass(frozen=True, slots=True)
class RateAcquisitionRule:
    """2013-08-28 ~ — 주택 유상거래 세율(지방세법 제11조 제1항 제8호).

    취득세 = V × r. 누진 구간의 r = (V × progressive_numerator / progressive_denominator −
    progressive_offset) / 100을 비율 기준 소수 넷째 자리에서 사사오입한다(7억 → 0.0167). 지방교육세
    = V × r × education_share × education_rate. 농어촌특별세(85㎡ 초과) = V × rural_base_rate ×
    rural_rate.
    """

    effective_from: dt.date
    effective_to: dt.date | None
    tiers: tuple[RateTier, ...]
    progressive_numerator: int
    progressive_denominator: int
    progressive_offset: int
    education_share: Decimal
    education_rate: Decimal
    rural_base_rate: Decimal
    rural_rate: Decimal
    basis: str


AcquisitionRule = SplitAcquisitionRule | ReductionAcquisitionRule | RateAcquisitionRule


def _split(start: str, end: str, acquisition_reduction: str, basis: str) -> SplitAcquisitionRule:
    return SplitAcquisitionRule(
        effective_from=dt.date.fromisoformat(start), effective_to=dt.date.fromisoformat(end),
        acquisition_rate=P("0.02"), acquisition_reduction=P(acquisition_reduction),
        registration_rate=P("0.02"), registration_reduction=P("0.5"),
        education_rate=P("0.2"), rural_acquisition_rate=P("0.1"), rural_reduction_rate=P("0.2"),
        basis=basis,
    )


def _reduction(start: str, end: str, tiers: tuple[tuple[int | None, str], ...],
               basis: str) -> ReductionAcquisitionRule:
    return ReductionAcquisitionRule(
        effective_from=dt.date.fromisoformat(start), effective_to=dt.date.fromisoformat(end),
        standard_rate=P("0.04"), education_base_rate=P("0.02"), education_rate=P("0.2"),
        rural_base_rate=P("0.02"), rural_acquisition_rate=P("0.1"), rural_reduction_rate=P("0.2"),
        tiers=tuple(ReductionTier(upper, P(reduction)) for upper, reduction in tiers),
        basis=basis,
    )


def _rate(start: str, end: str | None, tiers: tuple[tuple[int | None, str | None], ...],
          basis: str) -> RateAcquisitionRule:
    return RateAcquisitionRule(
        effective_from=dt.date.fromisoformat(start),
        effective_to=dt.date.fromisoformat(end) if end else None,
        tiers=tuple(RateTier(upper, P(rate) if rate is not None else None)
                    for upper, rate in tiers),
        progressive_numerator=2, progressive_denominator=3 * _EOK, progressive_offset=3,
        education_share=P("0.5"), education_rate=P("0.2"),
        rural_base_rate=P("0.02"), rural_rate=P("0.1"),
        basis=basis,
    )


ACQUISITION_RULES: tuple[AcquisitionRule, ...] = (
    _split("2006-01-01", "2006-08-31", "0.25",
           "구 지방세법(법률 제7843호, 2006.1.1 시행) 제112조①·제131조①3호·제273조의2(개인 간 "
           "주택거래 취득세 25%·"
           "등록세 50% 경감)·제260조의3①1호. 농특세법 제5조①1호·6호, 제4조9호·11호(85㎡ 이하 "
           "비과세)"),
    _split("2006-09-01", "2010-12-31", "0.5",
           "구 지방세법 제273조의2(법률 제7972호, 2006.9.1 시행 — 개인 간 요건 삭제, 취득세·등록세 "
           "50% 경감). "
           "적용시한 법률 제9924호(2010.1.1)로 2010.12.31까지"),
    _reduction("2011-01-01", "2011-03-21", ((9 * _EOK, "0.5"), (None, "0")),
               "지방세법(법률 제10221호 전부개정, 2011.1.1 시행) 제11조①7호나목(4%)·제151조①1호. "
               "지방세특례제한법 제40조의2(법률 제10417호 — 9억 이하 1주택 50% 경감)"),
    _reduction("2011-03-22", "2011-12-31", ((9 * _EOK, "0.75"), (None, "0.5")),
               "지방세특례제한법 제40조의2 전문개정(법률 제10654호, 2011.5.19 공포, 부칙 제2조로 "
               "2011.3.22 취득분부터 소급)"),
    _reduction("2012-01-01", "2012-09-23", ((9 * _EOK, "0.5"), (None, "0")),
               "지방세특례제한법 제40조의2(법률 제11138호, 2012.1.1 시행 — 9억 이하 1주택 50% "
               "경감)"),
    _reduction("2012-09-24", "2012-12-31", ((9 * _EOK, "0.75"), (12 * _EOK, "0.5"), (None, "0.25")),
               "지방세특례제한법 제40조의2 전문개정(법률 제11487호, 2012.10.2 공포, 부칙 제2조로 "
               "2012.9.24 취득분부터 소급)"),
    _reduction("2013-01-01", "2013-06-30", ((9 * _EOK, "0.75"), (12 * _EOK, "0.5"), (None, "0.25")),
               "지방세특례제한법 제40조의2①(법률 제11716호, 2013.3.23 공포, 부칙 제2조로 2013.1.1 "
               "취득분부터 소급)"),
    _reduction("2013-07-01", "2013-08-27", ((9 * _EOK, "0.5"), (None, "0")),
               "지방세특례제한법 제40조의2②(법률 제11716호 — 2013.7.1~12.31 9억 이하 1주택 50% "
               "경감)"),
    _rate("2013-08-28", "2019-12-31", ((6 * _EOK, "0.01"), (9 * _EOK, "0.02"), (None, "0.03")),
          "지방세법 제11조①8호 신설(법률 제12118호, 2013.12.26 공포, 부칙 제2조로 2013.8.28 "
          "취득분부터 소급). "
          "지방교육세 제151조①1호(법률 제12153호, 2014.1.1 — 같은 날짜까지 소급). 농특세법 "
          "제5조①6호"),
    _rate("2020-01-01", None, ((6 * _EOK, "0.01"), (9 * _EOK, None), (None, "0.03")),
          "지방세법 제11조①8호 가~다목(법률 제16855호, 2019.12.31 공포, 2020.1.1 시행 — 6억 초과 "
          "9억 이하 누진 산식, "
          "소수점 이하 다섯째 자리에서 반올림). 2020.8.12 다주택 중과(제13조의2)는 1세대 1주택에 "
          "해당 없음. "
          "2026-10-05 현재 변경 없음"),
)


# ── 중개 보수 ───────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class BrokerageTier:
    """중개 보수 구간 — 거래금액이 `upper` **미만**(마지막은 끝 없음)이면 상한 요율 `rate`, 한도
    `cap`(없으면 None)."""

    upper: int | None
    rate: Decimal
    cap: int | None


@dataclass(frozen=True, slots=True)
class BrokerageRule:
    """주택 매매·교환의 법정 상한 중개 보수(매수인 일방, 부가세 별도) — 서울특별시 기준."""

    effective_from: dt.date
    effective_to: dt.date | None
    tiers: tuple[BrokerageTier, ...]
    basis: str


def _brokerage(start: str, end: str | None, tiers: tuple[tuple[int | None, str, int | None], ...],
               basis: str) -> BrokerageRule:
    return BrokerageRule(
        effective_from=dt.date.fromisoformat(start),
        effective_to=dt.date.fromisoformat(end) if end else None,
        tiers=tuple(BrokerageTier(upper, P(rate), cap) for upper, rate, cap in tiers),
        basis=basis,
    )


BROKERAGE_RULES: tuple[BrokerageRule, ...] = (
    _brokerage("2006-01-01", "2015-04-13",
               ((50_000_000, "0.006", 250_000), (200_000_000, "0.005", 800_000),
                (600_000_000, "0.004", None), (None, "0.009", None)),
               "서울특별시 부동산중개수수료 조례(제3821호, 2001.1.5) [별표1] → 서울특별시 주택 "
               "중개수수료등에관한 조례"
               "(제4531호, 2007.5.29 전부개정 — 매매 요율 같음) [별표 1]. 6억 이상은 '1천분의 9 "
               "이하'(협의 상한)"),
    _brokerage("2015-04-14", "2021-10-18",
               ((50_000_000, "0.006", 250_000), (200_000_000, "0.005", 800_000),
                (600_000_000, "0.004", None), (900_000_000, "0.005", None), (None, "0.009", None)),
               "서울특별시 주택 중개보수 등에 관한 조례(제5858호, 2015.4.14 공포·시행) [별표 1] — "
               "6억~9억 0.5% 신설. "
               "전환은 중개계약일 기준이나 매입일(매매계약일 = 중개계약일로 본다)로 판정한다"),
    _brokerage("2021-10-19", None,
               ((50_000_000, "0.006", 250_000), (200_000_000, "0.005", 800_000),
                (900_000_000, "0.004", None), (1_200_000_000, "0.005", None),
                (1_500_000_000, "0.006", None), (None, "0.007", None)),
               "공인중개사법 시행규칙(국토교통부령 제902호, 2021.10.19 시행) 제20조①·[별표 1], "
               "부칙 제2조(매매계약 "
               "체결일 기준, 2021.12.29까지 서울 종전 조례의 초과분은 별표 1로 제한). 서울 조례 "
               "제8296호(2021.12.30)·"
               "현행 제8585호와 같음. 2026-10-05 현재 변경 없음"),
)


# ── 재산세 ──────────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class RatioTier:
    """과세표준 비율 구간 — 시가표준액(공시가격 대용)이 `upper` 이하(마지막은 끝 없음)이면
    `ratio`."""

    upper: int | None
    ratio: Decimal


@dataclass(frozen=True, slots=True)
class PropertyTaxYear:
    """한 과세연도의 주택분 재산세(1세대 1주택, 주택 전체 기준).

    과세표준 = 시가표준액 × 비율. 본세 = 세율표(과세표준) — 1세대 1주택이고 시가표준액이
    `special_max` 이하이면 특례 세율표. 도시지역분(2010년까지는 도시계획세) = 과세표준 × urban_rate.
    지방교육세 = 본세 × education_rate. 7월·9월에 반씩, 지분별(½) 세액이 `lump_threshold` 이하이면
    7월에 전부 — 2010년까지는 도시계획세를 따로 판단한다.
    """

    year: int
    ratio_tiers: tuple[RatioTier, ...]
    table: tuple[Bracket, ...]
    special_table: tuple[Bracket, ...] | None
    special_max: int | None
    urban_rate: Decimal
    urban_separate: bool
    education_rate: Decimal
    lump_threshold: int
    basis: str


#: 표 A — 2006~2008 주택 재산세(구 지방세법 제188조①3호나목). 4천만·1억 경계.
PROPERTY_TABLE_A: tuple[Bracket, ...] = (
    Bracket(40_000_000, P("0.0015"), 0),
    Bracket(100_000_000, P("0.003"), 60_000),
    Bracket(None, P("0.005"), 260_000),
)
#: 표 B — 2009~ 주택 재산세 표준세율(구법 제188조, 현행 제111조①3호나목). 6천만·1.5억·3억 경계.
PROPERTY_TABLE_B: tuple[Bracket, ...] = (
    Bracket(60_000_000, P("0.001"), 0),
    Bracket(150_000_000, P("0.0015"), 30_000),
    Bracket(300_000_000, P("0.0025"), 180_000),
    Bracket(None, P("0.004"), 630_000),
)
#: 표 C — 2021~2026 1세대 1주택 특례세율(제111조의2 — 시가표준액 9억 이하). 표 B − 과세표준 × 0.05%.
PROPERTY_TABLE_C: tuple[Bracket, ...] = (
    Bracket(60_000_000, P("0.0005"), 0),
    Bracket(150_000_000, P("0.001"), 30_000),
    Bracket(300_000_000, P("0.002"), 180_000),
    Bracket(None, P("0.0035"), 630_000),
)

_FLAT_50: tuple[RatioTier, ...] = (RatioTier(None, P("0.5")),)
_FLAT_60: tuple[RatioTier, ...] = (RatioTier(None, P("0.6")),)
_FLAT_45: tuple[RatioTier, ...] = (RatioTier(None, P("0.45")),)
_TIERED_43_45: tuple[RatioTier, ...] = (
    RatioTier(3 * _EOK, P("0.43")), RatioTier(6 * _EOK, P("0.44")), RatioTier(None, P("0.45")))

_PROPERTY_BASIS = {
    2006: "구 지방세법 제187·188·191조, 부칙(법률 제7843호) 제5조 제2호(적용비율 50%), 도시계획세 "
          "제237조 0.15%",
    2007: "구 지방세법(법률 제8147호) — 2006과 같음",
    2008: "부칙(법률 제7843호) 제5조 제2호 55% 고지 → 법률 제9422호(2009.2.6) 부칙 제2조가 "
          "2008년도분 50%로 소급",
    2009: "구 지방세법 제187·188조(법률 제9422호, 2009.2.6 시행 — 표 B), 시행령 "
          "제138조(공정시장가액비율 60%)",
    2010: "구 지방세법(법률 제9924호), 시행령 제138조. 도시계획세 0.15%",
    2011: "지방세법(법률 제10221호 전부개정, 2011.1.1) 제110·111·112·115·151조, 시행령 제109조. "
          "도시지역분 0.14%",
    2012: "지방세법(법률 제11137호 판) — 2011과 같음",
    2013: "지방세법 제115조(법률 제11617호, 2013.1.1 — 7월 일괄 기준 10만 원)",
    2018: "지방세법 제115조①3호(법률 제15292호, 2018.1.1 — 7월 일괄 기준 20만 원)",
    2021: "지방세법 제111조의2 신설(법률 제17769호) — 1세대 1주택 특례세율, 법률 "
          "제18294호(2021.7.8)로 시가표준액 9억 "
          "이하로 확대(2021.6.1 납세의무분부터)",
    2022: "지방세법 시행령 제109조①2호 단서(대통령령 제32747호, 2022.6.30 — 2022년도 1세대 1주택 "
          "45%)",
    2023: "지방세법 시행령 제109조①2호 단서(대통령령 제33609호, 2023.6.30 — 3억 이하 43%, 6억 이하 "
          "44%, 초과 45%)",
    2024: "대통령령 제34528호(2024.5.28) 43/44/45%. 특례세율 유효기간 6년으로 연장(법률 제19860호, "
          "2023.12.29)",
    2025: "대통령령 제35544호(2025.5.27) 43/44/45%",
    2026: "대통령령 제36364호(2026.5.29 공포, 2026.6.1 시행) 43/44/45%. 특례세율은 2026.12.28 "
          "성립분까지",
}


def _property_year(year: int) -> PropertyTaxYear:
    if year <= 2008:
        ratio, table = _FLAT_50, PROPERTY_TABLE_A
    elif year <= 2021:
        ratio, table = _FLAT_60, PROPERTY_TABLE_B
    elif year == 2022:
        ratio, table = _FLAT_45, PROPERTY_TABLE_B
    else:
        ratio, table = _TIERED_43_45, PROPERTY_TABLE_B
    special = year >= 2021
    if year <= 2012:
        lump = 50_000
    elif year <= 2017:
        lump = 100_000
    else:
        lump = 200_000
    # 근거가 바뀌지 않은 해는 마지막으로 바뀐 해의 근거를 그대로 적는다(값은 해마다 위에서 정한다)
    basis = _PROPERTY_BASIS[max(y for y in _PROPERTY_BASIS if y <= year)]
    return PropertyTaxYear(
        year=year, ratio_tiers=ratio, table=table,
        special_table=PROPERTY_TABLE_C if special else None,
        special_max=9 * _EOK if special else None,
        urban_rate=P("0.0015") if year <= 2010 else P("0.0014"), urban_separate=year <= 2010,
        education_rate=P("0.2"), lump_threshold=lump, basis=basis,
    )


PROPERTY_TAX_YEARS: dict[int, PropertyTaxYear] = {
    year: _property_year(year) for year in range(2006, 2027)}


# ── 종합부동산세 ────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class ComprehensiveTaxYear:
    """한 과세연도의 주택분 종합부동산세 — 부부 각자(인별) 지분 공시가격에 1인 공제.

    2009~: 과세표준 = (지분 공시가격 − 공제) × 공정시장가액비율, 세액 = 세율표(과세표준). 2006~2008:
    과세표준 = 지분 공시가격 − 공제, 세액 = 세율표(과세표준) × 적용비율(`ratio_on_tax`). 재산세
    중복분 공제 = 지분 재산세 × (과세표준 × 재산세 비율 × 재산세 최고 세율) ÷ 재산세표(지분 × 재산세
    비율) — 2009~2015도 당시 고지 서식대로 과세표준(공정시장가액비율을 곱한 값)을 쓴다(research
    R9-7a 결정 1).
    """

    year: int
    deduction: int
    ratio: Decimal
    ratio_on_tax: bool
    table: tuple[Bracket, ...]
    filing_credit: Decimal
    rural_rate: Decimal
    basis: str


#: R1 — 2006~2008(법률 제7836호 제9조①). 3억·14억·94억.
COMPREHENSIVE_TABLE_R1: tuple[Bracket, ...] = (
    Bracket(3 * _EOK, P("0.01"), 0),
    Bracket(14 * _EOK, P("0.015"), 1_500_000),
    Bracket(94 * _EOK, P("0.02"), 8_500_000),
    Bracket(None, P("0.03"), 102_500_000),
)
#: R2 — 2009~2018(법률 제9273호 제9조①). 6억·12억·50억·94억.
COMPREHENSIVE_TABLE_R2: tuple[Bracket, ...] = (
    Bracket(6 * _EOK, P("0.005"), 0),
    Bracket(12 * _EOK, P("0.0075"), 1_500_000),
    Bracket(50 * _EOK, P("0.01"), 4_500_000),
    Bracket(94 * _EOK, P("0.015"), 29_500_000),
    Bracket(None, P("0.02"), 76_500_000),
)
#: R3 — 2019~2020(법률 제16109호 제9조①1호, 2주택 이하). 3억·6억·12억·50억·94억.
COMPREHENSIVE_TABLE_R3: tuple[Bracket, ...] = (
    Bracket(3 * _EOK, P("0.005"), 0),
    Bracket(6 * _EOK, P("0.007"), 600_000),
    Bracket(12 * _EOK, P("0.01"), 2_400_000),
    Bracket(50 * _EOK, P("0.014"), 7_200_000),
    Bracket(94 * _EOK, P("0.02"), 37_200_000),
    Bracket(None, P("0.027"), 103_000_000),
)
#: R4 — 2021~2022(법률 제17478호 제9조①1호).
COMPREHENSIVE_TABLE_R4: tuple[Bracket, ...] = (
    Bracket(3 * _EOK, P("0.006"), 0),
    Bracket(6 * _EOK, P("0.008"), 600_000),
    Bracket(12 * _EOK, P("0.012"), 3_000_000),
    Bracket(50 * _EOK, P("0.016"), 7_800_000),
    Bracket(94 * _EOK, P("0.022"), 37_800_000),
    Bracket(None, P("0.03"), 113_000_000),
)
#: R5 — 2023~(법률 제19200호 제9조①1호). 3억·6억·12억·25억·50억·94억.
COMPREHENSIVE_TABLE_R5: tuple[Bracket, ...] = (
    Bracket(3 * _EOK, P("0.005"), 0),
    Bracket(6 * _EOK, P("0.007"), 600_000),
    Bracket(12 * _EOK, P("0.01"), 2_400_000),
    Bracket(25 * _EOK, P("0.013"), 6_000_000),
    Bracket(50 * _EOK, P("0.015"), 11_000_000),
    Bracket(94 * _EOK, P("0.02"), 36_000_000),
    Bracket(None, P("0.027"), 101_800_000),
)

_COMPREHENSIVE: dict[int, tuple[int, str, bool, tuple[Bracket, ...], str, str]] = {
    2006: (6 * _EOK, "0.7", True, COMPREHENSIVE_TABLE_R1, "0.03",
           "종합부동산세법(법률 제7836호) 제8조①·제9조①②(적용비율 70%), 시행령 제4조의2. 세대별 "
           "합산은 헌재 2008.11.13. "
           "2006헌바112 위헌 — 인별 계산. 기한 내 신고·납부 3% 세액공제(법률 제7328호 부칙 제3조)"),
    2007: (6 * _EOK, "0.8", True, COMPREHENSIVE_TABLE_R1, "0.03",
           "같은 법 제9조②2호(적용비율 80%). 인별 계산, 신고·납부 3% 세액공제"),
    2008: (6 * _EOK, "0.8", True, COMPREHENSIVE_TABLE_R1, "0",
           "법률 제9273호(2008.12.26) 부칙 제3조① — 종전 과세표준 × 80% × 종전 세율. 재산세 "
           "적용비율 50%"),
}
for _year in range(2009, 2019):
    _COMPREHENSIVE[_year] = (6 * _EOK, "0.8", False, COMPREHENSIVE_TABLE_R2, "0",
                             "종합부동산세법(법률 제9273호) 제8조①·제9조①, 시행령 "
                             "제2조의4①(공정시장가액비율 80%). "
                             "재산세 중복분 공제는 당시 고지 서식(시행규칙 제102호 2009.9.23 — "
                             "2016~는 시행령 제26670호 "
                             "제4조의2①과 같은 산식)")
_COMPREHENSIVE[2019] = (6 * _EOK, "0.85", False, COMPREHENSIVE_TABLE_R3, "0",
                        "법률 제16109호(2019.1.1) 제9조①1호, 시행령 제29524호 제2조의4①1호(85%)")
_COMPREHENSIVE[2020] = (6 * _EOK, "0.9", False, COMPREHENSIVE_TABLE_R3, "0",
                        "같은 시행령 제2조의4①2호(90%)")
_COMPREHENSIVE[2021] = (6 * _EOK, "0.95", False, COMPREHENSIVE_TABLE_R4, "0",
                        "법률 제17478호(2021.1.1) 제9조①1호, 시행령 제2조의4①3호(95%), 시행령 "
                        "제31447호 제4조의2①")
_COMPREHENSIVE[2022] = (6 * _EOK, "0.6", False, COMPREHENSIVE_TABLE_R4, "0",
                        "시행령 제32831호(2022.8.2, 그해 납세의무분부터 — 60%). 재산세 비율 "
                        "45%(1세대 1주택)")
for _year in range(2023, 2027):
    _COMPREHENSIVE[_year] = (9 * _EOK, "0.6", False, COMPREHENSIVE_TABLE_R5, "0",
                             "법률 제19200호(2023.1.1) 제8조①3호(9억)·제9조①1호, 시행령 "
                             "제2조의4①(60%)·제4조의3①. "
                             "2026.8.3 세제개편안은 2027년분부터")

COMPREHENSIVE_TAX_YEARS: dict[int, ComprehensiveTaxYear] = {
    year: ComprehensiveTaxYear(year=year, deduction=deduction, ratio=P(ratio), ratio_on_tax=on_tax,
                               table=table, filing_credit=P(credit), rural_rate=P("0.2"),
                               basis=basis)
    for year, (deduction, ratio, on_tax, table, credit, basis) in sorted(_COMPREHENSIVE.items())
}


# ── 양도소득세(010 반복 5 — FR-031, research R10-21) ───────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class YearlyRate:
    """연수에 비례하는 공제율 — `from_years` 이상이면 연수 × `per_year`, `cap`까지."""

    from_years: int
    per_year: Decimal
    cap: Decimal


@dataclass(frozen=True, slots=True)
class TransferRule:
    """주택 양도소득세 — 1세대 1주택 비과세·고가주택·장기보유특별공제·세율·기본공제·지방소득세.

    모델 규약(010 R10-21): 1세대 1주택, 부부 5:5 공동명의(인별 기본공제·세율), 비과세의 거주 요건은
    늘 적용한다(취득 당시 조정대상지역 가정 — 보수적). 일시적 2주택·감면 특례는 넣지 않는다.
    """

    effective_from: dt.date
    effective_to: dt.date | None
    #: 고가주택 기준 양도가액 — 이하이면 비과세, 넘으면 그 초과 비율만 과세.
    exemption_ceiling: int
    exemption_holding_years: int
    exemption_residence_years: int
    #: 2년 이상 보유의 기본세율(과세표준 누진표).
    brackets: tuple[Bracket, ...]
    #: 단기 보유 세율 — (보유 연수 미만, 세율), 짧은 쪽부터.
    short_term: tuple[tuple[int, Decimal], ...]
    #: 장기보유특별공제 — 일반(표1)과 1세대 1주택(표2 — 보유분 + 거주분).
    ltsd_general: YearlyRate
    ltsd_home_holding: YearlyRate
    ltsd_home_residence: YearlyRate
    #: 양도소득 기본공제(인별, 연간).
    basic_deduction: int
    #: 지방소득세 — 양도소득세의 비율.
    local_rate: Decimal
    basis: str


TRANSFER_RULES: tuple[TransferRule, ...] = (
    TransferRule(
        effective_from=dt.date.fromisoformat("2023-01-01"), effective_to=None,
        exemption_ceiling=12 * _EOK, exemption_holding_years=2, exemption_residence_years=2,
        brackets=(
            Bracket(14_000_000, P("0.06"), 0), Bracket(50_000_000, P("0.15"), 1_260_000),
            Bracket(88_000_000, P("0.24"), 5_760_000), Bracket(150_000_000, P("0.35"), 15_440_000),
            Bracket(300_000_000, P("0.38"), 19_940_000),
            Bracket(500_000_000, P("0.40"), 25_940_000),
            Bracket(1_000_000_000, P("0.42"), 35_940_000), Bracket(None, P("0.45"), 65_940_000)),
        short_term=((1, P("0.70")), (2, P("0.60"))),
        ltsd_general=YearlyRate(3, P("0.02"), P("0.30")),
        ltsd_home_holding=YearlyRate(3, P("0.04"), P("0.40")),
        ltsd_home_residence=YearlyRate(2, P("0.04"), P("0.40")),
        basic_deduction=2_500_000, local_rate=P("0.10"),
        basis="소득세법 제89조(1세대 1주택 비과세)·제95조(장기보유특별공제 표1·표2)·"
              "제103조(기본공제)·제104조(세율 — 2023-01-01 이후 양도분 과세표준 구간, 주택 단기 "
              "70%·60%), 고가주택 12억 원(2021-12-08 이후 양도분), 지방세법(양도소득분 지방소득세 "
              "10%). 출처 링크는 010 research R10-21"),
)


# ── 찾기 ────────────────────────────────────────────────────────────────────────────────────

def acquisition_rule(on: dt.date) -> AcquisitionRule:
    for rule in ACQUISITION_RULES:
        if rule.effective_from <= on and (rule.effective_to is None or on <= rule.effective_to):
            return rule
    raise RuleNotCovered("acquisition", on)


def brokerage_rule(on: dt.date) -> BrokerageRule:
    for rule in BROKERAGE_RULES:
        if rule.effective_from <= on and (rule.effective_to is None or on <= rule.effective_to):
            return rule
    raise RuleNotCovered("brokerage", on)


def property_tax_year(year: int) -> PropertyTaxYear:
    try:
        return PROPERTY_TAX_YEARS[year]
    except KeyError:
        raise RuleNotCovered("property", dt.date(year, 6, 1)) from None


def comprehensive_tax_year(year: int) -> ComprehensiveTaxYear:
    try:
        return COMPREHENSIVE_TAX_YEARS[year]
    except KeyError:
        raise RuleNotCovered("comprehensive", dt.date(year, 6, 1)) from None


def transfer_rule(on: dt.date) -> TransferRule:
    """양도일의 주택 양도소득세 규칙. 표 밖이면 `RuleNotCovered`(가까운 규칙으로 대신하지
    않는다)."""
    for rule in TRANSFER_RULES:
        if rule.effective_from <= on and (rule.effective_to is None or on <= rule.effective_to):
            return rule
    raise RuleNotCovered("transfer", on)

