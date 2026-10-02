"""미국 종목의 등록 (T069) — 006 FR-030, FR-030a, SC-007, research R6-6.

**미국은 거래소가 달라도 같은 티커면 같은 종목이다.** 005는 시세 출처의 거래소 코드로 시장을 정했다
(`PCX` → `AMEX`). 목록 출처가 같은 ETF를 `NYSE`로 주면, `(시장, 심볼)`로 찾을 때 같은 종목이 둘이
된다 — 시세를 다시 받고 이력이 다른 쪽을 가리킨다. 둘 다 정상으로 보인다.
"""
from __future__ import annotations

import pytest
from httpx2 import ASGITransport, AsyncClient
from sqlalchemy import select

from src.api.main import create_app
from src.api.routes import stock_search
from src.db.models import Stock
from src.db.session import get_session
from src.worker.listing_queue import ListingQueue
from tests.integration.listing_support import (
    ABR_D,
    APPLE,
    BRK_B,
    NOW,
    SPY,
    listing_settings,
    reset_listing_state,
    seed_us,
)


@pytest.fixture(autouse=True)
def _listing_state():
    reset_listing_state()
    yield
    reset_listing_state()


@pytest.fixture
async def client(session_factory):  # type: ignore[no-untyped-def]
    await seed_us(session_factory, "NYSE", [SPY, BRK_B, ABR_D])
    await seed_us(session_factory, "NASDAQ", [APPLE])
    app = create_app()

    async def _override():  # type: ignore[no-untyped-def]
        async with session_factory() as s:
            yield s

    app.dependency_overrides[get_session] = _override
    app.dependency_overrides[stock_search.get_now] = lambda: NOW
    app.dependency_overrides[stock_search.get_listing_settings] = listing_settings
    app.dependency_overrides[stock_search.get_listing_queue] = ListingQueue
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


async def select_by_search(client: AsyncClient, q: str) -> dict:  # type: ignore[type-arg]
    found = (await client.get("/api/stocks/search", params={"q": q})).json()
    lid = found["results"][0]["listingId"]
    res = await client.post("/api/stocks/selection", json={"source": "listing", "listingId": lid})
    assert res.status_code == 200, res.text
    return res.json()


async def stocks(session_factory) -> list[tuple[str, str]]:  # type: ignore[no-untyped-def]
    async with session_factory() as s:
        return [(r.market, r.symbol) for r in (await s.execute(select(Stock))).scalars()]


SIM = {"start": "2021-08-02", "end": "2021-08-31", "principal": "1000",
       "principalCurrency": "USD", "reinvest": "true"}


class Test티커로_먼저_찾는다:
    async def test_거래소가_달라도_기존_종목을_쓴다(self, client, session_factory) -> None:
        """FR-030a — 005가 AMEX로 저장한 SPY를 목록은 NYSE로 준다."""
        async with session_factory() as s:
            s.add(Stock(market="AMEX", symbol="SPY", name="SPDR S&P 500 ETF Trust",
                        currency="USD"))
            await s.commit()
        body = await select_by_search(client, "SPY")
        assert (body["market"], body["symbol"]) == ("AMEX", "SPY")
        assert await stocks(session_factory) == [("AMEX", "SPY")]

    async def test_없으면_목록의_거래소로_만든다(self, client, session_factory) -> None:
        body = await select_by_search(client, "SPY")
        assert (body["market"], body["symbol"], body["currency"]) == ("NYSE", "SPY", "USD")
        assert body["listedOn"] is None
        assert await stocks(session_factory) == [("NYSE", "SPY")]

    async def test_클래스_주식은_시세_출처_표기로_만든다(self, client, session_factory) -> None:
        """FR-031 — 목록의 `BRKb`를 그대로 보내면 시세 출처가 찾지 못한다."""
        body = await select_by_search(client, "버크셔")
        assert body["symbol"] == "BRK-B"
        assert body["name"] == "버크셔 해서웨이 B"

    async def test_두_번_골라도_하나다(self, client, session_factory) -> None:
        """SC-007."""
        await select_by_search(client, "애플")
        await select_by_search(client, "AAPL")
        assert await stocks(session_factory) == [("NASDAQ", "AAPL")]


class Test이력_재실행:
    async def test_다른_거래소의_이력도_같은_종목으로_실행한다(
            self, client, session_factory) -> None:
        """005 이력이 AMEX:SPY를 들고 있고 DB에는 006이 NYSE:SPY로 등록했다."""
        await select_by_search(client, "SPY")
        res = await client.get("/api/stocks/simulation",
                               params={**SIM, "market": "AMEX", "symbol": "SPY"})
        assert res.status_code == 202, res.text
        assert await stocks(session_factory) == [("NYSE", "SPY")]

    async def test_미등록이면_역변환으로_목록에서_찾아_등록한다(
            self, client, session_factory) -> None:
        """FR-030b — 우선주 `ABR-D`(목록) ↔ `ABR-PD`(시세 출처)."""
        res = await client.get("/api/stocks/simulation",
                               params={**SIM, "market": "NYSE", "symbol": "ABR-PD"})
        assert res.status_code == 202, res.text
        assert await stocks(session_factory) == [("NYSE", "ABR-PD")]

    async def test_목록에_없으면_다시_고르라고_한다(self, client, session_factory) -> None:
        res = await client.get("/api/stocks/simulation",
                               params={**SIM, "market": "NASDAQ", "symbol": "ZZZZ"})
        assert res.status_code == 404
        assert res.json()["action"] == "reselect"
        assert await stocks(session_factory) == []
