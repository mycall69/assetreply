"""비교 블록의 현재 가치 선 (014 반복 2026-10-11b T182) — spec FR-036, SC-021,
contracts/rest-api.md A12, data-model 14.

`value_points`는 시계열 점마다 하나씩 값을 고른다 — 날짜 글자 → 금액 글자(`totals`)가 있으면
그것(주식·가상자산 일시금 — 예수금을 더한 원화 총자산), 없으면 점 `balance`(적립식·예금·적금·
부동산). 계산하지 않고 고른다. 금액은 지수 표기 없이 낸다. `comparison_block`은 받은 점으로
`valueLine`을 싣고, 매도 후 기준이면 `afterSaleValue` = 원화 원금 + 매도 후 투자 수익이다. 다른
칸(`lineEnd` 포함)은 그대로다.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from src.api.services.comparison_metrics import comparison_block, value_points
from src.simulation.comparison_costs import crypto_costs, deposit_costs, stock_costs

P = Decimal

SERIES = {"points": [
    {"date": "2026-01-02", "balance": "9940000", "returnRate": "-0.000542"},
    {"date": "2026-02-02", "balance": "10650000", "returnRate": "0.070458"},
    {"date": "2026-10-06", "balance": "12000000", "returnRate": "0.205458"},
]}

STOCK_SALE = stock_costs(buy_fee=P("1491"), dividend_tax=P("0"), sale_fee=P("1800"),
                         sale_tax=P("24000"), tax_kind="transaction_tax")


def stock_summary(**over: object) -> dict[str, object]:
    base: dict[str, object] = {
        "principal": "10000000", "profit": "2054580", "returnRate": "0.205458",
        "asOf": "2026-10-06", "isFinal": True, "totalKrw": "12054580",
        "saleCost": {"fee": "1800", "tax": "24000", "total": "25800"},
        "profitAfterSale": "2028780", "returnRateAfterSale": "0.202878"}
    base.update(over)
    return base


class Test점_고르기:
    def test_합계가_있으면_그_날의_합계다(self) -> None:
        totals = {"2026-01-02": "9994509", "2026-02-02": "10704580", "2026-10-06": "12054580"}
        assert value_points(SERIES, totals) == [
            {"date": "2026-01-02", "value": "9994509"},
            {"date": "2026-02-02", "value": "10704580"},
            {"date": "2026-10-06", "value": "12054580"},
        ]

    def test_합계가_없으면_점_잔고다(self) -> None:
        assert value_points(SERIES) == [
            {"date": p["date"], "value": p["balance"]} for p in SERIES["points"]]

    def test_차례와_날짜가_점과_같다(self) -> None:
        reversed_totals = {"2026-10-06": "3", "2026-02-02": "2", "2026-01-02": "1"}
        assert [v["date"] for v in value_points(SERIES, reversed_totals)] == [
            "2026-01-02", "2026-02-02", "2026-10-06"]

    def test_지수_표기를_쓰지_않는다(self) -> None:
        series = {"points": [{"date": "2026-01-02", "balance": "0E-12", "returnRate": "0"},
                             {"date": "2026-01-03", "balance": "1.2E+7", "returnRate": "0"}]}
        assert value_points(series) == [{"date": "2026-01-02", "value": "0"},
                                        {"date": "2026-01-03", "value": "12000000"}]

    def test_합계에_없는_날은_지어내지_않는다(self) -> None:
        with pytest.raises(KeyError):
            value_points(SERIES, {"2026-01-02": "1"})


class Test블록:
    def test_매도_후_기준이면_매도_후_금액이_있다(self) -> None:
        line = value_points(SERIES)
        block = comparison_block("stock_lump", stock_summary(), STOCK_SALE,
                                 principal_currency="KRW", value_points=line)
        assert block["mainBasis"] == "after_sale"
        assert block["valueLine"] == {"points": line, "afterSaleValue": "12028780"}
        assert block["lineEnd"] == {"date": "2026-10-06", "holdingReturnRate": "0.205458",
                                    "afterSaleReturnRate": "0.202878"}

    def test_해외_원금은_원화_원금으로_더한다(self) -> None:
        summary = stock_summary(principal="10000", principalKrw="11500000", totalKrw="13554580",
                                profit="2054580", profitAfterSale="2028780")
        block = comparison_block("stock_lump", summary, STOCK_SALE, principal_currency="USD",
                                 value_points=value_points(SERIES))
        assert block["valueLine"]["afterSaleValue"] == "13528780"  # type: ignore[index]

    def test_보유_중_기준이면_매도_후_금액이_없다(self) -> None:
        summary = {"principal": "10000000", "profit": "500000", "returnRate": "0.050000",
                   "asOf": "2026-10-06", "isFinal": True, "totalKrw": "10500000"}
        block = comparison_block("crypto_lump", summary, crypto_costs(buy_fee=P("5000")),
                                 principal_currency="KRW", value_points=value_points(SERIES))
        assert block["mainBasis"] == "holding"
        assert block["valueLine"]["afterSaleValue"] is None  # type: ignore[index]
        assert block["lineEnd"]["afterSaleReturnRate"] is None  # type: ignore[index]

    def test_정기예금도_보유_중이다(self) -> None:
        summary = {"principal": "10000000", "profit": "1234567", "returnRate": "0.123457",
                   "asOf": "2026-10-06", "isFinal": True}
        block = comparison_block("deposit", summary,
                                 deposit_costs(matured_taxes=[P("10000")], open_tax=P("0")),
                                 value_points=value_points(SERIES))
        assert block["valueLine"]["afterSaleValue"] is None  # type: ignore[index]

    def test_점을_넘기지_않으면_키가_없다(self) -> None:
        block = comparison_block("stock_lump", stock_summary(), STOCK_SALE,
                                 principal_currency="KRW")
        assert "valueLine" not in block
