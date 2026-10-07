"""해외 주식 매도 비용의 양도차익 구성 (012 T078) — FR-019, SC-011, research R12-18. 순수 함수 —
DB·HTTP 없음(헌법 원칙 IV).

- `foreign_sale_cost`는 차익을 만든 **원 미만을 버린 값** 셋을 함께 낸다 —
  매도금액(`sale_krw`)·취득가(`acquisition_krw`)·수수료(`fees_krw` = 매수 +
  매도). 그래서 `gain = sale_krw − acquisition_krw − fees_krw`가 정확하다. 따로 버리면 화면의 세
  값이 차익과 1원 어긋난다
- 국내(`domestic_sale_cost`)는 셋 모두 `None`이다(`gain`·`deduction`과 같다)
- 기존 값(`fee`·`tax`·`total`·`gain`)은 바뀌지 않는다
"""

from __future__ import annotations

from decimal import Decimal

from src.simulation.stock_sale_cost import domestic_sale_cost, foreign_sale_cost

M = Decimal


class Test해외:
    def test_구성_값은_원_미만을_버린_값이고_차익과_0원_차이다(self) -> None:
        # 2026-10-07 보고(XLK)의 값 — 소수가 붙은 원화 금액으로 넣는다
        cost = foreign_sale_cost(
            sale_krw=M("539229405.87"),
            sell_fee_krw=M("80884.41"),
            acquisition_krw=M("36181082.90"),
            buy_fees_krw=M("5427.70"),
            rate=M("0.22"),
            deduction=M("2500000"),
        )
        assert (cost.sale_krw, cost.acquisition_krw, cost.fees_krw) == (
            M("539229405"),
            M("36181082"),
            M("86311"),
        )
        assert cost.gain == cost.sale_krw - cost.acquisition_krw - cost.fees_krw == M("502962012")

    def test_기존_값은_그대로다(self) -> None:
        cost = foreign_sale_cost(
            sale_krw=M("539229405.87"),
            sell_fee_krw=M("80884.41"),
            acquisition_krw=M("36181082.90"),
            buy_fees_krw=M("5427.70"),
            rate=M("0.22"),
            deduction=M("2500000"),
        )
        assert (cost.fee, cost.tax, cost.total, cost.deduction) == (
            M("80884"),
            M("110101642"),
            M("110182526"),
            M("2500000"),
        )

    def test_손실이어도_식이_맞고_세금은_0이다(self) -> None:
        cost = foreign_sale_cost(
            sale_krw=M("900000.5"),
            sell_fee_krw=M("135.9"),
            acquisition_krw=M("1000000.4"),
            buy_fees_krw=M("150.2"),
            rate=M("0.22"),
            deduction=M("2500000"),
        )
        assert cost.gain == cost.sale_krw - cost.acquisition_krw - cost.fees_krw == M("-100285")
        assert cost.tax == M("0")


class Test국내:
    def test_구성_값이_없다(self) -> None:
        cost = domestic_sale_cost(M("56304000"), fee_rate=M("0.000150"), tax_rate=M("0.0020"))
        assert (cost.sale_krw, cost.acquisition_krw, cost.fees_krw) == (None, None, None)
