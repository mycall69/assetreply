"""주식 매도 수수료·세금 (010 반복 4 T069 → 011 T009) — 010 FR-030, 011 FR-013·FR-037, research
R11-7. 순수 함수 — DB·HTTP 없음(헌법 원칙 IV).

기준일에 보유 주식을 모두 판다고 가정한 비용이다.

- 국내(KRX): 수수료 = 매도금액 × 매매 수수료율, 매도 세금 = 매도금액 × **설정의 국내 매도 세율**
- 해외: 양도소득세 = max(0, 원화 양도차익 − **설정의 기본공제**) × **설정의 세율**, 양도차익 = 원화
  매도금액 − 원화 취득가 − 매수·매도 수수료
- 원화 금액은 원 미만을 버린다

**011(사용자 승인 2026-10-06, A1)**: 010 반복 4의 시행일별 법령 표(`transaction_tax_rate`·표 밖은
세금을 비움)를 설정값이 대체했다 (명확화 — 모든 기준일에 설정값 하나). 그래서 표 검사 셋(시행일
세율, 국내·해외 표 밖)을 빼고 세율·공제를 인자로 받는 검사로 바꿨다. 원 미만 버림·공제 이하·손실의
기대값은 010 그대로다.
"""

from __future__ import annotations

from decimal import Decimal

from src.simulation.stock_sale_cost import domestic_sale_cost, foreign_sale_cost

M = Decimal


class Test국내:
    def test_수수료와_매도_세금은_원_미만을_버린다(self) -> None:
        cost = domestic_sale_cost(M("56304000"), fee_rate=M("0.000150"), tax_rate=M("0.0020"))
        # 56,304,000 × 0.015% = 8,445.6 → 8,445, × 0.20% = 112,608
        assert (cost.fee, cost.tax, cost.total) == (M("8445"), M("112608"), M("121053"))
        assert (cost.tax_kind, cost.tax_rate, cost.gain, cost.deduction) == (
            "transaction_tax",
            M("0.0020"),
            None,
            None,
        )

    def test_매도금액에_소수가_있어도_원화_금액은_정수다(self) -> None:
        cost = domestic_sale_cost(M("1234567.89"), fee_rate=M("0.000150"), tax_rate=M("0.0015"))
        assert (cost.fee, cost.tax) == (M("185"), M("1851"))  # 185.18…, 1,851.85…

    def test_세율은_넘긴_값_그대로_쓴다(self) -> None:
        # 설정이 0.18%면 기준일과 관계없이 0.18% — 56,304,000 × 0.18% = 101,347.2 → 101,347
        cost = domestic_sale_cost(M("56304000"), fee_rate=M("0.000150"), tax_rate=M("0.001800"))
        assert (cost.tax, cost.tax_rate, cost.total) == (M("101347"), M("0.001800"), M("109792"))

    def test_세율_0이면_세금이_0이고_비지_않는다(self) -> None:
        cost = domestic_sale_cost(M("56304000"), fee_rate=M("0.000150"), tax_rate=M("0"))
        assert (cost.tax, cost.total) == (M("0"), M("8445"))


class Test해외:
    def test_공제를_넘는_차익의_22퍼센트다(self) -> None:
        cost = foreign_sale_cost(
            sale_krw=M("53289965"),
            sell_fee_krw=M("7993.49"),
            acquisition_krw=M("10000000"),
            buy_fees_krw=M("1500.3"),
            rate=M("0.22"),
            deduction=M("2500000"),
        )
        # 원화 금액마다 원 미만을 먼저 버린다 — 차익 = 53,289,965 − 10,000,000 − 1,500 − 7,993 =
        # 43,280,472 세금 = (43,280,472 − 2,500,000) × 22% = 8,971,703.84 → 8,971,703
        assert (cost.gain, cost.deduction, cost.tax_rate) == (
            M("43280472"),
            M("2500000"),
            M("0.22"),
        )
        assert (cost.fee, cost.tax, cost.total) == (M("7993"), M("8971703"), M("8979696"))
        assert cost.tax_kind == "capital_gains_tax"

    def test_차익이_공제_이하면_세금이_없다(self) -> None:
        cost = foreign_sale_cost(
            sale_krw=M("12000000"),
            sell_fee_krw=M("1800"),
            acquisition_krw=M("10000000"),
            buy_fees_krw=M("1500"),
            rate=M("0.22"),
            deduction=M("2500000"),
        )
        assert (cost.gain, cost.tax, cost.total) == (M("1996700"), M("0"), M("1800"))

    def test_손실이면_세금이_없다(self) -> None:
        cost = foreign_sale_cost(
            sale_krw=M("8000000"),
            sell_fee_krw=M("1200"),
            acquisition_krw=M("10000000"),
            buy_fees_krw=M("1500"),
            rate=M("0.22"),
            deduction=M("2500000"),
        )
        assert (cost.gain, cost.tax, cost.total) == (M("-2002700"), M("0"), M("1200"))

    def test_공제_0이면_차익_전부에_세율이다(self) -> None:
        cost = foreign_sale_cost(
            sale_krw=M("12000000"),
            sell_fee_krw=M("1800"),
            acquisition_krw=M("10000000"),
            buy_fees_krw=M("1500"),
            rate=M("0.22"),
            deduction=M("0"),
        )
        # 1,996,700 × 22% = 439,274
        assert (cost.gain, cost.deduction, cost.tax, cost.total) == (
            M("1996700"), M("0"), M("439274"), M("441074"))

    def test_세율과_공제는_넘긴_값_그대로_쓴다(self) -> None:
        cost = foreign_sale_cost(
            sale_krw=M("53289965"),
            sell_fee_krw=M("7993"),
            acquisition_krw=M("10000000"),
            buy_fees_krw=M("1500"),
            rate=M("0.200000"),
            deduction=M("1000000"),
        )
        # (43,280,472 − 1,000,000) × 20% = 8,456,094.4 → 8,456,094
        assert (cost.tax, cost.tax_rate, cost.deduction) == (M("8456094"), M("0.200000"),
                                                              M("1000000"))
        assert cost.total is not None
