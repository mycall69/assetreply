"""표의 통화와 KRW 평가 (T137) — 006 FR-066, FR-068, SC-026, SC-028, research R6-25,
contracts/rest-api. 반복 2026-10-03 #4.

해외 종목의 행은 **종목 통화 값을 그대로** 싣는다 — 예수금·배당 소득세·매매 수수료·잔고·배당금 총액.
그 위에 KRW 값(`balanceKrw`, 투자 수익·수익율)을 따로 싣는다. 005 FR-041(원금 통화로 환산)을
대체한다.

**투자 수익·수익율은 원금 통화와 관계없이 KRW다.** 달러 원금만 달러 기준이면 이력 비교에서 원화 원금
실행과 다른 기준의 수익률이 나란히 놓인다. 달러·엔 원금의 KRW 원금은 **첫 매수일의 매매기준율**로
정한다 — 행마다 바꾸면 원금이 움직여 수익률이 환율만으로 움직인다.
"""
from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest
from httpx2 import ASGITransport, AsyncClient
from sqlalchemy import select

from src.api.main import create_app
from src.db.dialect import upsert
from src.db.models import (
    FxCoverage,
    FxRate,
    Stock,
    StockCoverage,
    StockDividend,
    StockPrice,
)
from src.db.session import get_session

D = dt.date.fromisoformat
#: 2021-09-01(수) 배당락 → 09-03(금)이 2번째 거래일(재투자).
DAYS = ["2021-08-02", "2021-09-01", "2021-09-02", "2021-09-03", "2021-10-01"]
#: 주가가 오르고 환율도 오른다 — 달러 기준 수익률과 KRW 기준 수익률이 다르게 나온다.
USD_PRICE = {"2021-08-02": "100", "2021-09-01": "100", "2021-09-02": "100",
             "2021-09-03": "100", "2021-10-01": "110"}
USD_FX = {"2021-08-02": "1150", "2021-09-01": "1160", "2021-09-02": "1165",
          "2021-09-03": "1170", "2021-10-01": "1190"}
#: 엔화는 100엔당 고시다(006 FR-042). 1단위당 값으로 평가하지 않으면 KRW 원금이 100배 틀린다.
JPY_FX = {"2021-08-02": "1045", "2021-09-01": "1060", "2021-10-01": "1020"}
FEE = Decimal("0.000150")
TAX_FOREIGN = Decimal("0.150000")
ONE_WON = Decimal("1")


@pytest.fixture
async def client(session_factory):
    async with session_factory() as s:
        await upsert(s, Stock, [
            {"market": "NASDAQ", "symbol": "AAPL", "name": "Apple Inc.", "currency": "USD",
             "first_available_date": D("1980-12-12")},
            {"market": "TSE", "symbol": "7203.T", "name": "Toyota", "currency": "JPY",
             "first_available_date": D("1999-05-10")},
            {"market": "KRX", "symbol": "005930.KS", "name": "삼성전자", "currency": "KRW",
             "first_available_date": D("1975-06-11")},
        ])
        await s.commit()
        ids = {r.symbol: int(r.id) for r in (await s.execute(select(Stock))).scalars()}
        prices = {"AAPL": USD_PRICE,
                  "7203.T": {d: "2000" for d in DAYS},
                  "005930.KS": {d: "70000" for d in DAYS}}
        # 배당이 커야 원화 원금(약 868달러)에서도 재투자 행이 생긴다.
        dividends = {"AAPL": "10", "7203.T": "30", "005930.KS": "361"}
        for symbol, by_day in prices.items():
            await upsert(s, StockPrice, [{
                "stock_id": ids[symbol], "quote_date": D(d), "open_raw": Decimal(v),
                "close_raw": Decimal(v), "close_adjusted": Decimal(v),
                "source": "yahoo:chart"} for d, v in by_day.items()])
            await upsert(s, StockDividend, [{
                "stock_id": ids[symbol], "ex_date": D("2021-09-01"),
                "amount_per_share": Decimal(dividends[symbol]), "source": "yahoo:chart"}])
            await upsert(s, StockCoverage, [{
                "stock_id": ids[symbol], "covered_from": D("2021-08-01"),
                "covered_through": D("2021-10-31")}], preserve=())
        for code, by_day, unit in (("USD", USD_FX, 1), ("JPY", JPY_FX, 100)):
            await upsert(s, FxRate, [{
                "currency_code": code, "quote_date": D(d), "base_rate": Decimal(v),
                "quote_unit": unit, "source": "ECOS:731Y001", "is_provisional": False}
                for d, v in by_day.items()])
            await upsert(s, FxCoverage, [{
                "currency_code": code, "covered_from": D("2021-07-01"),
                "covered_through": D("2021-10-31")}], preserve=())
        await s.commit()

    app = create_app()

    async def _override():
        async with session_factory() as s:
            yield s

    app.dependency_overrides[get_session] = _override
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


