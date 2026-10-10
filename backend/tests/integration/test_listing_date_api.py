"""검색 응답·비교 블록의 상장일 (014 반복 2026-10-10f T159) — FR-033, SC-018, contracts A10.

- 검색 응답 둘(`/api/stocks/search`·`/external`)의 행에 `firstTradedOn` — 저장된 종목의 Yahoo 첫
  거래일만 싣는다. **검색은 출처를 부르지 않는다**(결과마다 부르면 요청 제한이 주식 수집을 막는다).
  `listedOn`(키움 국내 상장일)은 그대로다
- 미국 종목은 **티커로** 찾는다 — 목록 출처와 시세 출처의 거래소가 다를 수 있다(006 FR-030a)
- 비교 블록 `listing{date, basis}` — 주식 `listing`(키움) → `first_trade`(Yahoo) → `null`, 코인
  `first_bar` → `null`
- 메뉴 시뮬레이션 응답은 바뀌지 않는다
"""
from __future__ import annotations

import datetime as dt

import pytest
from httpx2 import ASGITransport, AsyncClient
from sqlalchemy import update

from src.api.main import create_app
from src.api.routes import stock_search, stock_selection
from src.api.services.stock_selection import FirstTradeLookup
from src.db.dialect import upsert
from src.db.models import Stock
from src.db.session import get_session
from src.ingestion.yahoo.parse import StockQuote
from src.worker.listing_queue import ListingQueue
from tests.integration.comparison_support import AAPL_KRW, KRX, http, seed_stocks
from tests.integration.crypto_support import add_coin, seed_daily, seed_usd
from tests.integration.listing_support import (
    APPLE,
    KOSPI_ROWS,
    NOW,
    SPY,
    listing_settings,
    reset_listing_state,
    seed,
    seed_us,
)
from tests.integration.test_stock_first_trade import FirstTradeStub

D = dt.date.fromisoformat


@pytest.fixture(autouse=True)
def _listing_state():  # type: ignore[no-untyped-def]
    reset_listing_state()
    yield
    reset_listing_state()


class SearchStub:
    def __init__(self, results: list[StockQuote]) -> None:
        self._results = results

    async def search(self, query: str, limit: int):  # type: ignore[no-untyped-def]
        return self._results[:limit], "{}", 200

    async def __aenter__(self):  # type: ignore[no-untyped-def]
        return self

    async def __aexit__(self, *_: object) -> None:
        return None


TOYOTA = StockQuote("TSE", "7203.T", "Toyota Motor Corporation", "JPY")
SONY = StockQuote("TSE", "6758.T", "Sony Group Corporation", "JPY")


@pytest.fixture
async def search_client(session_factory):  # type: ignore[no-untyped-def]
    await seed(session_factory, "KOSPI", KOSPI_ROWS)
    await seed_us(session_factory, "NYSE", [SPY])
    await seed_us(session_factory, "NASDAQ", [APPLE])
    async with session_factory() as s:
        await upsert(s, Stock, [
            {"market": "KRX", "symbol": "005930.KS", "name": "삼성전자", "currency": "KRW",
             "first_trade_date": D("2000-01-04")},
            # 시세 출처의 거래소(AMEX)가 목록(NYSE)과 다르다 — 티커로 찾아야 한다
            {"market": "AMEX", "symbol": "SPY", "name": "S&P 500 SPDR ETF", "currency": "USD",
             "first_trade_date": D("1993-01-29")},
            {"market": "TSE", "symbol": "7203.T", "name": "Toyota Motor Corporation",
             "currency": "JPY",
             "first_trade_date": D("1999-05-06")},
        ])
        await s.commit()
    app = create_app()

    async def _override():  # type: ignore[no-untyped-def]
        async with session_factory() as s:
            yield s

    stub = FirstTradeStub()
    app.dependency_overrides[get_session] = _override
    app.dependency_overrides[stock_search.get_now] = lambda: NOW
    app.dependency_overrides[stock_search.get_listing_settings] = listing_settings
    app.dependency_overrides[stock_search.get_listing_queue] = ListingQueue
    app.dependency_overrides[stock_search.get_source] = lambda: SearchStub([TOYOTA, SONY])
    app.dependency_overrides[stock_selection.get_first_trade] = lambda: FirstTradeLookup(stub, 3.0)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac, stub


async def first_row(client: AsyncClient, q: str) -> dict[str, object]:
    body = (await client.get("/api/stocks/search", params={"q": q})).json()
    row: dict[str, object] = body["results"][0]
    return row


