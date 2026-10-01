"""환전이 없는 경우 (T071) — 005 FR-023, contracts/rest-api 오류표."""
from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest
from httpx2 import ASGITransport, AsyncClient
from sqlalchemy import select

from src.api.main import create_app
from src.db.dialect import upsert
from src.db.models import Stock, StockCoverage, StockPrice
from src.db.session import get_session

D = dt.date.fromisoformat


@pytest.fixture
async def client(session_factory):
    async with session_factory() as s:
        await upsert(s, Stock, [
            {"market": "KRX", "symbol": "005930.KS", "name": "삼성전자",
             "currency": "KRW", "first_available_date": D("1975-06-11")},
            {"market": "NASDAQ", "symbol": "AAPL", "name": "Apple Inc.",
             "currency": "USD", "first_available_date": D("1980-12-12")}])
        await s.commit()
        for symbol in ("005930.KS", "AAPL"):
            stock_id = int((await s.execute(
                select(Stock).where(Stock.symbol == symbol))).scalar_one().id)
            await upsert(s, StockPrice, [{
                "stock_id": stock_id, "quote_date": D(d),
                "open_raw": Decimal("100"), "close_raw": Decimal("100"),
                "close_adjusted": Decimal("100"), "source": "yahoo:chart"}
                for d in ("2021-08-02", "2021-09-01")])
            # 픽스처는 "이미 수집을 마친 상태"를 흉내낸다. 커버리지를 적지 않으면
            # 요청 구간이 미수집으로 판정돼 202가 돌아간다 (FR-047).
            # **두 종목 모두 적는다** — 하나만 적으면 다른 종목만 202가 되어,
            # 실패가 통화 처리 문제인 것처럼 보인다.
            await upsert(s, StockCoverage, [{
                "stock_id": stock_id, "covered_from": D("2021-08-01"),
                "covered_through": D("2021-09-30")}], preserve=())
        await s.commit()

    app = create_app()

    async def _override():
        async with session_factory() as s:
            yield s

    app.dependency_overrides[get_session] = _override
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


BASE = {"start": "2021-08-01", "principal": "1000000", "reinvest": "true",
        "end": "2021-09-30", "limit": "50"}


class Test같은_통화:
    async def test_환전이_일어나지_않는다(self, client) -> None:
        """FR-023."""
        body = (await client.get("/api/stocks/simulation", params={
            **BASE, "market": "KRX", "symbol": "005930.KS",
            "principalCurrency": "KRW"})).json()
        assert "exchange" not in body

    async def test_행에_환율이_실리지_않는다(self, client) -> None:
        """정상 상태에 값을 두면 화면이 존재 여부가 아니라 내용을 검사해야 한다."""
        body = (await client.get("/api/stocks/simulation", params={
            **BASE, "market": "KRX", "symbol": "005930.KS",
            "principalCurrency": "KRW"})).json()
        assert all("fxRate" not in r for r in body["rows"])


class Test환율이_없을_때:
    async def test_환산할_수_없으면_409다(self, client) -> None:
        """값을 만들어내지 않는다. 환산할 수 없다는 사실이 드러나야 한다 (원칙 V)."""
        res = await client.get("/api/stocks/simulation", params={
            **BASE, "market": "NASDAQ", "symbol": "AAPL",
            "principalCurrency": "KRW"})
        assert res.status_code == 409
        assert res.json()["status"] == "fx_unavailable"

    async def test_빈_표를_주지_않는다(self, client) -> None:
        res = await client.get("/api/stocks/simulation", params={
            **BASE, "market": "NASDAQ", "symbol": "AAPL",
            "principalCurrency": "KRW"})
        assert "rows" not in res.json()
