"""비교 표의 비용 몫 — 일시금·정기예금·부동산 (013 T008) — FR-011, SC-001, research R13-3,
data-model 3.1.

비용은 **기간 전체 비용**이다(명확화 4). 이미 반영된 몫(현재 가치·투자 원금에 이미 든 것)과 기준일
매도 가정 몫으로 나눈다. 원화 환산은 주식 적립식의 `buyFeeTotal`과 같은 규칙이다 — 국내는 합의 원
미만 버림, 해외는 (금액 × 그 행의 매매기준율) 합의 원 미만 버림.

메뉴가 비우는 몫은 `None`이고 합도 `None`이다 — 0으로 메우지 않는다(원칙 V).
"""

from __future__ import annotations

import ast
import pathlib
from decimal import Decimal

from src.simulation.comparison_costs import (
    CostItem,
    CostPart,
    Costs,
    crypto_costs,
    deposit_costs,
    krw_sum,
    realestate_costs,
    stock_costs,
)

P = Decimal


class Test원화_환산:
    def test_국내는_합의_원_미만_버림(self) -> None:
        amounts = [(P("1500.4"), None), (P("12.3"), None), (P("0.4"), None)]
        assert krw_sum(amounts, domestic=True) == P("1513")

    def test_해외는_행마다_환율을_곱한_합의_원_미만_버림(self) -> None:
        amounts = [(P("1.5"), P("1150")), (P("0.25"), P("1170.5"))]
        # 1725 + 292.625 = 2017.625 → 2017
        assert krw_sum(amounts, domestic=False) == P("2017")

    def test_해외에서_환율이_없는_행은_빼고_금액이_없는_행도_뺀다(self) -> None:
        amounts = [(P("1"), P("1200")), (P("9"), None), (None, P("1300"))]
        assert krw_sum(amounts, domestic=False) == P("1200")

    def test_빈_목록은_0이다(self) -> None:
        assert krw_sum([], domestic=True) == 0


class Test몫과_합:
    def test_몫의_합은_항목의_합이다(self) -> None:
        part = CostPart((CostItem("buy_fee", P("10")), CostItem("dividend_tax", P("5"))))
        assert part.total == P("15")

    def test_항목_하나가_None이면_몫의_합도_None이다(self) -> None:
        part = CostPart((CostItem("sale_fee", P("10")), CostItem("crypto_tax", None)))
        assert part.total is None

    def test_전체_합은_두_몫의_합이다(self) -> None:
        costs = Costs(CostPart((CostItem("buy_fee", P("10")),)),
                      CostPart((CostItem("sale_fee", P("7")),)))
        assert costs.total == P("17")

    def test_매도_몫이_없으면_전체_합은_반영된_몫이다(self) -> None:
        assert Costs(CostPart((CostItem("buy_fee", P("10")),))).total == P("10")

    def test_매도_몫의_합이_None이면_전체도_None이다(self) -> None:
        costs = Costs(CostPart((CostItem("buy_fee", P("10")),)),
                      CostPart((CostItem("crypto_tax", None),)), blank="outside_rules")
        assert costs.total is None


class Test주식_일시금:
    def test_국내는_수수료_배당세가_반영_몫이고_매도_수수료_거래세가_매도_몫이다(self) -> None:
        costs = stock_costs(buy_fee=P("1200"), dividend_tax=P("3400"), sale_fee=P("150"),
                            sale_tax=P("2000"), tax_kind="transaction_tax")
        assert costs.reflected.items == (CostItem("buy_fee", P("1200")),
                                         CostItem("dividend_tax", P("3400")))
        assert costs.sale is not None
        assert costs.sale.items == (CostItem("sale_fee", P("150")),
                                    CostItem("transaction_tax", P("2000")))
        assert costs.total == P("6750")
        assert costs.blank is None

    def test_해외는_양도소득세다(self) -> None:
        costs = stock_costs(buy_fee=P("5427"), dividend_tax=P("2843017"), sale_fee=P("80884"),
                            sale_tax=P("110101642"), tax_kind="capital_gains_tax")
        assert costs.sale is not None
        assert [i.kind for i in costs.sale.items] == ["sale_fee", "capital_gains_tax"]
        # 2026-10-07 XLK 보고의 값 — 매수 + 매도 수수료가 saleCost.feesKrw(86,311)다.
        assert costs.reflected.items[0].amount + costs.sale.items[0].amount == P("86311")

    def test_매도_비용이_없으면_매도_몫이_없다(self) -> None:
        costs = stock_costs(buy_fee=P("1"), dividend_tax=P("0"), sale_fee=None, sale_tax=None,
                            tax_kind=None)
        assert costs.sale is None
        assert costs.total == P("1")

    def test_세금을_모르면_비우고_까닭을_남긴다(self) -> None:
        costs = stock_costs(buy_fee=P("1"), dividend_tax=P("0"), sale_fee=P("2"), sale_tax=None,
                            tax_kind="outside_table")
        assert costs.sale is not None and costs.sale.total is None
        assert costs.total is None and costs.blank == "outside_table"


