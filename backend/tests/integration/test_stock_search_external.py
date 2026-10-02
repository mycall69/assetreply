"""일본 종목 검색 (T022) — 006 FR-026, FR-027, contracts/rest-api `GET /api/stocks/search/external`.

005의 외부 출처 검색이다. **결과에서 TSE만 남긴다** — 국내·미국 종목을 빼지 않으면 같은 종목이
로컬 결과와 외부 결과에 두 번 나오고, 사용자는 다른 종목으로 여겨 아무거나 고른다.

005의 `test_stock_search_api.py`를 대신한다. 그 파일은 하나의 검색이 세 시장을 모두 돌려주는
005의 계약을 검증했고, 006에서 그 계약이 둘로 나뉘었다(research R6-12).
"""
from __future__ import annotations

import pytest
from httpx2 import ASGITransport, AsyncClient

from src.api.main import create_app
from src.db.session import get_session
from src.ingestion.yahoo.errors import StockSourceRateLimited, StockSourceUnavailable
from src.ingestion.yahoo.parse import StockQuote

KRX = StockQuote("KRX", "005930.KS", "Samsung Electronics", "KRW")
NASDAQ = StockQuote("NASDAQ", "AAPL", "Apple Inc.", "USD")
TSE = StockQuote("TSE", "7203.T", "Toyota Motor Corporation", "JPY")
TSE_ETF = StockQuote("TSE", "1306.T", "NEXT FUNDS TOPIX ETF", "JPY", kind="etf")


class StubSource:
    def __init__(self, results=None, error=None) -> None:  # type: ignore[no-untyped-def]
        self._results = results if results is not None else []
        self._error = error
        self.queries: list[str] = []

    async def search(self, query: str, limit: int):  # type: ignore[no-untyped-def]
        self.queries.append(query)
        if self._error is not None:
            raise self._error
        return self._results[:limit], "{}", 200

    async def __aenter__(self):  # type: ignore[no-untyped-def]
        return self

    async def __aexit__(self, *_: object) -> None:
        return None


@pytest.fixture
def make_client(session_factory):  # type: ignore[no-untyped-def]
    def _make(source):  # type: ignore[no-untyped-def]
        from src.api.routes import stock_search

        app = create_app()

        async def _override():  # type: ignore[no-untyped-def]
            async with session_factory() as s:
                yield s

        app.dependency_overrides[get_session] = _override
        app.dependency_overrides[stock_search.get_source] = lambda: source
        return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    return _make


async def external(make_client, source, q: str = "toyota"):  # type: ignore[no-untyped-def]
    async with make_client(source) as ac:
        return await ac.get("/api/stocks/search/external", params={"q": q})


class TestTSE만:
    async def test_국내_미국을_빼고_일본만_남긴다(self, make_client) -> None:
        """FR-026."""
        res = await external(make_client, StubSource([KRX, NASDAQ, TSE]))
        assert res.status_code == 200
        body = res.json()
        assert body["query"] == "toyota"
        assert body["results"] == [{
            "market": "TSE", "symbol": "7203.T", "name": "Toyota Motor Corporation",
            "currency": "JPY", "kind": "stock"}]

    async def test_ETF_여부를_싣는다(self, make_client) -> None:
        body = (await external(make_client, StubSource([TSE_ETF]), "topix")).json()
        assert body["results"][0]["kind"] == "etf"

    async def test_일본_종목이_없으면_빈_목록이다(self, make_client) -> None:
        res = await external(make_client, StubSource([KRX, NASDAQ]), "samsung")
        assert res.status_code == 200
        assert res.json()["results"] == []

    async def test_검색_시점에_출처에_묻는다(self, make_client) -> None:
        source = StubSource([TSE])
        async with make_client(source) as ac:
            await ac.get("/api/stocks/search/external", params={"q": "toyota"})
            await ac.get("/api/stocks/search/external", params={"q": "sony"})
        assert source.queries == ["toyota", "sony"]


class Test출처_장애:
    """005와 같은 오류. 화면은 이 실패를 **일본 영역에만** 표시한다 (FR-027)."""

    async def test_출처_장애는_502다(self, make_client) -> None:
        res = await external(make_client, StubSource(error=StockSourceUnavailable("장애")))
        assert res.status_code == 502
        assert res.json()["status"] == "source_unavailable"

    async def test_호출_한도는_503이다(self, make_client) -> None:
        res = await external(make_client, StubSource(error=StockSourceRateLimited("한도")))
        assert res.status_code == 503
        assert res.json()["status"] == "source_rate_limited"


class Test질의_검증:
    async def test_빈_질의는_400이다(self, make_client) -> None:
        res = await external(make_client, StubSource([]), "  ")
        assert res.status_code == 400
        assert res.json()["status"] == "invalid_query"

    async def test_limit이_범위를_넘으면_거절한다(self, make_client) -> None:
        async with make_client(StubSource([])) as ac:
            res = await ac.get("/api/stocks/search/external",
                               params={"q": "toyota", "limit": 999})
        assert res.status_code == 422
