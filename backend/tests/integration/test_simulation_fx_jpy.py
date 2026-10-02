"""엔화 종목·원화 원금 (T046) — 006 FR-040, FR-041, FR-042, SC-009.

`exchange.rate`와 행의 `fxRate`는 **1엔당** 원화 값이다. 첫 환전은 **실제 첫 매수일**의 환율이다 —
시작일이 휴일이어도 시작일 환율을 쓰지 않는다(돈은 살 때 바꾼다).
"""
from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest
from httpx2 import ASGITransport, AsyncClient
from sqlalchemy import select

from src.api.main import create_app
from src.db.dialect import upsert
from src.db.models import FxCoverage, FxRate, Stock, StockCoverage, StockPrice
from src.db.session import get_session

D = dt.date.fromisoformat
DAYS = ["2021-08-02", "2021-09-01", "2021-10-01"]
#: 100엔당 원화. 7월 30일(금)은 시작일 8월 1일(일)의 "가장 가까운 이전 고시일"이다.
FX = {"2021-07-30": "1050.00", "2021-08-02": "1045.00", "2021-09-01": "1060.00",
      "2021-10-01": "1020.00"}


@pytest.fixture
async def client(session_factory):  # type: ignore[no-untyped-def]
    async with session_factory() as s:
        await upsert(s, Stock, [{
            "market": "TSE", "symbol": "7203.T", "name": "Toyota Motor Corporation",
            "currency": "JPY", "first_available_date": D("1990-01-04")}])
        await s.commit()
        stock_id = int((await s.execute(select(Stock))).scalar_one().id)
        await upsert(s, StockPrice, [{
            "stock_id": stock_id, "quote_date": D(d),
            "open_raw": Decimal("1000"), "close_raw": Decimal("1000"),
            "close_adjusted": Decimal("1000"), "source": "yahoo:chart"} for d in DAYS])
        await upsert(s, StockCoverage, [{
            "stock_id": stock_id, "covered_from": D("2021-08-01"),
            "covered_through": D("2021-10-31")}], preserve=())
        await upsert(s, FxRate, [{
            "currency_code": "JPY", "quote_date": D(d), "base_rate": Decimal(v),
            "quote_unit": 100, "source": "ECOS:731Y001", "is_provisional": False}
            for d, v in FX.items()])
        # 이미 수집을 마친 상태를 흉내낸다 — 커버리지가 없으면 환율 수집 중(202)이다.
        await upsert(s, FxCoverage, [{
            "currency_code": "JPY", "covered_from": D("2021-07-01"),
            "covered_through": D("2021-10-31")}], preserve=())
        await s.commit()

    app = create_app()

    async def _override():  # type: ignore[no-untyped-def]
        async with session_factory() as s:
            yield s

    app.dependency_overrides[get_session] = _override
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


PARAMS = {"market": "TSE", "symbol": "7203.T", "start": "2021-08-01", "end": "2021-10-31",
          "principal": "1000000", "principalCurrency": "KRW", "reinvest": "true",
          "limit": "50"}


async def fetch(client: AsyncClient) -> dict:  # type: ignore[type-arg]
    res = await client.get("/api/stocks/simulation", params=PARAMS)
    assert res.status_code == 200, res.text
    return res.json()


class Test고시_단위:
    async def test_환전_환율은_1엔당_값이다(self, client) -> None:
        """FR-042 — 100엔당 1,045원 → 1엔당 10.45원에 현금 살 때 가산."""
        rate = Decimal((await fetch(client))["exchange"]["rate"])
        assert Decimal("10.45") < rate < Decimal("10.50")

    async def test_행의_평가_환율도_1엔당_값이다(self, client) -> None:
        rows = {r["date"]: r for r in (await fetch(client))["rows"]}
        assert rows["2021-09-01"]["fxRate"] == "10.600000"
        assert rows["2021-10-01"]["fxRate"] == "10.200000"

    async def test_한_주도_못_사는_일이_없다(self, client) -> None:
        """SC-009 — 단위를 버리면 1,000,000원이 약 955엔이 되어 1,000엔짜리를 살 수 없다."""
        rows = (await fetch(client))["rows"]
        first = rows[-1]                     # 최신순 — 마지막이 첫 매수 행이다
        assert first["date"] == "2021-08-02"
        assert first["boughtShares"] >= 90


class Test첫_매수일의_환율:
    async def test_시작일이_휴일이어도_첫_매수일의_환율이다(self, client) -> None:
        """FR-041 — 시작일(일요일)의 가장 가까운 이전 고시일(7월 30일)을 쓰지 않는다."""
        exchange = (await fetch(client))["exchange"]
        assert exchange["rateDate"] == "2021-08-02"

    async def test_평가는_매매기준율이다(self, client) -> None:
        """FR-040 — 평가에 현금 살 때 가산을 얹으면 잔고가 실제보다 크게 나온다."""
        body = await fetch(client)
        rows = {r["date"]: r for r in body["rows"]}
        assert Decimal(rows["2021-08-02"]["fxRate"]) == Decimal("10.45")
        assert Decimal(body["exchange"]["rate"]) > Decimal(rows["2021-08-02"]["fxRate"])
