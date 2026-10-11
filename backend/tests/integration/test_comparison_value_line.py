"""비교 경로 일곱의 현재 가치 선 (014 반복 2026-10-11b T182) — spec FR-036, SC-021,
contracts/rest-api.md A12, data-model 14, research R14-29.

`comparison.valueLine.points`는 `series.points`와 **같은 날짜·같은 차례로 하나씩**이고, 값은 그
날의 원화 총자산이다 — 비교 표 "현재 가치"(`currentValue`)와 같은 뜻. 주식·가상자산 일시금은 점
`balance`(보유분만)에 예수금이 더해진 값이라 다를 수 있고, 적립식·정기예금·정기 적금·부동산은 점
`balance`와 같다. 마지막 점이 기준일이면 `currentValue`와 같은 글자다. `afterSaleValue`는 원화
원금 + 매도 후 투자 수익(매도 후 기준일 때만).

메뉴 응답(`summary`·`series`·`condition`)과 블록의 다른 칸(`lineEnd`)은 그대로다(`assert_same`).
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest

from tests.integration.comparison_support import AAPL_KRW, AAPL_USD, KRX, both, http, seed_stocks
from tests.integration.crypto_support import add_coin, seed_daily, seed_usd
from tests.integration.deposit_support import TODAY, seed_rates
from tests.integration.stock_recurring_support import AAPL_WEEKLY, KRX_MONTHLY
from tests.integration.stock_recurring_support import seed as seed_recurring
from tests.integration.test_comparison_identity import apt, assert_same  # noqa: F401
from tests.integration.test_realestate_simulation_api import Api

P = Decimal
D = dt.date.fromisoformat
LINE_END_KEYS = {"date", "holdingReturnRate", "afterSaleReturnRate"}


def value_line(body: dict) -> dict:  # type: ignore[type-arg]
    return body["comparison"]["valueLine"]  # type: ignore[no-any-return]


def assert_aligned(body: dict) -> list[tuple[dict, dict]]:  # type: ignore[type-arg]
    """점마다 하나씩, 같은 날짜·같은 차례. 지수 표기가 없다. 블록의 다른 칸은 그대로다."""
    line = value_line(body)
    assert set(line) == {"points", "afterSaleValue"}
    points, values = body["series"]["points"], line["points"]
    assert [v["date"] for v in values] == [p["date"] for p in points]
    for v in values:
        assert set(v) == {"date", "value"}
        assert "E" not in v["value"] and "e" not in v["value"]
    assert set(body["comparison"]["lineEnd"]) == LINE_END_KEYS
    return list(zip(points, values, strict=True))


def assert_end(body: dict) -> None:  # type: ignore[type-arg]
    """마지막 점이 기준일이면 그 값이 표의 현재 가치와 같은 글자다."""
    last = value_line(body)["points"][-1]
    assert last["date"] == body["summary"]["asOf"]
    assert last["value"] == body["comparison"]["currentValue"]


def assert_after_sale(body: dict) -> None:  # type: ignore[type-arg]
    """매도 후 금액 = 원화 원금 + 매도 후 투자 수익 — 매도 후 기준일 때만(`lineEnd`와 짝)."""
    block = body["comparison"]
    after = value_line(body)["afterSaleValue"]
    if block["mainBasis"] == "after_sale":
        assert block["lineEnd"]["afterSaleReturnRate"] is not None
        assert P(after) == P(block["principal"]["krw"]) + P(block["profit"])
        assert "E" not in after
    else:
        assert after is None
        assert block["lineEnd"]["afterSaleReturnRate"] is None


def assert_menu_untouched(table, series) -> None:  # type: ignore[no-untyped-def]
    """메뉴 경로에는 현재 가치 선이 없다."""
    assert "valueLine" not in table.text
    assert "valueLine" not in series.text


class Test주식_일시금:
    async def test_국내_종목은_예수금을_더한_원화_총자산이다(self, session_factory) -> None:
        await seed_stocks(session_factory)
        async with http(session_factory) as client:
            table, series, compare = await both(client, "/api/stocks/simulation", KRX)
        body = assert_same(table, series, compare)
        assert_menu_untouched(table, series)
        pairs = assert_aligned(body)
        basis = P(body["summary"]["principal"])
        # 1주 70,000원 × 142주 — 원금 1천만 원 중 남은 돈이 예수금이다. 점 `balance`와 다르다.
        assert all(P(v["value"]) > P(p["balance"]) for p, v in pairs)
        for p, v in pairs:
            # 금액 = 원금 × (1 + 수익률) — 수익률이 소수 6자리로 잘린 만큼만 어긋난다.
            assert abs(P(v["value"]) - basis * (1 + P(p["returnRate"]))) <= basis * P("0.000001")
        assert_end(body)
        assert_after_sale(body)

    @pytest.mark.parametrize("params", [AAPL_USD, AAPL_KRW], ids=["USD", "KRW"])
    async def test_해외_종목은_원화_원금_더하기_투자_수익이다(self, session_factory,
                                              params: dict[str, str]) -> None:
        await seed_stocks(session_factory)
        async with http(session_factory) as client:
            table, series, compare = await both(client, "/api/stocks/simulation", params)
        body = assert_same(table, series, compare)
        pairs = assert_aligned(body)
        summary = body["summary"]
        basis = P(summary.get("principalKrw") or summary["principal"])
        for p, v in pairs:
            assert abs(P(v["value"]) - basis * (1 + P(p["returnRate"]))) <= basis * P("0.000001")
        assert_end(body)
        assert_after_sale(body)


class Test주식_적립식:
    @pytest.mark.parametrize("params", [KRX_MONTHLY, AAPL_WEEKLY], ids=["국내 매달", "해외 매주"])
    async def test_점_잔고_원화_총자산과_같다(self, session_factory,
                                    params: dict[str, str]) -> None:
        await seed_recurring(session_factory)
        async with http(session_factory) as client:
            table, series, compare = await both(client, "/api/stocks/recurring-simulation", params)
        body = assert_same(table, series, compare)
        assert_menu_untouched(table, series)
        for p, v in assert_aligned(body):
            assert P(v["value"]) == P(p["balance"])
        assert_after_sale(body)


@pytest.fixture
async def btc(session_factory) -> int:  # type: ignore[no-untyped-def]
    coin_id = await add_coin(session_factory)
    await seed_daily(session_factory, coin_id, "btc_2020_2021.json",
                     covered=(D("2020-01-01"), D("2021-12-31")))
    await seed_usd(session_factory, D("2019-12-01"), D("2022-12-31"))
    return coin_id


class Test가상자산:
    async def test_일시금은_원화_원금_더하기_투자_수익이다(self, session_factory, btc: int) -> None:
        params = {"coinId": str(btc), "start": "2020-01-15", "principal": "10000000",
                  "principalCurrency": "KRW", "end": "2021-12-31"}
        async with http(session_factory) as client:
            table, series, compare = await both(client, "/api/crypto/simulation", params)
        body = assert_same(table, series, compare)
        assert_menu_untouched(table, series)
        basis = P(body["summary"]["principal"])
        for p, v in assert_aligned(body):
            assert abs(P(v["value"]) - basis * (1 + P(p["returnRate"]))) <= basis * P("0.000001")
            # 남은 현금이 0 이상이라 보유분만의 평가보다 작지 않다.
            assert P(v["value"]) >= P(p["balance"])
        assert_end(body)
        assert_after_sale(body)

    async def test_적립식은_점_잔고와_같다(self, session_factory, btc: int) -> None:
        params = {"coinId": str(btc), "start": "2020-01-15", "amount": "100000",
                  "principalCurrency": "KRW", "frequency": "monthly", "end": "2021-12-31"}
        async with http(session_factory) as client:
            table, series, compare = await both(client, "/api/crypto/recurring-simulation", params)
        body = assert_same(table, series, compare)
        for p, v in assert_aligned(body):
            assert P(v["value"]) == P(p["balance"])
        assert_end(body)
        assert_after_sale(body)


@pytest.fixture
def deposit_today(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr("src.api.services.deposit_simulation.kst_today", lambda: TODAY)


class Test예금:
    async def test_정기예금은_점_잔고와_같다(self, session_factory, deposit_today: None) -> None:
        await seed_rates(session_factory)
        params = {"institution": "commercial_bank", "start": "2020-01-15", "principal": "10000000"}
        async with http(session_factory) as client:
            table, series, compare = await both(client, "/api/deposit/simulation", params)
        body = assert_same(table, series, compare)
        assert_menu_untouched(table, series)
        for p, v in assert_aligned(body):
            assert P(v["value"]) == P(p["balance"])
        assert_end(body)
        assert_after_sale(body)

    async def test_정기_적금은_점_잔고와_같다(self, session_factory, deposit_today: None) -> None:
        await seed_rates(session_factory, "commercial_bank_isav")
        await seed_rates(session_factory, "commercial_bank")
        params = {"institution": "commercial_bank", "start": "2015-01-15", "amount": "1000000"}
        async with http(session_factory) as client:
            table, series, compare = await both(client, "/api/deposit/installment-simulation",
                                                params)
        body = assert_same(table, series, compare)
        for p, v in assert_aligned(body):
            assert P(v["value"]) == P(p["balance"])
        assert_end(body)
        assert_after_sale(body)


class Test부동산:
    async def test_점_평가액과_같다(self, apt: Api) -> None:  # noqa: F811
        names = await apt.collected()
        params = {"complexId": str(names["헬리오시티아파트"]), "area": "30k",
                  "buyDate": "2021-03-15"}
        table, series, compare = await both(apt.http, "/api/realestate/simulation", params)
        body = assert_same(table, series, compare)
        assert_menu_untouched(table, series)
        for p, v in assert_aligned(body):
            assert P(v["value"]) == P(p["balance"])
        assert_after_sale(body)