class Test검색:
    async def test_국내는_키움_상장일과_저장된_첫_거래일을_함께_싣는다(self, search_client) -> None:  # type: ignore[no-untyped-def]
        client, _ = search_client
        row = await first_row(client, "삼성전자")
        assert (row["listedOn"], row["firstTradedOn"]) == ("1975-06-11", "2000-01-04")

    async def test_미국은_티커로_찾은_첫_거래일이다(self, search_client) -> None:  # type: ignore[no-untyped-def]
        client, _ = search_client
        row = await first_row(client, "SPY")
        assert (row["listedOn"], row["firstTradedOn"]) == (None, "1993-01-29")

    async def test_한_번도_고르지_않은_종목은_null이다(self, search_client) -> None:  # type: ignore[no-untyped-def]
        client, _ = search_client
        row = await first_row(client, "애플")
        assert "firstTradedOn" in row and row["firstTradedOn"] is None

    async def test_외부_검색도_저장된_것만이다(self, search_client) -> None:  # type: ignore[no-untyped-def]
        client, _ = search_client
        body = (await client.get("/api/stocks/search/external", params={"q": "toyota"})).json()
        assert [(r["symbol"], r["firstTradedOn"]) for r in body["results"]] == [
            ("7203.T", "1999-05-06"), ("6758.T", None)]

    async def test_검색은_출처를_부르지_않는다(self, search_client) -> None:  # type: ignore[no-untyped-def]
        client, stub = search_client
        for q in ("삼성전자", "SPY", "애플"):
            await client.get("/api/stocks/search", params={"q": q})
        await client.get("/api/stocks/search/external", params={"q": "toyota"})
        assert stub.calls == []


async def set_first_trade(session_factory, symbol: str, day: dt.date) -> None:  # type: ignore[no-untyped-def]
    async with session_factory() as s:
        await s.execute(update(Stock).where(Stock.symbol == symbol).values(first_trade_date=day))
        await s.commit()


async def compare(session_factory, path: str, params: dict[str, str]) -> dict[str, object]:  # type: ignore[no-untyped-def]
    async with http(session_factory) as client:
        res = await client.get(path, params=params)
    assert res.status_code == 200, res.text
    body: dict[str, object] = res.json()
    return body


def listing(body: dict[str, object]) -> object:
    block = body["comparison"]
    assert isinstance(block, dict)
    return block["listing"]


class Test비교_주식:
    async def test_국내는_키움_상장일이다(self, session_factory) -> None:  # type: ignore[no-untyped-def]
        await seed_stocks(session_factory)
        await seed(session_factory, "KOSPI", KOSPI_ROWS)
        await set_first_trade(session_factory, "005930.KS", D("2000-01-04"))
        body = await compare(session_factory, "/api/comparison/stocks/simulation", KRX)
        assert listing(body) == {"date": "1975-06-11", "basis": "listing"}

    async def test_목록에_상장일이_없으면_Yahoo_첫_거래일이다(self, session_factory) -> None:  # type: ignore[no-untyped-def]
        await seed_stocks(session_factory)
        await set_first_trade(session_factory, "AAPL", D("1980-12-12"))
        body = await compare(session_factory, "/api/comparison/stocks/simulation", AAPL_KRW)
        assert listing(body) == {"date": "1980-12-12", "basis": "first_trade"}

    async def test_모르면_null이다_시작일_하한으로_메우지_않는다(self, session_factory) -> None:  # type: ignore[no-untyped-def]
        """`seed_stocks`의 AAPL은 `first_available_date`(1980-12-12)가 있다.

        그것은 시작일 하한이다 — 상장일로 쓰지 않는다.
        """
        await seed_stocks(session_factory)
        body = await compare(session_factory, "/api/comparison/stocks/simulation", AAPL_KRW)
        assert listing(body) is None

    async def test_메뉴_응답은_그대로다(self, session_factory) -> None:  # type: ignore[no-untyped-def]
        await seed_stocks(session_factory)
        await set_first_trade(session_factory, "AAPL", D("1980-12-12"))
        async with http(session_factory) as client:
            menu = (await client.get("/api/stocks/simulation", params=AAPL_KRW)).json()
        assert "listing" not in menu and "firstTradedOn" not in str(menu)


@pytest.fixture
async def coins(session_factory):  # type: ignore[no-untyped-def]
    known = await add_coin(session_factory, first_available=D("2010-07-18"))
    unknown = await add_coin(session_factory, "999999", "XYZ", "Unknown Coin", name_ko=None)
    for coin_id in (known, unknown):
        await seed_daily(session_factory, coin_id, "btc_2020_2021.json",
                         covered=(D("2020-01-01"), D("2021-12-31")))
    await seed_usd(session_factory, D("2019-12-01"), D("2022-12-31"))
    return known, unknown


CRYPTO = {"start": "2020-01-15", "principal": "10000000", "principalCurrency": "KRW",
          "end": "2021-12-31"}
CRYPTO_RECURRING = {"start": "2020-01-15", "amount": "100000", "principalCurrency": "KRW",
                    "frequency": "monthly", "end": "2021-12-31"}


class Test비교_가상자산:
    async def test_첫_일봉이다(self, session_factory, coins) -> None:  # type: ignore[no-untyped-def]
        known, _ = coins
        for path, params in (("/api/comparison/crypto/simulation", CRYPTO),
                             ("/api/comparison/crypto/recurring-simulation", CRYPTO_RECURRING)):
            body = await compare(session_factory, path, {**params, "coinId": str(known)})
            assert listing(body) == {"date": "2010-07-18", "basis": "first_bar"}

    async def test_모르면_null이다(self, session_factory, coins) -> None:  # type: ignore[no-untyped-def]
        _, unknown = coins
        body = await compare(session_factory, "/api/comparison/crypto/simulation",
                             {**CRYPTO, "coinId": str(unknown)})
        assert listing(body) is None