BASE = {"start": "2021-08-01", "end": "2021-10-31", "reinvest": "true", "limit": "50"}
AAPL = {"market": "NASDAQ", "symbol": "AAPL"}
KRW_PRINCIPAL = {**BASE, **AAPL, "principal": "1000000", "principalCurrency": "KRW"}
USD_PRINCIPAL = {**BASE, **AAPL, "principal": "1000", "principalCurrency": "USD"}


async def simulate(client: AsyncClient, params: dict[str, str]) -> dict:
    res = await client.get("/api/stocks/simulation", params=params)
    assert res.status_code == 200, res.text
    body: dict = res.json()
    return body


def one(body: dict, kind: str, date: str | None = None) -> dict:
    [row] = [r for r in body["rows"]
             if r["kind"] == kind and (date is None or r["date"] == date)]
    return row


def dec(row: dict, key: str) -> Decimal:
    return Decimal(row[key])


@pytest.mark.parametrize("params", [KRW_PRINCIPAL, USD_PRINCIPAL], ids=["원화원금", "달러원금"])
class Test해외_종목은_종목_통화로_남는다:
    """FR-066, SC-026 — 원금 통화와 관계없이 같은 열이 같은 통화다."""

    async def test_잔고는_보유_수와_시가의_곱이다(self, client, params) -> None:
        """환산했다면 원화 원금에서 1,000배 가까이 커진다."""
        for row in (await simulate(client, params))["rows"]:
            assert dec(row, "balance") == Decimal(row["heldShares"]) * dec(row, "openPrice")

    async def test_배당_소득세는_달러다(self, client, params) -> None:
        row = one(await simulate(client, params), "dividend")
        # 배당락 행은 사지 않는다 — 보유 수가 배당이 붙은 수다.
        assert dec(row, "dividendTax") == (
            Decimal(row["heldShares"]) * dec(row, "dividendPerShare") * TAX_FOREIGN)

    async def test_매매_수수료는_달러다(self, client, params) -> None:
        row = one(await simulate(client, params), "reinvest")
        assert dec(row, "tradeFee") == (
            Decimal(row["boughtShares"]) * dec(row, "openPrice") * FEE)

    async def test_예수금은_달러다(self, client, params) -> None:
        """배당락 행의 예수금 증가가 같은 행의 세후 배당금 총액(달러)과 같다."""
        body = await simulate(client, params)
        before = one(body, "month_first", "2021-08-02")
        dividend = one(body, "dividend")
        assert dec(dividend, "cash") - dec(before, "cash") == dec(dividend, "dividendTotalNet")

    async def test_배당금_총액은_달러다(self, client, params) -> None:
        """FR-067 — 세전 = 보유 수 × 주당 배당금, 세후 = 세전 − 세금."""
        row = one(await simulate(client, params), "dividend")
        assert dec(row, "dividendTotal") == (
            Decimal(row["heldShares"]) * dec(row, "dividendPerShare"))
        assert dec(row, "dividendTotal") - dec(row, "dividendTotalNet") == dec(row, "dividendTax")

    async def test_배당락_행이_아니면_배당금_총액이_없다(self, client, params) -> None:
        for row in (await simulate(client, params))["rows"]:
            if row["kind"] != "dividend":
                assert "dividendTotal" not in row and "dividendTotalNet" not in row

    async def test_모든_행에_환율과_KRW_잔고가_있다(self, client, params) -> None:
        """FR-068 — 원금이 달러여도 KRW로 평가하므로 환율이 있다."""
        for row in (await simulate(client, params))["rows"]:
            assert "fxRate" in row and "fxRateDate" in row
            assert abs(dec(row, "balanceKrw") - dec(row, "balance") * dec(row, "fxRate")) <= (
                Decimal("0.5"))

    async def test_투자금은_입력한_원금이다(self, client, params) -> None:
        body = await simulate(client, params)
        assert all(r["principal"] == params["principal"] for r in body["rows"])
        assert body["summary"]["principal"] == params["principal"]


