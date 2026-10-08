"""비교 경로의 정규화 블록 — 적립식·정기 적금 (013 T042) — FR-011, FR-015, research R13-4.

적립식 보드(`RecurringBoard`)는 매도 후 값을 주 값으로 보이고, 비면 "—"다 — 보유 중 값으로 물러나지
않는다. 현재 가치는 `totalKrw`, 투자 원금은 총 납입 원금(`contributed` + 원화 `contributedKrw`)이다.
정기 적금은 보유 중 값이고 현재 가치는 평가액(`balance`)이다.
"""

from __future__ import annotations

from decimal import Decimal

from src.api.services.comparison_metrics import comparison_block
from src.simulation.comparison_costs import crypto_costs, deposit_costs, stock_costs

P = Decimal
STOCK = stock_costs(buy_fee=P("145"), dividend_tax=P("0"), sale_fee=P("145"), sale_tax=P("1946"),
                    tax_kind="transaction_tax")


def recurring(**over: object) -> dict[str, object]:
    base: dict[str, object] = {
        "contributed": "3000000", "contributedKrw": "3000000", "contributions": 3,
        "totalKrw": "3149854", "buyFeeTotal": "145", "profit": "149854", "returnRate": "0.049951",
        "profitAfterSale": "147763", "returnRateAfterSale": "0.049254", "asOf": "2026-03-03",
        "isFinal": True, "saleCost": {"fee": "145", "tax": "1946", "total": "2091"}}
    base.update(over)
    return base


class Test적립식:
    def test_매도_후가_주_값이고_원금은_총_납입_원금이다(self) -> None:
        block = comparison_block("stock_recurring", recurring(), STOCK, principal_currency="KRW")
        assert block["mainBasis"] == "after_sale"
        assert (block["profit"], block["returnRate"]) == ("147763", "0.049254")
        assert block["principal"] == {"amount": "3000000", "currency": "KRW", "krw": "3000000"}
        assert block["currentValue"] == "3149854"
        assert block["lineEnd"] == {"date": "2026-03-03", "holdingReturnRate": "0.049951",
                                    "afterSaleReturnRate": "0.049254"}

    def test_외화_원금이면_원화_분모를_함께_싣는다(self) -> None:
        summary = recurring(contributed="2000", contributedKrw="2890400")
        block = comparison_block("stock_recurring", summary, STOCK, principal_currency="USD")
        assert block["principal"] == {"amount": "2000", "currency": "USD", "krw": "2890400"}

    def test_매도_후_값이_비면_값이_없다_보유_중으로_물러나지_않는다(self) -> None:
        summary = recurring(profitAfterSale=None, returnRateAfterSale=None)
        costs = crypto_costs(buy_fee=P("1"), sale_fee=P("1"), sale_tax=None,
                             tax_kind="outside_rules")
        block = comparison_block("crypto_recurring", summary, costs, principal_currency="KRW")
        assert block["mainBasis"] == "unavailable"
        assert (block["profit"], block["returnRate"]) == (None, None)
        assert block["holding"] == {"profit": "149854", "returnRate": "0.049951"}
        assert block["lineEnd"]["afterSaleReturnRate"] is None  # type: ignore[index]


class Test정기_적금:
    SUMMARY = {"contributed": "36000000", "installments": 36, "taxTotal": "147654",
               "balance": "37000000", "profit": "1000000", "returnRate": "0.027778",
               "asOf": "2018-01-15", "isFinal": True, "provisionalFrom": None}

    def test_보유_중이고_현재_가치는_평가액이다(self) -> None:
        block = comparison_block("installment", dict(self.SUMMARY),
                                 deposit_costs(matured_taxes=[P("147654")], open_tax=P("0")))
        assert block["mainBasis"] == "holding"
        assert block["currentValue"] == "37000000"
        assert block["principal"] == {"amount": "36000000", "currency": "KRW", "krw": "36000000"}
        assert block["lineEnd"]["afterSaleReturnRate"] is None  # type: ignore[index]

    def test_미발표_달이면_잠정이다(self) -> None:
        summary = {**self.SUMMARY, "provisionalFrom": "2017-12-15"}
        block = comparison_block("installment", summary,
                                 deposit_costs(matured_taxes=[], open_tax=P("0")))
        assert block["provisional"] == ["unpublished_rate"]
