"""비교 경로 일곱의 단가 등락 (013 반복 2026-10-09 T087) — spec FR-011a, SC-001, SC-010,
contracts/rest-api.md 1.2, research R13-18.

단가의 시작일·기준일 값은 그 대상 메뉴 성과 추이의 가격 선(주식 수정 종가·가상자산 시가·예금 그 달
금리)과 부동산 보드(매입가·평가액)의 같은 날·달 값이다(SC-010). 분할이 낀 종목은 시작일 종가를 그 뒤
분할 비율로 나눈 수정주가이고, 등락률이 그것을 기준으로 한다. 메뉴 응답(`summary`·`series`)은
그대로다 (`assert_same`).

부동산 기준일 시세가 없는 경우(`missing: no_trades`)는 이 고정 데이터로 만들 수 없어 단위 테스트
(`test_unit_price`·`test_comparison_metrics_unit_price`)가 본다.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest

from src.db.dialect import upsert
from src.db.models import Stock, StockCoverage, StockPrice, StockSplit
from src.simulation.money import quantize_rate
from tests.integration.comparison_support import KRX, both, http, seed_stocks
from tests.integration.crypto_support import add_coin, seed_daily, seed_usd
from tests.integration.deposit_support import LATEST, TODAY, rate_of, seed_rates
from tests.integration.stock_recurring_support import AAPL_WEEKLY, KRX_MONTHLY, krx_price
from tests.integration.stock_recurring_support import seed as seed_recurring
from tests.integration.test_comparison_identity import apt, assert_same  # noqa: F401
from tests.integration.test_realestate_simulation_api import Api

P = Decimal
D = dt.date.fromisoformat

#: 카카오 — 2021-09-02에 5:1 분할(원주가 500 → 100). 수정주가로는 시작일 단가가 100이다.
KAKAO_RAW = {"2021-08-02": "500", "2021-09-01": "500", "2021-09-02": "100", "2021-09-03": "100",
             "2021-10-01": "110"}
KAKAO = {**KRX, "symbol": "035720.KS"}


def unit(body: dict) -> dict:  # type: ignore[type-arg]
    return body["comparison"]["unitPrice"]  # type: ignore[no-any-return]


def first_point(body: dict) -> dict:  # type: ignore[type-arg]
    return body["series"]["points"][0]  # type: ignore[no-any-return]


def rate(change: str, start: str) -> str:
    return str(quantize_rate(P(change) / P(start)))


async def seed_kakao(session_factory) -> None:  # type: ignore[no-untyped-def]
    async with session_factory() as s:
        await upsert(s, Stock, [{"market": "KRX", "symbol": "035720.KS", "name": "카카오",
                                 "currency": "KRW", "first_available_date": D("1999-11-11")}])
        await s.commit()
        stock_id = next(int(r.id) for r in (await s.execute(
            Stock.__table__.select().where(Stock.symbol == "035720.KS"))).all())
        await upsert(s, StockPrice, [
            {"stock_id": stock_id, "quote_date": D(d), "open_raw": P(v), "close_raw": P(v),
             "close_adjusted": P(v), "source": "yahoo:chart"} for d, v in KAKAO_RAW.items()])
        await upsert(s, StockSplit, [{"stock_id": stock_id, "effective_date": D("2021-09-02"),
                                      "numerator": 5, "denominator": 1,
                                      "source": "yahoo:chart"}])
        await upsert(s, StockCoverage, [{"stock_id": stock_id, "covered_from": D("2021-08-01"),
                                         "covered_through": D("2021-10-31")}], preserve=())
        await s.commit()


class Test주식_일시금:
    async def test_국내_종목_단가는_메뉴_주가_선과_같다(self, session_factory) -> None:
        await seed_stocks(session_factory)
        async with http(session_factory) as client:
            body = assert_same(*await both(client, "/api/stocks/simulation", KRX))
        u = unit(body)
        # 시작일 2021-08-01(일요일) → 매수일 2021-08-02. 원주가 100 × 700.
        assert (u["kind"], u["basis"], u["currency"]) == ("share", "split_restated_close", "KRW")
        assert u["start"]["date"] == first_point(body)["date"] == "2021-08-02"
        assert P(u["start"]["value"]) == P(first_point(body)["price"]) == P("70000")
        assert (u["asOf"]["date"], P(u["asOf"]["value"])) == (body["summary"]["asOf"], P("77000"))
        assert (P(u["change"]), u["changeRate"]) == (P("7000"), rate("7000", "70000"))
        assert u["split"] is None and u["asOf"]["missing"] is None

    async def test_분할이_끼면_수정주가로_등락을_잰다(self, session_factory) -> None:
        await seed_kakao(session_factory)
        async with http(session_factory) as client:
            body = assert_same(*await both(client, "/api/stocks/simulation", KAKAO))
        u = unit(body)
        # 원주가 500을 5:1로 나눈 100 — 원주가로 쟀으면 500 → 110(−78%)이 된다.
        assert P(u["start"]["value"]) == P(first_point(body)["price"]) == P("100")
        assert P(u["asOf"]["value"]) == P("110")
        assert (P(u["change"]), u["changeRate"]) == (P("10"), "0.100000")
        assert u["split"] == {"ratio": "5:1"}

    async def test_해외_종목은_상장국_통화다(self, session_factory) -> None:
        await seed_stocks(session_factory)
        params = {**KRX, "market": "NASDAQ", "symbol": "AAPL"}
        async with http(session_factory) as client:
            body = assert_same(*await both(client, "/api/stocks/simulation", params))
        u = unit(body)
        assert u["currency"] == "USD"
        assert (P(u["start"]["value"]), P(u["asOf"]["value"])) == (P("100"), P("110"))


class Test주식_적립식:
    @pytest.mark.parametrize(("params", "currency"), [(KRX_MONTHLY, "KRW"), (AAPL_WEEKLY, "USD")],
                             ids=["국내 매달", "해외 매주"])
    async def test_첫_납입_수정주가와_기준일_종가다(self, session_factory,
                                         params: dict[str, str], currency: str) -> None:
        await seed_recurring(session_factory)
        async with http(session_factory) as client:
            body = assert_same(*await both(client, "/api/stocks/recurring-simulation", params))
        u = unit(body)
        assert u["currency"] == currency
        assert u["start"]["date"] == first_point(body)["date"]
        assert P(u["start"]["value"]) == P(first_point(body)["price"])
        assert u["asOf"]["date"] == body["summary"]["asOf"]
        if currency == "KRW":
            assert P(u["asOf"]["value"]) == krx_price(u["asOf"]["date"])[1]
        assert P(u["change"]) == P(u["asOf"]["value"]) - P(u["start"]["value"])


@pytest.fixture
async def btc(session_factory) -> int:  # type: ignore[no-untyped-def]
    coin_id = await add_coin(session_factory)
    await seed_daily(session_factory, coin_id, "btc_2020_2021.json",
                     covered=(D("2020-01-01"), D("2021-12-31")))
    await seed_usd(session_factory, D("2019-12-01"), D("2022-12-31"))
    return coin_id


class Test가상자산:
    async def test_일시금은_매수_일봉과_기준일_일봉의_시가다(self, session_factory,
                                               btc: int) -> None:
        params = {"coinId": str(btc), "start": "2020-01-15", "principal": "10000000",
                  "principalCurrency": "KRW", "end": "2021-12-31"}
        async with http(session_factory) as client:
            body = assert_same(*await both(client, "/api/crypto/simulation", params))
        u = unit(body)
        points = body["series"]["points"]
        assert (u["kind"], u["basis"], u["currency"]) == ("coin", "daily_open", "USD")
        assert (u["start"]["date"], P(u["start"]["value"])) == (points[0]["date"],
                                                                P(points[0]["price"]))
        assert (u["asOf"]["date"], P(u["asOf"]["value"])) == (points[-1]["date"],
                                                              P(points[-1]["price"]))
        assert u["asOf"]["date"] == body["summary"]["asOf"]
        assert u["changeRate"] == rate(u["change"], u["start"]["value"])

    async def test_적립식은_첫_납입_일봉의_시가다(self, session_factory, btc: int) -> None:
        params = {"coinId": str(btc), "start": "2020-01-15", "amount": "100000",
                  "principalCurrency": "KRW", "frequency": "monthly", "end": "2021-12-31"}
        async with http(session_factory) as client:
            body = assert_same(*await both(client, "/api/crypto/recurring-simulation", params))
        u = unit(body)
        points = body["series"]["points"]
        assert (u["start"]["date"], P(u["start"]["value"])) == (points[0]["date"],
                                                                P(points[0]["price"]))
        assert (u["asOf"]["date"], P(u["asOf"]["value"])) == (points[-1]["date"],
                                                              P(points[-1]["price"]))


@pytest.fixture
def deposit_today(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr("src.api.services.deposit_simulation.kst_today", lambda: TODAY)


class Test예금:
    async def test_정기예금은_가입_달_금리와_마지막_발표_달_잠정_금리다(
            self, session_factory, deposit_today: None) -> None:
        await seed_rates(session_factory)
        params = {"institution": "commercial_bank", "start": "2020-01-15", "principal": "10000000"}
        async with http(session_factory) as client:
            body = assert_same(*await both(client, "/api/deposit/simulation", params))
        u = unit(body)
        opened, latest = rate_of("commercial_bank", "2020-01"), rate_of("commercial_bank",
                                                                        LATEST.strftime("%Y-%m"))
        assert (u["kind"], u["basis"], u["currency"]) == ("rate", "published_rate", None)
        assert (u["start"]["date"], P(u["start"]["value"])) == ("2020-01-01", opened)
        assert P(first_point(body)["price"]) == opened
        # 기준일(2026-10)은 미발표 — 마지막 발표 달(2026-08)의 금리를 그 달과 함께 잠정으로.
        assert u["asOf"] == {"date": LATEST.isoformat(), "value": u["asOf"]["value"],
                             "provisional": True, "estimated": False, "missing": None}
        assert P(u["asOf"]["value"]) == latest
        assert (P(u["change"]), u["changeRate"]) == (latest - opened, None)

    async def test_기준일_달이_발표되었으면_잠정이_아니다(self, session_factory,
                                              deposit_today: None) -> None:
        await seed_rates(session_factory)
        params = {"institution": "commercial_bank", "start": "2020-01-15", "principal": "10000000",
                  "end": "2025-12-31"}
        async with http(session_factory) as client:
            body = assert_same(*await both(client, "/api/deposit/simulation", params))
        u = unit(body)
        assert u["asOf"]["provisional"] is False
        assert u["asOf"]["date"] == body["summary"]["asOf"][:7] + "-01"
        assert P(u["asOf"]["value"]) == rate_of("commercial_bank", body["summary"]["asOf"][:7])

    async def test_정기_적금은_적금_금리다(self, session_factory, deposit_today: None) -> None:
        await seed_rates(session_factory, "commercial_bank_isav")
        await seed_rates(session_factory, "commercial_bank")
        params = {"institution": "commercial_bank", "start": "2015-01-15", "amount": "1000000"}
        async with http(session_factory) as client:
            body = assert_same(*await both(client, "/api/deposit/installment-simulation", params))
        u = unit(body)
        assert P(u["start"]["value"]) == rate_of("commercial_bank_isav", "2015-01")
        assert P(u["asOf"]["value"]) == rate_of("commercial_bank_isav", LATEST.strftime("%Y-%m"))
        assert u["asOf"]["provisional"] is True


class Test부동산:
    async def test_매입가와_평가액의_시세다(self, apt: Api) -> None:  # noqa: F811
        names = await apt.collected()
        params = {"complexId": str(names["헬리오시티아파트"]), "area": "30k",
                  "buyDate": "2021-03-15"}
        body = assert_same(*await both(apt.http, "/api/realestate/simulation", params))
        u, summary = unit(body), body["summary"]
        assert (u["kind"], u["basis"], u["currency"]) == ("home", "market_price", "KRW")
        assert (u["start"]["date"], P(u["start"]["value"])) == ("2021-03-01",
                                                                P(summary["buyPrice"]))
        assert u["start"]["estimated"] == body["condition"]["buyPriceWindow"]["estimated"]
        assert (u["asOf"]["date"], P(u["asOf"]["value"])) == (summary["valueMonth"] + "-01",
                                                              P(summary["value"]))
        assert (u["asOf"]["estimated"], u["asOf"]["provisional"]) == (summary["estimated"],
                                                                      summary["provisional"])
        assert P(u["change"]) == P(summary["value"]) - P(summary["buyPrice"])
