"""고른 대상의 상장일 경로 (014 반복 2026-10-10g T168) — FR-034, SC-019, contracts A11.

주식·가상자산 메뉴의 **고른 줄**(검색 칸 아래)이 읽는다. 고른 줄이 생기는 길은 등록과 이력 다시
실행(등록 없음 — 010) 둘이라, 등록 응답이 아니라 대상으로 묻는 경로다(사용자 보고 2026-10-10 — QLD를
고른 줄에 상장일이 없었다).

- `GET /api/stocks/listing-date?market=&symbol=` — 비교 블록 `listing`(A10)과 **같은 규칙**:
  키움 상장일 → 첫 거래일, 둘 다 없으면 한 번 받아 둔다(실패해도 200 `listing: null`). 미국은
  티커로 찾는다(006 FR-030a). 없는 종목은 404 — 등록하지 않는다
- `GET /api/crypto/listing-date?coinId=` — 수집으로 알게 된 첫 일봉. 모르면 `null`, 없는 코인
  404. 출처를 부르지 않는다
"""
from __future__ import annotations

import datetime as dt

import pytest
from sqlalchemy import func, select

from src.db.models import Stock
from src.ingestion.yahoo.errors import StockSourceUnavailable
from tests.integration.comparison_support import AAPL_KRW, KRX, http, seed_stocks
from tests.integration.crypto_support import add_coin
from tests.integration.listing_support import KOSPI_ROWS, reset_listing_state, seed
from tests.integration.test_listing_date_api import (
    compare,
    listing,
    lookup_http,
    set_first_trade,
)
from tests.integration.test_stock_first_trade import FirstTradeStub

D = dt.date.fromisoformat
STOCK = "/api/stocks/listing-date"
COIN = "/api/crypto/listing-date"
SAMSUNG = {"market": "KRX", "symbol": "005930.KS"}
AAPL = {"market": "NASDAQ", "symbol": "AAPL"}


@pytest.fixture(autouse=True)
def _listing_state():  # type: ignore[no-untyped-def]
    reset_listing_state()
    yield
    reset_listing_state()


async def stored_first_trade(session_factory, symbol: str) -> dt.date | None:  # type: ignore[no-untyped-def]
    async with session_factory() as s:
        day: dt.date | None = (await s.execute(
            select(Stock.first_trade_date).where(Stock.symbol == symbol))).scalar_one()
        return day


