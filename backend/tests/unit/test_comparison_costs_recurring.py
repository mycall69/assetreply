"""비교 표의 비용 몫 — 적립식·정기 적금 (013 T041) — FR-011, SC-001, research R13-3.

적립식은 보드가 이미 합계를 낸다 — 반영 몫은 `buyFeeTotal`(주식은 `dividendTaxTotal`도), 매도 가정
몫은 `saleCost`의 수수료·세금이다. 가상자산 적립식의 세금은 과세 시행일(2027-01-01) 전 기준일이면 0,
그 뒤면 **비운다** (0으로 메우지 않는다 — 011 FR-020). 정기 적금은 만기 세금(`taxTotal` — 메뉴 칸)과
진행 중 계약의 경과 세금이다.
"""

from __future__ import annotations

from decimal import Decimal

from src.simulation.comparison_costs import CostItem, crypto_costs, deposit_costs, stock_costs

P = Decimal


class Test주식_적립식:
    def test_보드의_합계가_두_몫이다(self) -> None:
        costs = stock_costs(buy_fee=P("145"), dividend_tax=P("0"), sale_fee=P("145"),
                            sale_tax=P("1946"), tax_kind="transaction_tax")
        assert costs.reflected.items == (CostItem("buy_fee", P("145")),
                                         CostItem("dividend_tax", P("0")))
        assert costs.sale is not None and costs.sale.total == P("2091")
        assert costs.total == P("2236")


class Test가상자산_적립식:
    def test_과세_시행일_전이면_세금이_0이다(self) -> None:
        costs = crypto_costs(buy_fee=P("1200"), sale_fee=P("300"), sale_tax=P("0"),
                             tax_kind="not_yet_taxed")
        assert costs.sale is not None
        assert costs.sale.items == (CostItem("sale_fee", P("300")), CostItem("crypto_tax", P("0")))
        assert (costs.blank, costs.total) == (None, P("1500"))

    def test_과세_시행일_뒤면_세금과_합을_비운다(self) -> None:
        costs = crypto_costs(buy_fee=P("1200"), sale_fee=P("300"), sale_tax=None,
                             tax_kind="outside_rules")
        assert costs.sale is not None
        assert costs.sale.items[1] == CostItem("crypto_tax", None)
        assert (costs.sale.total, costs.total, costs.blank) == (None, None, "outside_rules")
        assert costs.reflected.total == P("1200")


class Test정기_적금:
    def test_만기_세금과_경과_세금이다(self) -> None:
        costs = deposit_costs(matured_taxes=[P("147654")], open_tax=P("18906"))
        assert costs.reflected.items == (CostItem("interest_tax_matured", P("147654")),
                                         CostItem("interest_tax_open", P("18906")))
        assert costs.sale is None and costs.total == P("166560")
