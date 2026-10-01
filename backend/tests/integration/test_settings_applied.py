"""설정이 결과에 반영된다 (T057) — 005 FR-017, FR-018, SC-007, SC-008.

갱신되지 않으면 화면은 정상으로 보이면서 낡은 값을 보여주고, 사용자는 새 설정이
반영된 결과로 읽는다 (002 FR-034와 같은 계열).
"""
from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest
from httpx2 import ASGITransport, AsyncClient
from sqlalchemy import select

from src.api.main import create_app
from src.db.dialect import upsert
from src.db.models import Stock, StockDividend, StockPrice
from src.db.session import get_session

D = dt.date.fromisoformat
DAYS = ["2021-08-02", "2021-09-01", "2021-10-01"]


@pytest.fixture
async def client(session_factory):
    async with session_factory() as s:
        await upsert(s, Stock, [{
            "market": "KRX", "symbol": "005930.KS", "name": "삼성전자",
            "currency": "KRW", "first_available_date": D("1975-06-11")}])
        await s.commit()
        stock_id = int((await s.execute(select(Stock))).scalar_one().id)
        await upsert(s, StockPrice, [{
            "stock_id": stock_id, "quote_date": D(d),
            "open_raw": Decimal("10000"), "close_raw": Decimal("10000"),
            "close_adjusted": Decimal("10000"), "source": "yahoo:chart"}
            for d in DAYS])
        await upsert(s, StockDividend, [{
            "stock_id": stock_id, "ex_date": D("2021-09-01"),
            "amount_per_share": Decimal("1000"), "source": "yahoo:chart"}])
        await s.commit()

    app = create_app()

    async def _override():
        async with session_factory() as s:
            yield s

    app.dependency_overrides[get_session] = _override
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


PARAMS = {"market": "KRX", "symbol": "005930.KS", "start": "2021-08-01",
          "principal": "100000", "principalCurrency": "KRW", "reinvest": "false",
          "end": "2021-10-31", "limit": "50"}


async def dividend_cash(client: AsyncClient) -> Decimal:
    body = (await client.get("/api/stocks/simulation", params=PARAMS)).json()
    row = next(r for r in body["rows"] if r["kind"] == "dividend")
    return Decimal(row["cash"])


class Test설정_변경_반영:
    async def test_세율을_바꾸면_결과가_달라진다(self, client) -> None:
        """FR-017, SC-007."""
        before = await dividend_cash(client)
        await client.put("/api/stocks/settings", json={
            "tradeFeeRate": "0.000150", "dividendTaxRate": "0"})
        after = await dividend_cash(client)
        assert after > before

    async def test_수수료를_바꾸면_보유_주식이_달라진다(self, client) -> None:
        body = (await client.get("/api/stocks/simulation", params=PARAMS)).json()
        before = body["rows"][0]["heldShares"]

        await client.put("/api/stocks/settings", json={
            "tradeFeeRate": "0.5", "dividendTaxRate": "0.154000"})
        body = (await client.get("/api/stocks/simulation", params=PARAMS)).json()
        assert body["rows"][0]["heldShares"] < before

    async def test_저장할_캐시가_없어_즉시_반영된다(self, client) -> None:
        """결과를 저장하지 않으므로(research R5-9) 무효화할 캐시도 없다."""
        await client.put("/api/stocks/settings", json={
            "tradeFeeRate": "0", "dividendTaxRate": "0"})
        first = await dividend_cash(client)
        await client.put("/api/stocks/settings", json={
            "tradeFeeRate": "0", "dividendTaxRate": "0.5"})
        assert await dividend_cash(client) < first


class Test적용_조건_표시:
    async def test_응답에_적용된_수수료율과_세율이_실린다(self, client) -> None:
        """FR-018, SC-008 — 설정은 바뀌므로 값만 남으면 어느 조건의 결과인지 모른다."""
        body = (await client.get("/api/stocks/simulation", params=PARAMS)).json()
        assert body["condition"]["tradeFeeRate"] == "0.000150"
        assert body["condition"]["dividendTaxRate"] == "0.154000"

    async def test_설정을_바꾸면_실린_값도_바뀐다(self, client) -> None:
        await client.put("/api/stocks/settings", json={
            "tradeFeeRate": "0.000300", "dividendTaxRate": "0.220000"})
        body = (await client.get("/api/stocks/simulation", params=PARAMS)).json()
        assert body["condition"]["tradeFeeRate"] == "0.000300"
        assert body["condition"]["dividendTaxRate"] == "0.220000"
