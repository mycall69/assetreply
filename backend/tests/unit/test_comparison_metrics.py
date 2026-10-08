"""비교 경로의 정규화 블록 — 일시금·정기예금·부동산 (013 T009) — FR-011, FR-015, SC-001, SC-005,
research R13-4·R13-5, data-model 3.

메뉴 요약(JSON 문자열)과 비용 몫에서 표의 칸을 만든다. 주 값(투자 수익·수익률)은 **각 메뉴 보드의
규칙 그대로**다 — 주식 일시금·부동산은 매도 후 값이 있으면 그것, 없으면 보유 중(`PerformanceBoard`·
`RealEstateBoard`), 가상자산 일시금·정기예금은 보유 중.
"""

from __future__ import annotations

import ast
import datetime as dt
import pathlib
from decimal import Decimal

from src.api.services.comparison_metrics import FxInfo, comparison_block
from src.simulation.comparison_costs import (
    crypto_costs,
    deposit_costs,
    realestate_costs,
    stock_costs,
)

P = Decimal
D = dt.date.fromisoformat

STOCK_SALE = stock_costs(buy_fee=P("5427"), dividend_tax=P("2843017"), sale_fee=P("80884"),
                         sale_tax=P("110101642"), tax_kind="capital_gains_tax")


def stock_summary(**over: object) -> dict[str, object]:
    base: dict[str, object] = {
        "principal": "20000000", "profit": "519297203", "returnRate": "25.964860",
        "asOf": "2026-10-06", "isFinal": True, "totalKrw": "539297203",
        "saleCost": {"fee": "80884", "tax": "110101642", "total": "110182526"},
        "profitAfterSale": "409114677", "returnRateAfterSale": "20.455734"}
    base.update(over)
    return base


class Test주식_일시금:
    def test_매도_후_값이_주_값이다(self) -> None:
        block = comparison_block("stock_lump", stock_summary(), STOCK_SALE,
                                 principal_currency="KRW")
        assert block["mainBasis"] == "after_sale"
        assert (block["profit"], block["returnRate"]) == ("409114677", "20.455734")
        assert block["holding"] == {"profit": "519297203", "returnRate": "25.964860"}
        assert block["currentValue"] == "539297203"
        assert block["principal"] == {"amount": "20000000", "currency": "KRW", "krw": "20000000"}
        assert block["lineEnd"] == {"date": "2026-10-06", "holdingReturnRate": "25.964860",
                                    "afterSaleReturnRate": "20.455734"}
        assert (block["asOf"], block["isFinal"], block["provisional"]) == ("2026-10-06", True, [])

    def test_매도_후_값이_없으면_보유_중으로_물러난다(self) -> None:
        summary = stock_summary(profitAfterSale=None, returnRateAfterSale=None)
        block = comparison_block("stock_lump", summary, STOCK_SALE, principal_currency="KRW")
        assert block["mainBasis"] == "holding"
        assert (block["profit"], block["returnRate"]) == ("519297203", "25.964860")
        assert block["lineEnd"]["afterSaleReturnRate"] is None  # type: ignore[index]

    def test_매도_비용이_없으면_보유_중이다(self) -> None:
        summary = stock_summary()
        del summary["saleCost"]
        block = comparison_block("stock_lump", summary, STOCK_SALE, principal_currency="KRW")
        assert block["mainBasis"] == "holding"

    def test_외화_원금이면_원금에_원화를_함께_싣는다(self) -> None:
        summary = stock_summary(principal="10000", principalKrw="13581000")
        block = comparison_block("stock_lump", summary, STOCK_SALE, principal_currency="USD")
        assert block["principal"] == {"amount": "10000", "currency": "USD", "krw": "13581000"}

    def test_확정_전이면_잠정_까닭이_있다(self) -> None:
        block = comparison_block("stock_lump", stock_summary(isFinal=False), STOCK_SALE,
                                 principal_currency="KRW")
        assert block["provisional"] == ["not_final"]

    def test_외화_대상은_평가_환율과_출처를_싣는다(self) -> None:
        exchange = {"rate": "1158.1", "rateDate": "2010-02-11", "kind": "cash_buy_discounted",
                    "spreadDiscount": "0.9"}
        fx = FxInfo(currency="USD", valuation_rate=P("1358.500000"),
                    valuation_rate_date=D("2026-10-06"), exchange=exchange)
        block = comparison_block("stock_lump", stock_summary(), STOCK_SALE,
                                 principal_currency="KRW", fx=fx)
        assert block["fx"] == {"currency": "USD", "valuationRate": "1358.500000",
                               "valuationRateDate": "2026-10-06", "source": "ECOS:731Y001",
                               "exchange": exchange}

    def test_원화_대상은_환율이_없다(self) -> None:
        block = comparison_block("stock_lump", stock_summary(), STOCK_SALE,
                                 principal_currency="KRW")
        assert block["fx"] is None

    def test_비용_몫을_싣는다(self) -> None:
        block = comparison_block("stock_lump", stock_summary(), STOCK_SALE,
                                 principal_currency="KRW")
        assert block["costs"] == {
            "total": "113030970",
            "reflected": {"total": "2848444", "items": [
                {"kind": "buy_fee", "amount": "5427", "inPrincipal": False},
                {"kind": "dividend_tax", "amount": "2843017", "inPrincipal": False}]},
            "sale": {"total": "110182526", "blank": None, "items": [
                {"kind": "sale_fee", "amount": "80884", "inPrincipal": False},
                {"kind": "capital_gains_tax", "amount": "110101642", "inPrincipal": False}]}}

    def test_지수_표기가_없다(self) -> None:
        summary = stock_summary(profit="0E-12", returnRate="0E-6")
        block = comparison_block("stock_lump", summary, STOCK_SALE, principal_currency="KRW")
        assert block["holding"] == {"profit": "0", "returnRate": "0"}