class Test가상자산_일시금:
    def test_매수_수수료뿐이고_매도_몫이_없다(self) -> None:
        costs = crypto_costs(buy_fee=P("4567"))
        assert costs.reflected.items == (CostItem("buy_fee", P("4567")),)
        assert costs.sale is None
        assert costs.total == P("4567")


class Test정기예금:
    def test_끝난_회차와_진행_중_회차의_이자_소득세다(self) -> None:
        costs = deposit_costs(matured_taxes=[P("15142"), P("24995")], open_tax=P("35259"))
        assert costs.reflected.items == (CostItem("interest_tax_matured", P("40137")),
                                         CostItem("interest_tax_open", P("35259")))
        assert costs.sale is None
        assert costs.total == P("75396")


class Test부동산:
    def test_취득_보유_매도_항목이다(self) -> None:
        costs = realestate_costs(
            acquisition_tax=P("10000000"), education_tax=P("1000000"), rural_tax=P("0"),
            brokerage_buy=P("4000000"), property_tax=P("3000000"),
            comprehensive_tax=P("500000"), sale_brokerage=P("4400000"),
            income_tax=P("20000000"), local_tax=P("2000000"), sale_kind="taxed")
        acquisition = [i for i in costs.reflected.items if i.in_principal]
        assert [i.kind for i in acquisition] == ["acquisition_tax", "education_tax", "rural_tax",
                                                 "brokerage_buy"]
        assert sum((i.amount or P(0) for i in acquisition), P(0)) == P("15000000")
        holding = [i for i in costs.reflected.items if not i.in_principal]
        assert [i.kind for i in holding] == ["property_tax", "comprehensive_tax"]
        assert costs.sale is not None
        assert [i.kind for i in costs.sale.items] == ["brokerage_sale", "transfer_income_tax",
                                                      "transfer_local_tax"]
        assert costs.sale.total == P("26400000")
        assert costs.total == P("44900000")

    def test_매도비용이_없으면_매도_몫이_없다(self) -> None:
        costs = realestate_costs(
            acquisition_tax=P("1"), education_tax=P("0"), rural_tax=P("0"), brokerage_buy=P("0"),
            property_tax=P("0"), comprehensive_tax=P("0"), sale_brokerage=None, income_tax=None,
            local_tax=None, sale_kind=None)
        assert costs.sale is None and costs.total == P("1")

    def test_세법_표_밖이면_세금을_비우고_까닭을_남긴다(self) -> None:
        costs = realestate_costs(
            acquisition_tax=P("1"), education_tax=P("0"), rural_tax=P("0"), brokerage_buy=P("0"),
            property_tax=P("0"), comprehensive_tax=P("0"), sale_brokerage=P("5"),
            income_tax=None, local_tax=None, sale_kind="outside_table")
        assert costs.sale is not None and costs.sale.total is None
        assert costs.total is None and costs.blank == "outside_table"


class Test계층:
    def test_api_저장소_db를_부르지_않는다(self) -> None:
        source = pathlib.Path("src/simulation/comparison_costs.py").read_text(encoding="utf-8")
        imported = {
            node.module for node in ast.walk(ast.parse(source))
            if isinstance(node, ast.ImportFrom) and node.module}
        assert not any(m.startswith(("src.api", "src.repository", "src.db")) for m in imported)
