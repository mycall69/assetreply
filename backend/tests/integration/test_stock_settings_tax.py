"""배당 소득세 국내·해외 (T126) — 006 FR-055, SC-021, research R6-23. 반복 2026-10-03 #3.

국내 종목(KRX)에는 국내 세율(기본 15.4%), 그 밖(미국·일본)에는 해외 세율(기본 15%)을 쓴다. 해외
종목에 국내 세율을 쓰면 세후 배당이 조금씩 적게 잡혀 수십 년 복리로 벌어지는데 오류가 없다. 응답
조건의 `dividendTaxRate`는 **적용한 세율**이다.

006 FR-068(반복 2026-10-03 #4, T137) — 달러 원금으로 미국 종목을 돌려도 투자 수익을 KRW로
평가하므로, 픽스처가 USD 환율을 받아 둔 상태를 함께 만든다. 없으면 202(환율 수집)다.
"""
from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest
from httpx2 import ASGITransport, AsyncClient
from sqlalchemy import select

from src.api.main import create_app
from src.db.dialect import upsert
from src.db.models import FxCoverage, FxRate, Stock, StockCoverage, StockDividend, StockPrice
from src.db.session import get_session

D = dt.date.fromisoformat
DAYS = ["2021-08-02", "2021-09-01", "2021-09-02", "2021-09-03", "2021-10-01"]
STOCKS = [("KRX", "005930.KS", "삼성전자", "KRW", "10000", "1000"),
          ("NASDAQ", "AAPL", "Apple Inc.", "USD", "100", "10")]


@pytest.fixture
async def client(session_factory):
    async with session_factory() as s:
        for market, symbol, name, currency, price, dividend in STOCKS:
            await upsert(s, Stock, [{"market": market, "symbol": symbol, "name": name,
                                     "currency": currency,
                                     "first_available_date": D("1980-12-12")}])
            await s.commit()
            stock_id = int((await s.execute(
                select(Stock.id).where(Stock.symbol == symbol))).scalar_one())
            await upsert(s, StockPrice, [{
                "stock_id": stock_id, "quote_date": D(d), "open_raw": Decimal(price),
                "close_raw": Decimal(price), "close_adjusted": Decimal(price),
                "source": "yahoo:chart"} for d in DAYS])
            await upsert(s, StockDividend, [{
                "stock_id": stock_id, "ex_date": D("2021-09-01"),
                "amount_per_share": Decimal(dividend), "source": "yahoo:chart"}])
            await upsert(s, StockCoverage, [{
                "stock_id": stock_id, "covered_from": D("2021-08-01"),
                "covered_through": D("2021-10-31")}], preserve=())
        await upsert(s, FxRate, [{
            "currency_code": "USD", "quote_date": D(d), "base_rate": Decimal("1150"),
            "quote_unit": 1, "source": "ECOS:731Y001", "is_provisional": False} for d in DAYS])
        await upsert(s, FxCoverage, [{
            "currency_code": "USD", "covered_from": D("2021-07-01"),
            "covered_through": D("2021-10-31")}], preserve=())
        await s.commit()

    app = create_app()

    async def _override():
        async with session_factory() as s:
            yield s

    app.dependency_overrides[get_session] = _override
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


def params(market: str, symbol: str, currency: str) -> dict[str, str]:
    # 원금 통화 = 종목 통화 — 환전 없이 세율만 본다.
    return {"market": market, "symbol": symbol, "start": "2021-08-01",
            "principal": "1000000" if currency == "KRW" else "10000",
            "principalCurrency": currency, "reinvest": "false", "end": "2021-10-31",
            "limit": "50"}


async def condition(client: AsyncClient, market: str, symbol: str, currency: str) -> dict:
    res = await client.get("/api/stocks/simulation", params=params(market, symbol, currency))
    assert res.status_code == 200, res.text
    body: dict = res.json()
    return body["condition"]


class Test시장으로_세율을_고른다:
    async def test_기본값은_국내_15점4_해외_15다(self, client) -> None:
        assert (await condition(client, "KRX", "005930.KS", "KRW"))["dividendTaxRate"] == (
            "0.154000")
        assert (await condition(client, "NASDAQ", "AAPL", "USD"))["dividendTaxRate"] == (
            "0.150000")

    async def test_바꾼_값이_시장별로_적용된다(self, client) -> None:
        res = await client.put("/api/stocks/settings", json={
            "tradeFeeRate": "0.000150", "dividendTaxRateDomestic": "0.200000",
            "dividendTaxRateForeign": "0.100000"})
        assert res.status_code == 200, res.text
        assert (await condition(client, "KRX", "005930.KS", "KRW"))["dividendTaxRate"] == (
            "0.200000")
        assert (await condition(client, "NASDAQ", "AAPL", "USD"))["dividendTaxRate"] == (
            "0.100000")

    async def test_해외_세율이_세후_배당에_쓰인다(self, client) -> None:
        """조건에 싣기만 하고 계산은 다른 세율로 하면 표시와 결과가 어긋난다."""
        await client.put("/api/stocks/settings", json={
            "tradeFeeRate": "0", "dividendTaxRateDomestic": "0.500000",
            "dividendTaxRateForeign": "0.100000"})
        body = (await client.get("/api/stocks/simulation",
                                 params=params("NASDAQ", "AAPL", "USD"))).json()
        start = next(r for r in body["rows"] if r["date"] == "2021-08-02")
        dividend = next(r for r in body["rows"] if r["kind"] == "dividend")
        # 100주 × 10달러 × (1 - 0.1) = 900달러가 예수금에 더해진다(국내 세율 0.5였다면 500).
        assert Decimal(dividend["cash"]) - Decimal(start["cash"]) == Decimal("900")