class Test주식:
    async def test_국내는_키움_상장일이고_출처를_부르지_않는다(self, session_factory) -> None:  # type: ignore[no-untyped-def]
        await seed_stocks(session_factory)
        await seed(session_factory, "KOSPI", KOSPI_ROWS)
        stub = FirstTradeStub()
        async with lookup_http(session_factory, stub) as client:
            res = await client.get(STOCK, params=SAMSUNG)
        assert res.status_code == 200, res.text
        assert res.json() == {"market": "KRX", "symbol": "005930.KS",
                              "listing": {"date": "1975-06-11", "basis": "listing"}}
        assert stub.calls == []

    async def test_미국은_저장된_첫_거래일이고_출처를_부르지_않는다(self, session_factory) -> None:  # type: ignore[no-untyped-def]
        await seed_stocks(session_factory)
        await set_first_trade(session_factory, "AAPL", D("1980-12-12"))
        stub = FirstTradeStub()
        async with lookup_http(session_factory, stub) as client:
            body = (await client.get(STOCK, params=AAPL)).json()
        assert body["listing"] == {"date": "1980-12-12", "basis": "first_trade"}
        assert stub.calls == []

    async def test_모르면_한_번_받아_두고_다시_부르지_않는다(self, session_factory) -> None:  # type: ignore[no-untyped-def]
        """이력 다시 실행은 등록을 거치지 않는다.

        고른 줄이 묻는 이때 받아 둬야 줄이 빈 채로 남지 않는다.
        """
        await seed_stocks(session_factory)
        stub = FirstTradeStub(D("1980-12-12"))
        async with lookup_http(session_factory, stub) as client:
            first = (await client.get(STOCK, params=AAPL)).json()
            second = (await client.get(STOCK, params=AAPL)).json()
        expected = {"date": "1980-12-12", "basis": "first_trade"}
        assert (first["listing"], second["listing"]) == (expected, expected)
        assert stub.calls == ["AAPL"]
        assert await stored_first_trade(session_factory, "AAPL") == D("1980-12-12")

    async def test_못_받으면_200_null이다(self, session_factory) -> None:  # type: ignore[no-untyped-def]
        await seed_stocks(session_factory)
        stub = FirstTradeStub(error=StockSourceUnavailable("출처 장애"))
        async with lookup_http(session_factory, stub) as client:
            res = await client.get(STOCK, params=AAPL)
        assert res.status_code == 200
        assert res.json()["listing"] is None
        assert await stored_first_trade(session_factory, "AAPL") is None

    async def test_시작일_하한으로_메우지_않는다(self, session_factory) -> None:  # type: ignore[no-untyped-def]
        """공유 클라이언트가 없으면(lifespan 밖) 받지 않는다.

        `first_available_date`(1980-12-12)는 상장일이 아니다.
        """
        await seed_stocks(session_factory)
        async with http(session_factory) as client:
            body = (await client.get(STOCK, params=AAPL)).json()
        assert body["listing"] is None

    async def test_미국은_다른_거래소로_등록된_같은_티커를_찾는다(self, session_factory) -> None:  # type: ignore[no-untyped-def]
        await seed_stocks(session_factory)
        await set_first_trade(session_factory, "AAPL", D("1980-12-12"))
        async with http(session_factory) as client:
            body = (await client.get(STOCK, params={"market": "NYSE", "symbol": "AAPL"})).json()
        assert (body["market"], body["symbol"]) == ("NASDAQ", "AAPL")
        assert body["listing"] == {"date": "1980-12-12", "basis": "first_trade"}

    async def test_없는_종목은_404이고_등록하지_않는다(self, session_factory) -> None:  # type: ignore[no-untyped-def]
        await seed_stocks(session_factory)
        async with session_factory() as s:
            before = (await s.execute(select(func.count()).select_from(Stock))).scalar_one()
        async with http(session_factory) as client:
            res = await client.get(STOCK, params={"market": "KRX", "symbol": "999999.KS"})
        assert res.status_code == 404
        assert res.json()["status"] == "unknown_stock"
        async with session_factory() as s:
            after = (await s.execute(select(func.count()).select_from(Stock))).scalar_one()
        assert after == before

    async def test_빠진_질의는_422다(self, session_factory) -> None:  # type: ignore[no-untyped-def]
        async with http(session_factory) as client:
            res = await client.get(STOCK, params={"market": "KRX"})
        assert res.status_code == 422

    async def test_비교_블록과_같은_글자다(self, session_factory) -> None:  # type: ignore[no-untyped-def]
        """같은 대상이면 고른 줄과 비교 표가 같은 날짜·기준이다(SC-019)."""
        await seed_stocks(session_factory)
        await seed(session_factory, "KOSPI", KOSPI_ROWS)
        await set_first_trade(session_factory, "AAPL", D("1980-12-12"))
        async with http(session_factory) as client:
            mine = [(await client.get(STOCK, params=p)).json()["listing"] for p in (SAMSUNG, AAPL)]
        theirs = [listing(await compare(session_factory, "/api/comparison/stocks/simulation", p))
                  for p in (KRX, AAPL_KRW)]
        assert mine == theirs


class Test가상자산:
    async def test_첫_일봉이다(self, session_factory) -> None:  # type: ignore[no-untyped-def]
        coin_id = await add_coin(session_factory, first_available=D("2010-07-18"))
        async with http(session_factory) as client:
            res = await client.get(COIN, params={"coinId": str(coin_id)})
        assert res.status_code == 200, res.text
        assert res.json() == {"coinId": coin_id,
                              "listing": {"date": "2010-07-18", "basis": "first_bar"}}

    async def test_모르면_null이다(self, session_factory) -> None:  # type: ignore[no-untyped-def]
        coin_id = await add_coin(session_factory, "999999", "XYZ", "Unknown Coin", name_ko=None)
        async with http(session_factory) as client:
            body = (await client.get(COIN, params={"coinId": str(coin_id)})).json()
        assert body == {"coinId": coin_id, "listing": None}

    async def test_없는_코인은_404다(self, session_factory) -> None:  # type: ignore[no-untyped-def]
        async with http(session_factory) as client:
            res = await client.get(COIN, params={"coinId": "424242"})
        assert res.status_code == 404
        assert res.json()["status"] == "unknown_coin"

    async def test_정수가_아니면_422다(self, session_factory) -> None:  # type: ignore[no-untyped-def]
        async with http(session_factory) as client:
            res = await client.get(COIN, params={"coinId": "btc"})
        assert res.status_code == 422