class Test원화_원금:
    async def test_투자_수익은_KRW다(self, client) -> None:
        """투자 수익 = (잔고 + 예수금) × 그 행의 매매기준율 − 원화 원금."""
        for row in (await simulate(client, KRW_PRINCIPAL))["rows"]:
            expected = ((dec(row, "balance") + dec(row, "cash")) * dec(row, "fxRate")
                        - Decimal("1000000"))
            assert abs(dec(row, "profit") - expected) <= ONE_WON, row

    async def test_수익율은_KRW_수익을_원화_원금으로_나눈_값이다(self, client) -> None:
        for row in (await simulate(client, KRW_PRINCIPAL))["rows"]:
            expected = dec(row, "profit") / Decimal("1000000")
            assert abs(dec(row, "returnRate") - expected) <= Decimal("0.000001")

    async def test_요약에_KRW_원금이_따로_없다(self, client) -> None:
        """원금이 곧 KRW 원금이다 — 같은 값을 두 번 싣지 않는다."""
        body = await simulate(client, KRW_PRINCIPAL)
        assert "principalKrw" not in body["summary"]
        assert "exchange" in body  # 환전은 원화 원금에만 있다 (FR-052)


class Test달러_원금:
    async def test_KRW_원금은_첫_매수일의_매매기준율이다(self, client) -> None:
        """1,000달러 × 1,150(2021-08-02) = 1,150,000원. 행마다 바꾸지 않는다."""
        body = await simulate(client, USD_PRINCIPAL)
        assert Decimal(body["summary"]["principalKrw"]) == Decimal("1150000")

    async def test_투자_수익은_KRW다(self, client) -> None:
        for row in (await simulate(client, USD_PRINCIPAL))["rows"]:
            expected = ((dec(row, "balance") + dec(row, "cash")) * dec(row, "fxRate")
                        - Decimal("1150000"))
            assert abs(dec(row, "profit") - expected) <= ONE_WON, row

    async def test_수익율은_KRW_기준이다(self, client) -> None:
        """달러 기준(달러 수익 ÷ 1,000)이면 환율 상승분이 빠진다."""
        row = one(await simulate(client, USD_PRINCIPAL), "month_first", "2021-10-01")
        krw = dec(row, "profit") / Decimal("1150000")
        usd = (dec(row, "balance") + dec(row, "cash") - Decimal("1000")) / Decimal("1000")
        assert abs(dec(row, "returnRate") - krw) <= Decimal("0.000001")
        assert abs(dec(row, "returnRate") - usd) > Decimal("0.01")

    async def test_요약이_마지막_거래일의_KRW_값이다(self, client) -> None:
        """005 FR-032 — 보드와 표의 마지막 행은 같은 기준이다."""
        body = await simulate(client, USD_PRINCIPAL)
        last = one(body, "month_first", "2021-10-01")
        assert body["summary"]["profit"] == last["profit"]
        assert body["summary"]["returnRate"] == last["returnRate"]

    async def test_환전은_없다(self, client) -> None:
        """FR-052 — 평가만 한다. 환전 정보가 있으면 달러를 달러로 바꾼 것처럼 읽힌다."""
        assert "exchange" not in await simulate(client, USD_PRINCIPAL)


class Test엔_원금:
    async def test_KRW_원금은_1엔당_값으로_정한다(self, client) -> None:
        """100,000엔 × 10.45(1,045원/100엔) = 1,045,000원. 단위를 버리면 100배다."""
        body = await simulate(client, {**BASE, "market": "TSE", "symbol": "7203.T",
                                       "principal": "100000", "principalCurrency": "JPY"})
        assert Decimal(body["summary"]["principalKrw"]) == Decimal("1045000")
        row = one(body, "month_first", "2021-10-01")
        assert row["fxRate"] == "10.200000"
        expected = ((dec(row, "balance") + dec(row, "cash")) * Decimal("10.2")
                    - Decimal("1045000"))
        assert abs(dec(row, "profit") - expected) <= ONE_WON


class Test국내_종목:
    async def test_모두_KRW이고_괄호_값이_없다(self, client) -> None:
        body = await simulate(client, {**BASE, "market": "KRX", "symbol": "005930.KS",
                                       "principal": "1000000", "principalCurrency": "KRW"})
        for row in body["rows"]:
            assert "balanceKrw" not in row and "fxRate" not in row
            assert dec(row, "profit") == (
                dec(row, "balance") + dec(row, "cash") - Decimal("1000000"))
        assert "principalKrw" not in body["summary"]
        dividend = one(body, "dividend")
        assert dec(dividend, "dividendTotal") == Decimal(dividend["heldShares"]) * Decimal("361")
