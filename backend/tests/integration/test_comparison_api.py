"""비교 경로의 `comparison` 블록과 메뉴 값의 짝 (013 T011) — FR-011, SC-001, data-model 3.

비교 표의 칸은 메뉴가 낸 값에서 나온다. 비용은 기간 전체 비용이고(명확화 4), 매도 가정 몫은 메뉴
보드의 매도 비용과 같으며, 해외 주식의 매수 + 매도 수수료는 `saleCost.feesKrw`(012 US6)와 같다.
"""

from __future__ import annotations

import datetime as dt
from decimal import ROUND_FLOOR, Decimal

import pytest

from tests.integration.comparison_support import AAPL_KRW, AAPL_USD, KRX, http, seed_stocks
from tests.integration.crypto_support import add_coin, seed_daily, seed_usd
from tests.integration.deposit_support import TODAY, seed_rates
from tests.integration.test_comparison_identity import Api, apt  # noqa: F401 — 픽스처

D = dt.date.fromisoformat
P = Decimal


def items(part: dict) -> dict[str, str | None]:  # type: ignore[type-arg]
    return {i["kind"]: i["amount"] for i in part["items"]}


async def pair(client, menu: str, params: dict[str, str]) -> tuple[dict, dict]:  # type: ignore[no-untyped-def,type-arg]
    # 월 단위 표 — 사건 행(매수·배당락·재투자)은 단위와 무관하게 남는다(012).
    table = await client.get(menu, params={**params, "limit": "200", "period": "monthly"})
    compare = await client.get(f"/api/comparison{menu.removeprefix('/api')}", params=params)
    assert table.status_code == 200 and compare.status_code == 200, compare.text
    return table.json(), compare.json()


class Test주식_일시금:
    async def test_국내는_매도_몫이_보드의_매도_비용이다(self, session_factory) -> None:
        await seed_stocks(session_factory)
        async with http(session_factory) as client:
            menu, body = await pair(client, "/api/stocks/simulation", KRX)
        block, summary = body["comparison"], menu["summary"]
        sale = summary["saleCost"]
        assert block["costs"]["sale"]["total"] == sale["total"]
        assert items(block["costs"]["sale"]) == {"sale_fee": sale["fee"],
                                                 "transaction_tax": sale["tax"]}
        assert (block["profit"], block["returnRate"]) == (summary["profitAfterSale"],
                                                          summary["returnRateAfterSale"])
        assert block["mainBasis"] == "after_sale"
        # 국내 매수 수수료·배당 소득세는 행의 합(원 미만 버림)이다 — 처음 매수와 재투자 매수.
        rows = menu["rows"]
        fees = sum((P(r["tradeFee"]) for r in rows if r["kind"] in ("buy", "reinvest")), P(0))
        taxes = sum((P(r["dividendTax"]) for r in rows if r["kind"] == "dividend"), P(0))
        reflected = items(block["costs"]["reflected"])
        assert reflected == {"buy_fee": str(fees.quantize(P(1), rounding=ROUND_FLOOR)),
                             "dividend_tax": str(taxes.quantize(P(1), rounding=ROUND_FLOOR))}
        assert any(r["kind"] == "reinvest" for r in rows), "재투자 매수가 있어야 뜻이 있다"
        assert block["fx"] is None

    @pytest.mark.parametrize("params", [AAPL_USD, AAPL_KRW], ids=["USD", "KRW"])
    async def test_해외는_매수와_매도_수수료가_feesKrw다(self, session_factory,
                                              params: dict[str, str]) -> None:
        await seed_stocks(session_factory)
        async with http(session_factory) as client:
            menu, body = await pair(client, "/api/stocks/simulation", params)
        block, sale = body["comparison"], menu["summary"]["saleCost"]
        reflected, sold = items(block["costs"]["reflected"]), items(block["costs"]["sale"])
        assert P(reflected["buy_fee"]) + P(sold["sale_fee"]) == P(sale["feesKrw"])
        assert sold["capital_gains_tax"] == sale["tax"]
        assert block["costs"]["sale"]["total"] == sale["total"]
        assert P(block["costs"]["total"]) == (P(block["costs"]["reflected"]["total"])
                                              + P(sale["total"]))
        latest = [r for r in menu["rows"] if r["date"] == menu["summary"]["asOf"]][-1]
        assert block["fx"]["valuationRateDate"] == latest["fxRateDate"]
        assert block["fx"]["currency"] == "USD"
        assert block["fx"]["exchange"] == menu.get("exchange")
        assert block["currentValue"] == menu["summary"]["totalKrw"]


