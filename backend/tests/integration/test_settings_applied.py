"""설정이 결과에 반영된다 (T057) — 005 FR-017, FR-018, SC-007, SC-008.

갱신되지 않으면 화면은 정상으로 보이면서 낡은 값을 보여주고, 사용자는 새 설정이
반영된 결과로 읽는다 (002 FR-034와 같은 계열).

006 FR-055(반복 2026-10-03 #3, T126) — 설정 API의 세율이 국내·해외 두 값이 되었다. 이 파일의 종목은
국내(KRX)라 국내 세율(`dividendTaxRateDomestic`)이 적용된다. 응답 조건의 `dividendTaxRate`는
**적용한 세율**이다.
"""
from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest
from httpx2 import ASGITransport, AsyncClient
from sqlalchemy import select

from src.api.main import create_app
from src.db.dialect import upsert
from src.db.models import Stock, StockCoverage, StockDividend, StockPrice
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
        # 픽스처는 "이미 수집을 마친 상태"를 흉내낸다. 커버리지를 적지 않으면
        # 요청 구간이 미수집으로 판정돼 202가 돌아간다 (FR-047).
        await upsert(s, StockCoverage, [{
            "stock_id": stock_id, "covered_from": D("2021-08-01"),
            "covered_through": D("2021-10-31")}], preserve=())
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
            "tradeFeeRate": "0.000150", "dividendTaxRateDomestic": "0",
            "dividendTaxRateForeign": "0.150000"})
        after = await dividend_cash(client)
        assert after > before

    async def test_수수료를_바꾸면_보유_주식이_달라진다(self, client) -> None:
        body = (await client.get("/api/stocks/simulation", params=PARAMS)).json()
        before = body["rows"][0]["heldShares"]

        await client.put("/api/stocks/settings", json={
            "tradeFeeRate": "0.5", "dividendTaxRateDomestic": "0.154000",
            "dividendTaxRateForeign": "0.150000"})
        body = (await client.get("/api/stocks/simulation", params=PARAMS)).json()
        assert body["rows"][0]["heldShares"] < before

    async def test_저장할_캐시가_없어_즉시_반영된다(self, client) -> None:
        """결과를 저장하지 않으므로(research R5-9) 무효화할 캐시도 없다."""
        await client.put("/api/stocks/settings", json={
            "tradeFeeRate": "0", "dividendTaxRateDomestic": "0",
            "dividendTaxRateForeign": "0.150000"})
        first = await dividend_cash(client)
        await client.put("/api/stocks/settings", json={
            "tradeFeeRate": "0", "dividendTaxRateDomestic": "0.5",
            "dividendTaxRateForeign": "0.150000"})
        assert await dividend_cash(client) < first


class Test적용_조건_표시:
    async def test_응답에_적용된_수수료율과_세율이_실린다(self, client) -> None:
        """FR-018, SC-008 — 설정은 바뀌므로 값만 남으면 어느 조건의 결과인지 모른다."""
        body = (await client.get("/api/stocks/simulation", params=PARAMS)).json()
        assert body["condition"]["tradeFeeRate"] == "0.000150"
        assert body["condition"]["dividendTaxRate"] == "0.154000"

    async def test_설정을_바꾸면_실린_값도_바뀐다(self, client) -> None:
        await client.put("/api/stocks/settings", json={
            "tradeFeeRate": "0.000300", "dividendTaxRateDomestic": "0.220000",
            "dividendTaxRateForeign": "0.150000"})
        body = (await client.get("/api/stocks/simulation", params=PARAMS)).json()
        assert body["condition"]["tradeFeeRate"] == "0.000300"
        assert body["condition"]["dividendTaxRate"] == "0.220000"
