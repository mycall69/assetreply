"""비교 블록의 단가 등락 (013 반복 2026-10-09 T086) — spec FR-011a, data-model 3.2.

`comparison_block`이 `unitPrice`를 싣는다 — 가족마다 `kind`·`basis`·`currency`, 시작일·기준일의
날짜·값· 잠정·추정, 차이·등락률(서버 문자열, 지수 표기 없음), 분할 비율. 넘기지 않으면 `None`이고
기존 칸은 그대로다.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

from src.api.services.comparison_metrics import comparison_block, unit_price_json
from src.simulation.comparison_costs import crypto_costs, deposit_costs, stock_costs
from src.simulation.unit_price import PricePoint, unit_price

P = Decimal
D = dt.date.fromisoformat

SUMMARY: dict[str, object] = {
    "principal": "10000000", "profit": "1000000", "returnRate": "0.100000", "asOf": "2026-10-07",
    "isFinal": True, "totalKrw": "11000000"}
COSTS = stock_costs(buy_fee=P("100"), dividend_tax=P("0"), sale_fee=None, sale_tax=None,
                    tax_kind=None)


class Test블록:
    def test_넘기지_않으면_None이고_기존_칸은_그대로다(self) -> None:
        before = comparison_block("stock_lump", SUMMARY, COSTS)
        assert before["unitPrice"] is None
        assert {k: v for k, v in before.items() if k != "unitPrice"} == {
            k: v for k, v in comparison_block("stock_lump", SUMMARY, COSTS).items()
            if k != "unitPrice"}

    def test_주식_수정주가(self) -> None:
        unit = unit_price("share", "split_restated_close", "KRW",
                          PricePoint(D("2010-01-04"), P("16180.000000")),
                          PricePoint(D("2026-10-07"), P("55000.000000")), split_ratio="50:1")
        block = comparison_block("stock_lump", SUMMARY, COSTS, unit_price=unit)
        assert block["unitPrice"] == {
            "kind": "share", "basis": "split_restated_close", "currency": "KRW",
            "start": {"date": "2010-01-04", "value": "16180.000000", "provisional": False,
                      "estimated": False},
            "asOf": {"date": "2026-10-07", "value": "55000.000000", "provisional": False,
                     "estimated": False, "missing": None},
            "change": "38820.000000", "changeRate": "2.399258", "split": {"ratio": "50:1"}}

    def test_가상자산_시가는_시세_통화다(self) -> None:
        unit = unit_price("coin", "daily_open", "USD", PricePoint(D("2020-01-15"), P("8800.5")),
                          PricePoint(D("2021-12-31"), P("46200")))
        block = comparison_block("crypto_lump", SUMMARY, crypto_costs(buy_fee=P("10")),
                                 unit_price=unit)
        assert block["unitPrice"]["currency"] == "USD"  # type: ignore[index]
        assert block["unitPrice"]["basis"] == "daily_open"  # type: ignore[index]
        assert block["unitPrice"]["split"] is None  # type: ignore[index]

    def test_금리는_currency가_없고_등락률이_null이다(self) -> None:
        unit = unit_price("rate", "published_rate", None, PricePoint(D("2015-01-01"), P("2.10")),
                          PricePoint(D("2026-08-01"), P("2.45"), provisional=True))
        block = comparison_block("deposit", SUMMARY, deposit_costs(matured_taxes=[P("1")],
                                                                   open_tax=P("0")),
                                 unit_price=unit)
        body = block["unitPrice"]
        assert body["currency"] is None and body["changeRate"] is None  # type: ignore[index]
        assert body["change"] == "0.35"  # type: ignore[index]
        assert body["asOf"] == {"date": "2026-08-01", "value": "2.45",  # type: ignore[index]
                                "provisional": True, "estimated": False, "missing": None}

    def test_부동산_시세_없음과_추정(self) -> None:
        unit = unit_price("home", "market_price", "KRW",
                          PricePoint(D("2021-03-01"), P("2100000000"), estimated=True),
                          PricePoint(D("2026-10-01"), None, missing="no_trades"))
        body = unit_price_json(unit)
        assert body is not None
        assert body["start"]["estimated"] is True  # type: ignore[index]
        assert body["asOf"]["value"] is None  # type: ignore[index]
        assert body["asOf"]["missing"] == "no_trades"  # type: ignore[index]
        assert (body["change"], body["changeRate"]) == (None, None)

    def test_지수_표기를_쓰지_않는다(self) -> None:
        unit = unit_price("coin", "daily_open", "USD",
                          PricePoint(D("2021-11-01"), P("0.0000053")),
                          PricePoint(D("2026-10-03"), P("0.0000123")))
        body = unit_price_json(unit)
        assert body is not None
        assert body["start"]["value"] == "0.0000053"  # type: ignore[index]
        assert "E" not in str(body["change"])