class Test가상자산_일시금:
    def test_보유_중_값이고_매도_후_점이_없다(self) -> None:
        summary = {"principal": "10000000", "profit": "2500000", "returnRate": "0.250000",
                   "asOf": "2026-10-07", "isFinal": True, "totalKrw": "12500000",
                   "boughtOn": "2020-01-01"}
        block = comparison_block("crypto_lump", summary, crypto_costs(buy_fee=P("5000")),
                                 principal_currency="KRW")
        assert block["mainBasis"] == "holding"
        assert (block["profit"], block["returnRate"]) == ("2500000", "0.250000")
        assert block["currentValue"] == "12500000"
        assert block["lineEnd"]["afterSaleReturnRate"] is None  # type: ignore[index]
        assert block["costs"]["sale"] is None  # type: ignore[index]


class Test정기예금:
    SUMMARY = {"principal": "10000000", "profit": "1557207", "returnRate": "0.155721",
               "asOf": "2026-10-04", "isFinal": True, "provisionalFrom": None}

    def test_보유_중이고_현재_가치는_원금_더하기_수익이다(self) -> None:
        block = comparison_block("deposit", dict(self.SUMMARY),
                                 deposit_costs(matured_taxes=[P("1")], open_tax=P("2")))
        assert block["mainBasis"] == "holding"
        assert block["currentValue"] == "11557207"
        assert block["principal"] == {"amount": "10000000", "currency": "KRW", "krw": "10000000"}
        assert block["provisional"] == []

    def test_미발표_달이면_잠정이다(self) -> None:
        summary = {**self.SUMMARY, "provisionalFrom": "2026-09-15"}
        block = comparison_block("deposit", summary,
                                 deposit_costs(matured_taxes=[], open_tax=P("0")))
        assert block["provisional"] == ["unpublished_rate"]


class Test부동산:
    COSTS = realestate_costs(
        acquisition_tax=P("10"), education_tax=P("1"), rural_tax=P("0"), brokerage_buy=P("4"),
        property_tax=P("3"), comprehensive_tax=P("0"), sale_brokerage=P("5"), income_tax=P("2"),
        local_tax=P("1"), sale_kind="taxed")

    def summary(self, **over: object) -> dict[str, object]:
        base: dict[str, object] = {
            "buyPrice": "1500000000", "invested": "1560000000", "value": "2100000000",
            "profit": "500000000", "returnRate": "0.320513", "asOf": "2026-10-08",
            "estimated": False, "provisional": False,
            "saleCost": {"total": "8"}, "profitAfterSale": "450000000",
            "returnRateAfterSale": "0.288462"}
        base.update(over)
        return base

    def test_매도_후가_주_값이고_원금은_투입_금액이다(self) -> None:
        block = comparison_block("realestate", self.summary(), self.COSTS)
        assert block["mainBasis"] == "after_sale"
        assert (block["profit"], block["returnRate"]) == ("450000000", "0.288462")
        assert block["principal"] == {"amount": "1560000000", "currency": "KRW",
                                      "krw": "1560000000"}
        assert block["currentValue"] == "2100000000"

    def test_매도_후_값이_없으면_보유_중으로_물러난다(self) -> None:
        summary = self.summary(profitAfterSale=None, returnRateAfterSale=None)
        block = comparison_block("realestate", summary, self.COSTS)
        assert block["mainBasis"] == "holding"
        assert block["profit"] == "500000000"

    def test_시세가_없으면_값이_없다(self) -> None:
        summary = self.summary(value=None, profit=None, returnRate=None)
        del summary["saleCost"]
        summary["profitAfterSale"] = None
        summary["returnRateAfterSale"] = None
        block = comparison_block("realestate", summary, self.COSTS)
        assert block["mainBasis"] == "unavailable"
        assert (block["profit"], block["returnRate"], block["currentValue"]) == (None, None, None)

    def test_잠정_추정_시세면_잠정_까닭이_있다(self) -> None:
        block = comparison_block("realestate", self.summary(provisional=True, estimated=True),
                                 self.COSTS)
        assert block["provisional"] == ["provisional_price", "estimated_price"]

    def test_취득_비용_항목은_원금에_포함이다(self) -> None:
        block = comparison_block("realestate", self.summary(), self.COSTS)
        items = block["costs"]["reflected"]["items"]  # type: ignore[index]
        assert [i["inPrincipal"] for i in items] == [True, True, True, True, False, False]


class Test계층:
    def test_db_저장소_경로를_부르지_않는다(self) -> None:
        source = pathlib.Path("src/api/services/comparison_metrics.py").read_text(
            encoding="utf-8")
        imported = {
            node.module for node in ast.walk(ast.parse(source))
            if isinstance(node, ast.ImportFrom) and node.module}
        assert not any(m.startswith(("src.repository", "src.db", "src.api.routes"))
                       for m in imported)
        assert "sqlalchemy" not in source