class Test가상자산_일시금:
    async def test_매수_수수료뿐이고_매도_후_점이_없다(self, session_factory) -> None:
        coin_id = await add_coin(session_factory)
        await seed_daily(session_factory, coin_id, "btc_2020_2021.json",
                         covered=(D("2020-01-01"), D("2021-12-31")))
        await seed_usd(session_factory, D("2019-12-01"), D("2022-12-31"))
        params = {"coinId": str(coin_id), "start": "2020-01-15", "principal": "10000000",
                  "principalCurrency": "KRW", "end": "2021-12-31"}
        async with http(session_factory) as client:
            menu, body = await pair(client, "/api/crypto/simulation", params)
        block = body["comparison"]
        assert block["costs"]["sale"] is None
        assert block["lineEnd"]["afterSaleReturnRate"] is None
        assert block["mainBasis"] == "holding"
        buy = next(r for r in menu["rows"] if r["kind"] == "buy")
        expected = (P(buy["tradeFee"]) * P(buy["fxRate"])).quantize(P(1), rounding=ROUND_FLOOR)
        assert items(block["costs"]["reflected"]) == {"buy_fee": str(expected)}
        assert block["currentValue"] == menu["summary"]["totalKrw"]


class Test정기예금:
    async def test_만기_세금_합과_현재_가치(self, session_factory, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        monkeypatch.setattr("src.api.services.deposit_simulation.kst_today", lambda: TODAY)
        await seed_rates(session_factory)
        params = {"institution": "commercial_bank", "start": "2020-01-15",
                  "principal": "10000000"}
        async with http(session_factory) as client:
            menu, body = await pair(client, "/api/deposit/simulation", params)
        block = body["comparison"]
        reflected = items(block["costs"]["reflected"])
        assert reflected["interest_tax_matured"] == str(sum(P(t["tax"]) for t in menu["terms"]))
        assert P(reflected["interest_tax_open"]) > 0
        summary = menu["summary"]
        assert block["currentValue"] == str(P(summary["principal"]) + P(summary["profit"]))
        assert block["costs"]["sale"] is None
        assert block["provisional"] == []

    async def test_미발표_달이면_잠정이다(self, session_factory, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        monkeypatch.setattr("src.api.services.deposit_simulation.kst_today", lambda: TODAY)
        await seed_rates(session_factory)
        params = {"institution": "commercial_bank", "start": "2026-09-15",
                  "principal": "10000000"}
        async with http(session_factory) as client:
            _, body = await pair(client, "/api/deposit/simulation", params)
        assert body["comparison"]["provisional"] == ["unpublished_rate"]


class Test부동산:
    async def test_취득_보유_매도_항목이_메뉴의_합과_같다(self, apt: Api) -> None:  # noqa: F811
        names = await apt.collected()
        params = {"complexId": str(names["헬리오시티아파트"]), "area": "30k",
                  "buyDate": "2021-03-15"}
        table = (await apt.simulate(**params)).json()
        body = (await apt.get("/api/comparison/realestate/simulation", **params)).json()
        block = body["comparison"]
        reflected = block["costs"]["reflected"]["items"]
        in_principal = [i for i in reflected if i["inPrincipal"]]
        holding = [i for i in reflected if not i["inPrincipal"]]
        assert sum(P(i["amount"]) for i in in_principal) == P(table["acquisition"]["total"])
        assert sum(P(i["amount"]) for i in holding) == P(table["summary"]["holdingTaxTotal"])
        assert block["costs"]["sale"]["total"] == table["summary"]["saleCost"]["total"]
        assert block["principal"]["krw"] == table["summary"]["invested"]
        assert block["currentValue"] == table["summary"]["value"]
