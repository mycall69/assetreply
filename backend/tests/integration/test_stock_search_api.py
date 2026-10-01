"""종목 검색 API (T028) — 005 FR-002, FR-002a, FR-002b, FR-002c.

**검색 실패와 "결과 없음"을 구별한다.** 출처가 죽었는데 빈 목록을 주면 사용자는 그
종목이 존재하지 않는다고 읽는다 — 할 일이 정반대인데 화면이 같은 말을 한다.
"""
from __future__ import annotations

import pytest
from httpx2 import ASGITransport, AsyncClient

from src.api.main import create_app
from src.db.session import get_session
from src.ingestion.yahoo.errors import StockSourceRateLimited, StockSourceUnavailable
from src.ingestion.yahoo.parse import StockQuote

KRX = StockQuote("KRX", "005930.KS", "삼성전자", "KRW")
NASDAQ = StockQuote("NASDAQ", "AAPL", "Apple Inc.", "USD")
TSE = StockQuote("TSE", "7203.T", "Toyota Motor", "JPY")


class StubSource:
    def __init__(self, results=None, error=None) -> None:
        self._results = results if results is not None else []
        self._error = error
        self.queries: list[str] = []

    async def search(self, query: str, limit: int):
        self.queries.append(query)
        if self._error is not None:
            raise self._error
        return self._results[:limit], "{}", 200

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_: object) -> None:
        return None


@pytest.fixture
def make_client(session_factory):
    def _make(source):
        app = create_app()

        async def _override():
            async with session_factory() as s:
                yield s

        from src.api.routes import stock_search

        app.dependency_overrides[get_session] = _override
        app.dependency_overrides[stock_search.get_source] = lambda: source
        return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    return _make


class Test세_시장:
    async def test_국내_미국_일본_종목이_모두_검색된다(self, make_client) -> None:
        """FR-002."""
        async with make_client(StubSource([KRX, NASDAQ, TSE])) as ac:
            body = (await ac.get("/api/stocks/search", params={"q": "a"})).json()
        assert {r["market"] for r in body["results"]} == {"KRX", "NASDAQ", "TSE"}

    async def test_시장과_통화를_함께_준다(self, make_client) -> None:
        """FR-002b — 통화가 다르면 환전 여부와 수익률 기준이 달라진다."""
        async with make_client(StubSource([KRX])) as ac:
            body = (await ac.get("/api/stocks/search", params={"q": "삼성"})).json()
        first = body["results"][0]
        assert first == {"market": "KRX", "symbol": "005930.KS",
                         "name": "삼성전자", "currency": "KRW"}


class Test실패와_빈_결과의_구별:
    async def test_결과가_없으면_빈_목록이고_200이다(self, make_client) -> None:
        async with make_client(StubSource([])) as ac:
            res = await ac.get("/api/stocks/search", params={"q": "zzzz"})
        assert res.status_code == 200
        assert res.json()["results"] == []

    async def test_출처_장애는_502다(self, make_client) -> None:
        """빈 목록으로 내려보내면 사용자는 그 종목이 없다고 읽는다."""
        async with make_client(
            StubSource(error=StockSourceUnavailable("장애"))
        ) as ac:
            res = await ac.get("/api/stocks/search", params={"q": "삼성"})
        assert res.status_code == 502
        assert res.json()["status"] == "source_unavailable"

    async def test_호출_한도는_503이다(self, make_client) -> None:
        """사용자가 할 일이 다르다 — 기다려야 한다."""
        async with make_client(
            StubSource(error=StockSourceRateLimited("한도"))
        ) as ac:
            res = await ac.get("/api/stocks/search", params={"q": "삼성"})
        assert res.status_code == 503
        assert res.json()["status"] == "source_rate_limited"


class Test질의_검증:
    async def test_빈_질의는_400이다(self, make_client) -> None:
        async with make_client(StubSource([])) as ac:
            res = await ac.get("/api/stocks/search", params={"q": ""})
        assert res.status_code == 400
        assert res.json()["status"] == "invalid_query"

    async def test_limit이_범위를_넘으면_거절한다(self, make_client) -> None:
        async with make_client(StubSource([])) as ac:
            res = await ac.get("/api/stocks/search", params={"q": "삼성", "limit": 999})
        assert res.status_code == 422


class Test목록_갱신:
    async def test_검색_시점에_출처에_묻는다(self, make_client) -> None:
        """FR-002c — 목록을 미리 쌓아 두면 신규 상장 종목이 빠진다."""
        source = StubSource([KRX])
        async with make_client(source) as ac:
            await ac.get("/api/stocks/search", params={"q": "삼성"})
            await ac.get("/api/stocks/search", params={"q": "애플"})
        assert source.queries == ["삼성", "애플"]
