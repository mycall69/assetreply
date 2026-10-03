"""응답 행의 배당 소득세·매매 수수료와 재투자 행 (T127) — 006 FR-058, FR-059, SC-024, SC-025,
contracts/rest-api. 반복 2026-10-03 #3.

- `dividendTax`는 배당락 행에, `tradeFee`는 매수가 있는 행(초기 매수 월 행, 재투자 행)에만 있다 —
  해당 없으면 **키가 없다**
- 재투자 매수는 배당락 뒤 2번째 거래일의 `kind: "reinvest"` 행이다
- 금액은 **원금 통화**다 — 원화 원금·달러 종목이면 그 행의 환율로 원화로 바꾼다. 따로 환산하면 같은
  행의 예수금과 어긋난다
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
#: 2021-09-01(수) 배당락 → 09-02(목) 1번째, 09-03(금) 2번째 거래일.
DAYS = ["2021-08-02", "2021-09-01", "2021-09-02", "2021-09-03", "2021-10-01"]
FX = {"2021-08-02": "1150", "2021-09-01": "1160", "2021-09-02": "1165",
      "2021-09-03": "1170", "2021-10-01": "1190"}
FEE = Decimal("0.000150")
TAX_FOREIGN = Decimal("0.150000")


@pytest.fixture
async def client(session_factory):
    async with session_factory() as s:
        await upsert(s, Stock, [{
            "market": "NASDAQ", "symbol": "AAPL", "name": "Apple Inc.",
            "currency": "USD", "first_available_date": D("1980-12-12")}])
        await s.commit()
        stock_id = int((await s.execute(select(Stock))).scalar_one().id)
        await upsert(s, StockPrice, [{
            "stock_id": stock_id, "quote_date": D(d),
            "open_raw": Decimal("100"), "close_raw": Decimal("100"),
            "close_adjusted": Decimal("100"), "source": "yahoo:chart"} for d in DAYS])
        await upsert(s, StockDividend, [{
            "stock_id": stock_id, "ex_date": D("2021-09-01"),
            "amount_per_share": Decimal("150"), "source": "yahoo:chart"}])
        await upsert(s, FxRate, [{
            "currency_code": "USD", "quote_date": D(d), "base_rate": Decimal(v),
            "quote_unit": 1, "source": "ECOS:731Y001", "is_provisional": False}
            for d, v in FX.items()])
        await upsert(s, StockCoverage, [{
            "stock_id": stock_id, "covered_from": D("2021-08-01"),
            "covered_through": D("2021-10-31")}], preserve=())
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


PARAMS = {"market": "NASDAQ", "symbol": "AAPL", "start": "2021-08-01",
          "principal": "1000000", "principalCurrency": "KRW", "reinvest": "true",
          "end": "2021-10-31", "limit": "50"}


async def rows(client: AsyncClient) -> list[dict]:
    res = await client.get("/api/stocks/simulation", params=PARAMS)
    assert res.status_code == 200, res.text
    body: list[dict] = res.json()["rows"]
    return body


def one(all_rows: list[dict], kind: str, date: str | None = None) -> dict:
    [row] = [r for r in all_rows if r["kind"] == kind and (date is None or r["date"] == date)]
    return row


class Test행_종류:
    async def test_배당락_뒤_두_번째_거래일에_재투자_행이_있다(self, client) -> None:
        all_rows = await rows(client)
        reinvest = one(all_rows, "reinvest")
        assert reinvest["date"] == "2021-09-03"
        assert reinvest["boughtShares"] > 0
        # 배당락 행에서는 사지 않는다.
        assert one(all_rows, "dividend")["boughtShares"] == 0


class Test키가_있는_행:
    async def test_배당락_행에만_배당_소득세가_있다(self, client) -> None:
        all_rows = await rows(client)
        assert isinstance(one(all_rows, "dividend")["dividendTax"], str)
        assert all("dividendTax" not in r for r in all_rows if r["kind"] != "dividend")

    async def test_매수가_있는_행에만_매매_수수료가_있다(self, client) -> None:
        all_rows = await rows(client)
        assert isinstance(one(all_rows, "month_first", "2021-08-02")["tradeFee"], str)
        assert isinstance(one(all_rows, "reinvest")["tradeFee"], str)
        assert "tradeFee" not in one(all_rows, "dividend")
        assert "tradeFee" not in one(all_rows, "month_first", "2021-10-01")


class Test원금_통화로_환산:
    async def test_배당_소득세는_그_행의_환율로_원화다(self, client) -> None:
        row = one(await rows(client), "dividend")
        # 배당락 행은 사지 않으므로 보유 수 = 배당이 붙은 수다.
        usd = Decimal(row["heldShares"]) * Decimal(row["dividendPerShare"]) * TAX_FOREIGN
        expected = usd * Decimal(row["fxRate"])
        assert abs(Decimal(row["dividendTax"]) - expected) < Decimal("1")
        assert Decimal(row["fxRate"]) == Decimal("1160")

    async def test_매매_수수료는_그_행의_환율로_원화다(self, client) -> None:
        row = one(await rows(client), "reinvest")
        usd = Decimal(row["boughtShares"]) * Decimal(row["openPrice"]) * FEE
        expected = usd * Decimal(row["fxRate"])
        assert abs(Decimal(row["tradeFee"]) - expected) < Decimal("1")
        assert Decimal(row["fxRate"]) == Decimal("1170")
