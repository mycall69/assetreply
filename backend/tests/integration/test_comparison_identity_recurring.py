"""비교 경로 셋(주식·가상자산 적립식, 정기 적금) ↔ 메뉴 경로 (013 T043) — FR-006, FR-011, FR-020,
SC-001, SC-002, contracts/rest-api.md 1.

T010과 같은 대조다 — 같은 질의면 `summary`·`condition`이 같고, `series`는 같은 `maxPoints`의 메뉴
`/series`와 같고, 202·거절 본문이 같다. 비용 몫은 보드의 합계와
짝이다(`buyFeeTotal`·`dividendTaxTotal`·`saleCost`·`taxTotal`). 가상자산 2027년 기준일은
`routes.crypto_simulation`의 `utc_yesterday`를 바꿔 만든다(CLAUDE.md 011).
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest

from src.ingestion.investing.parse import DailyBar
from src.repository import crypto_daily
from tests.integration.comparison_support import both, history_rows, http
from tests.integration.crypto_support import ETH_ID, add_coin, seed_daily, seed_usd
from tests.integration.deposit_support import TODAY, seed_rates
from tests.integration.stock_recurring_support import AAPL_WEEKLY, KRX_MONTHLY, seed
from tests.integration.test_comparison_identity import assert_same

D = dt.date.fromisoformat
P = Decimal


def items(part: dict) -> dict[str, str | None]:  # type: ignore[type-arg]
    return {i["kind"]: i["amount"] for i in part["items"]}


class Test주식_적립식:
    @pytest.mark.parametrize("params", [KRX_MONTHLY, AAPL_WEEKLY], ids=["국내 매달", "해외 매주"])
    async def test_메뉴와_같고_비용이_보드의_합계다(self, session_factory,
                                         params: dict[str, str]) -> None:
        await seed(session_factory)
        async with http(session_factory) as client:
            body = assert_same(*await both(client, "/api/stocks/recurring-simulation", params))
        summary, block = body["summary"], body["comparison"]
        assert items(block["costs"]["reflected"]) == {"buy_fee": summary["buyFeeTotal"],
                                                      "dividend_tax": summary["dividendTaxTotal"]}
        sale = summary["saleCost"]
        assert block["costs"]["sale"]["items"][0] == {"kind": "sale_fee", "amount": sale["fee"],
                                                      "inPrincipal": False}
        assert block["costs"]["sale"]["total"] == sale["total"]
        assert (block["profit"], block["returnRate"]) == (summary["profitAfterSale"],
                                                          summary["returnRateAfterSale"])
        assert block["currentValue"] == summary["totalKrw"]
        assert block["principal"]["krw"] == summary["contributedKrw"]

    async def test_받지_않은_종목은_같은_202다(self, session_factory) -> None:
        await seed(session_factory)
        params = {**KRX_MONTHLY, "start": "2010-01-04"}
        async with http(session_factory) as client:
            menu = await client.get("/api/stocks/recurring-simulation", params=params)
            compare = await client.get("/api/comparison/stocks/recurring-simulation",
                                       params=params)
        assert (menu.status_code, compare.status_code) == (202, 202)
        assert compare.json() == menu.json()


@pytest.fixture
async def btc(session_factory) -> int:  # type: ignore[no-untyped-def]
    coin_id = await add_coin(session_factory)
    await seed_daily(session_factory, coin_id, "btc_2020_2021.json",
                     covered=(D("2020-01-01"), D("2021-12-31")))
    await seed_usd(session_factory, D("2019-12-01"), D("2022-12-31"))
    return coin_id


def crypto(coin_id: int, **over: str) -> dict[str, str]:
    base = {"coinId": str(coin_id), "start": "2020-01-15", "amount": "100000",
            "principalCurrency": "KRW", "frequency": "monthly", "end": "2021-12-31"}
    base.update(over)
    return base


class Test가상자산_적립식:
    async def test_메뉴와_같고_세금은_0이다(self, session_factory, btc: int) -> None:
        async with http(session_factory) as client:
            body = assert_same(*await both(client, "/api/crypto/recurring-simulation",
                                           crypto(btc)))
        summary, block = body["summary"], body["comparison"]
        assert items(block["costs"]["reflected"]) == {"buy_fee": summary["buyFeeTotal"]}
        assert items(block["costs"]["sale"]) == {"sale_fee": summary["saleCost"]["fee"],
                                                 "crypto_tax": "0"}
        assert block["mainBasis"] == "after_sale"

    async def test_과세_시행일_뒤면_세금과_주_값을_비운다(self, session_factory,
                                              monkeypatch) -> None:  # type: ignore[no-untyped-def]
        monkeypatch.setattr("src.api.routes.crypto_simulation.utc_yesterday",
                            lambda: D("2027-01-05"))
        coin_id = await add_coin(session_factory, ETH_ID, "ETH", "Ethereum", name_ko="이더리움")
        days = [D("2026-12-01") + dt.timedelta(days=i) for i in range(35)]
        async with session_factory() as s:
            await crypto_daily.store_bars(s, coin_id, [
                DailyBar(day=d, open=P("3000") + i, high=P("3100") + i, low=P("2900") + i,
                         close=P("3000") + i, volume=None) for i, d in enumerate(days)])
            await crypto_daily.record_coverage(s, coin_id, days[0], days[-1])
            await s.commit()
        await seed_usd(session_factory, D("2026-11-01"), D("2027-01-04"))
        params = crypto(coin_id, start="2026-12-01", end="2027-01-04", frequency="weekly")
        async with http(session_factory) as client:
            body = assert_same(*await both(client, "/api/crypto/recurring-simulation", params))
        block = body["comparison"]
        assert block["costs"]["sale"]["blank"] == "outside_rules"
        assert block["costs"]["total"] is None
        assert (block["mainBasis"], block["profit"], block["returnRate"]) == (
            "unavailable", None, None)

    async def test_시작일이_계산_끝보다_늦으면_같은_거절이다(self, session_factory,
                                                btc: int) -> None:
        params = crypto(btc, start="2099-01-01", end="2099-12-31")
        async with http(session_factory) as client:
            menu = await client.get("/api/crypto/recurring-simulation", params=params)
            compare = await client.get("/api/comparison/crypto/recurring-simulation",
                                       params=params)
        assert (menu.status_code, compare.status_code) == (400, 400)
        assert compare.json() == menu.json()
        assert compare.json()["status"] == "start_after_end"


INSTALLMENT = {"institution": "commercial_bank", "start": "2015-01-15", "amount": "1000000"}


@pytest.fixture
def deposit_today(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr("src.api.services.deposit_simulation.kst_today", lambda: TODAY)


async def both_rates(session_factory) -> None:  # type: ignore[no-untyped-def]
    await seed_rates(session_factory, "commercial_bank_isav")
    await seed_rates(session_factory, "commercial_bank")


class Test정기_적금:
    async def test_메뉴와_같고_만기_세금이_메뉴_칸이다(self, session_factory,
                                           deposit_today: None) -> None:
        await both_rates(session_factory)
        async with http(session_factory) as client:
            body = assert_same(*await both(client, "/api/deposit/installment-simulation",
                                           INSTALLMENT))
        summary, block = body["summary"], body["comparison"]
        reflected = items(block["costs"]["reflected"])
        assert reflected["interest_tax_matured"] == summary["taxTotal"]
        assert P(reflected["interest_tax_open"]) > 0
        assert block["currentValue"] == summary["balance"]
        assert block["principal"]["krw"] == summary["contributed"]
        assert block["costs"]["sale"] is None
        assert "contracts" not in body and "deposits" not in body

    async def test_적금이_없는_투자처는_같은_거절이다(self, session_factory,
                                          deposit_today: None) -> None:
        params = {**INSTALLMENT, "institution": "savings_bank"}
        async with http(session_factory) as client:
            menu = await client.get("/api/deposit/installment-simulation", params=params)
            compare = await client.get("/api/comparison/deposit/installment-simulation",
                                       params=params)
        assert (menu.status_code, compare.status_code) == (400, 400)
        assert compare.json() == menu.json()
        assert compare.json()["status"] == "installment_not_available"

    async def test_금리_시작_전은_같은_거절이다(self, session_factory,
                                      deposit_today: None) -> None:
        await both_rates(session_factory)
        params = {**INSTALLMENT, "start": "2001-01-15"}
        async with http(session_factory) as client:
            menu = await client.get("/api/deposit/installment-simulation", params=params)
            compare = await client.get("/api/comparison/deposit/installment-simulation",
                                       params=params)
        assert (menu.status_code, compare.status_code) == (409, 409)
        assert compare.json() == menu.json()
        assert compare.json()["status"] == "before_first_month"

    async def test_이력을_쓰지_않는다(self, session_factory, deposit_today: None) -> None:
        await both_rates(session_factory)
        async with http(session_factory) as client:
            await client.get("/api/comparison/deposit/installment-simulation", params=INSTALLMENT)
        assert await history_rows(session_factory) == 0
