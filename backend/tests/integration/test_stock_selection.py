"""고른 종목의 등록 (T023) — 006 FR-030, FR-030b, FR-033, SC-007, SC-007a, research R6-17.

**검색 → 등록 → 실행 경로를 탄다. 픽스처가 `stock` 행을 미리 넣지 않는다.** 005는 고른 종목을
저장하는 경로가 없었는데(`ensure_stock` 호출처 0), 테스트가 행을 직접 넣어 그 결함이 가려졌다.
같은 이유로 `first_available_date`도 넣지 않는다 — 넣으면 휴일 시작 거절 결함이 다시 가려진다.
그래서 시작일은 거래일(2021-08-02)로 잡는다.
"""
from __future__ import annotations

import asyncio
import datetime as dt
from decimal import Decimal

import pytest
from httpx2 import ASGITransport, AsyncClient
from sqlalchemy import func, select
from src.worker.listing_queue import ListingQueue

from src.api.main import create_app
from src.api.routes import stock_search
from src.db.models import Stock, StockCollectionJob
from src.db.session import get_session
from src.ingestion.yahoo.parse import ChartData, DailyPrice
from src.worker.stock_queue import get_stock_queue
from src.worker.stock_worker import run_stock_job
from tests.integration.listing_support import (
    KOSDAQ_ROWS,
    KOSPI_ROWS,
    NOW,
    listing_settings,
    reset_listing_state,
    seed,
)

D = dt.date.fromisoformat


@pytest.fixture(autouse=True)
def _listing_state():
    reset_listing_state()
    yield
    reset_listing_state()


@pytest.fixture
async def client(session_factory):  # type: ignore[no-untyped-def]
    await seed(session_factory, "KOSPI", KOSPI_ROWS)
    await seed(session_factory, "KOSDAQ", KOSDAQ_ROWS)
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


async def listing_id(client: AsyncClient, q: str) -> int:
    """검색 결과에서 고른다 — 사용자가 하는 그대로."""
    body = (await client.get("/api/stocks/search", params={"q": q})).json()
    return int(body["results"][0]["listingId"])


async def stocks(session_factory) -> list[Stock]:  # type: ignore[no-untyped-def]
    async with session_factory() as s:
        return list((await s.execute(select(Stock).order_by(Stock.id))).scalars())


SIM = {"start": "2021-08-02", "end": "2021-08-31", "principal": "1000000",
       "principalCurrency": "KRW", "reinvest": "true"}


class Test목록_결과_등록:
    async def test_국내_목록_행으로_종목을_만든다(self, client, session_factory) -> None:
        """FR-030, FR-030b."""
        lid = await listing_id(client, "삼성전자")
        res = await client.post("/api/stocks/selection",
                                json={"source": "listing", "listingId": lid})
        assert res.status_code == 200
        assert res.json() == {"market": "KRX", "symbol": "005930.KS", "name": "삼성전자",
                              "currency": "KRW", "listedOn": "1975-06-11"}
        rows = await stocks(session_factory)
        assert [(r.market, r.symbol, r.currency) for r in rows] == [("KRX", "005930.KS", "KRW")]
        # 목록의 상장일을 시작 가능 날짜로 복사하지 않는다 (research R6-8)
        assert rows[0].first_available_date is None

    async def test_코스닥은_KQ로_등록한다(self, client) -> None:
        lid = await listing_id(client, "에코프로비엠")
        body = (await client.post("/api/stocks/selection",
                                  json={"source": "listing", "listingId": lid})).json()
        assert body["symbol"] == "247540.KQ"

    async def test_두_번_불러도_행이_하나다(self, client, session_factory) -> None:
        """SC-007."""
        lid = await listing_id(client, "삼성전자")
        for _ in range(2):
            await client.post("/api/stocks/selection", json={"source": "listing", "listingId": lid})
        assert len(await stocks(session_factory)) == 1

    async def test_005가_저장한_같은_종목이_있으면_그것을_쓴다(
            self, client, session_factory) -> None:
        """FR-030 — 식별자가 어긋나면 같은 종목이 둘이 되어 시세를 다시 받는다."""
        async with session_factory() as s:
            s.add(Stock(market="KRX", symbol="005930.KS", name="Samsung Electronics",
                        currency="KRW"))
            await s.commit()
        lid = await listing_id(client, "삼성전자")
        body = (await client.post("/api/stocks/selection",
                                  json={"source": "listing", "listingId": lid})).json()
        rows = await stocks(session_factory)
        assert len(rows) == 1
        assert (body["market"], body["symbol"]) == ("KRX", "005930.KS")

    async def test_없는_목록_행은_404다(self, client) -> None:
        res = await client.post("/api/stocks/selection",
                                json={"source": "listing", "listingId": 999999})
        assert res.status_code == 404
        assert res.json()["status"] == "unknown_listing"


class Test외부_결과_등록:
    TOYOTA = {"source": "external", "market": "TSE", "symbol": "7203.T",
              "name": "Toyota Motor Corporation", "currency": "JPY"}

    async def test_일본_종목을_등록한다(self, client, session_factory) -> None:
        res = await client.post("/api/stocks/selection", json=self.TOYOTA)
        assert res.status_code == 200
        assert res.json() == {"market": "TSE", "symbol": "7203.T",
                              "name": "Toyota Motor Corporation", "currency": "JPY",
                              "listedOn": None}
        assert [(r.market, r.symbol) for r in await stocks(session_factory)] == [("TSE", "7203.T")]

    @pytest.mark.parametrize("override", [
        {"market": "NYSE"}, {"market": "KRX"}, {"currency": "USD"}, {"symbol": ""},
        {"name": ""},
    ])
    async def test_TSE_JPY가_아니면_거절한다(self, client, session_factory, override) -> None:
        """클라이언트가 보낸 다른 값은 거절한다 — 일본 밖은 로컬 목록이 맡는다."""
        res = await client.post("/api/stocks/selection", json={**self.TOYOTA, **override})
        assert res.status_code == 400
        assert res.json()["status"] == "invalid_query"
        assert await stocks(session_factory) == []

    async def test_모르는_source는_거절한다(self, client) -> None:
        res = await client.post("/api/stocks/selection", json={"source": "guess"})
        assert res.status_code in (400, 422)


class StubChart:
    async def fetch_chart(self, symbol: str, date_from: dt.date, date_to: dt.date):  # type: ignore[no-untyped-def]
        return (ChartData(currency="KRW", first_trade_date=None, prices=[
            DailyPrice(quote_date=D("2021-08-02"), open_raw=Decimal("80000"),
                       close_raw=Decimal("80100"), close_adjusted=Decimal("80100")),
            DailyPrice(quote_date=D("2021-08-03"), open_raw=Decimal("81000"),
                       close_raw=Decimal("81100"), close_adjusted=Decimal("81100")),
        ]), "{}", 200)

    async def delay_between_chunks(self) -> None:
        return None


class Test등록_뒤_실행:
    async def test_검색_등록_실행이_끝까지_간다(self, client, session_factory) -> None:
        """SC-007a — 고른 종목으로 실행했을 때 "알 수 없는 종목"으로 끝나지 않는다."""
        lid = await listing_id(client, "삼성전자")
        chosen = (await client.post("/api/stocks/selection",
                                    json={"source": "listing", "listingId": lid})).json()
        params = {**SIM, "market": chosen["market"], "symbol": chosen["symbol"]}

        first = await client.get("/api/stocks/simulation", params=params)
        assert first.status_code == 202, first.text
        assert first.json()["status"] == "collecting"

        work = await asyncio.wait_for(get_stock_queue().pop(), timeout=1)
        await run_stock_job(session_factory, StubChart(), work)
        get_stock_queue().done(work.stock_id)

        done = await client.get("/api/stocks/simulation", params=params)
        assert done.status_code == 200, done.text
        assert done.json()["stock"]["symbol"] == "005930.KS"
        assert done.json()["rows"]

    async def test_미등록_국내_종목은_목록으로_등록한_뒤_진행한다(
            self, client, session_factory) -> None:
        """FR-030b, FR-033 — 이력(브라우저)은 DB와 따로 산다. 이력에서 다시 실행하는 경로다."""
        assert await stocks(session_factory) == []
        res = await client.get("/api/stocks/simulation",
                               params={**SIM, "market": "KRX", "symbol": "247540.KQ"})
        assert res.status_code == 202, res.text
        rows = await stocks(session_factory)
        assert [(r.market, r.symbol, r.name) for r in rows] == [
            ("KRX", "247540.KQ", "에코프로비엠")]

    async def test_목록에_없는_국내_종목은_다시_고르라고_한다(
            self, client, session_factory) -> None:
        res = await client.get("/api/stocks/simulation",
                               params={**SIM, "market": "KRX", "symbol": "000000.KS"})
        assert res.status_code == 404
        assert res.json()["status"] == "unknown_stock"
        assert res.json()["action"] == "reselect"
        assert await stocks(session_factory) == []

    async def test_시장_접미사가_어긋나면_등록하지_않는다(self, client, session_factory) -> None:
        """코스닥 종목을 `.KS`로 부르면 왕복이 깨진다 — 다른 종목으로 등록하지 않는다 (FR-031)."""
        res = await client.get("/api/stocks/simulation",
                               params={**SIM, "market": "KRX", "symbol": "247540.KS"})
        assert res.status_code == 404
        assert res.json()["action"] == "reselect"
        assert await stocks(session_factory) == []

    async def test_미등록_일본_종목은_다시_고르라고_한다(self, client) -> None:
        res = await client.get("/api/stocks/simulation",
                               params={**SIM, "market": "TSE", "symbol": "7203.T",
                                       "principalCurrency": "JPY"})
        assert res.status_code == 404
        assert res.json()["status"] == "unknown_stock"
        assert res.json()["action"] == "reselect"

    async def test_등록만으로_수집이_시작되지_않는다(self, client, session_factory) -> None:
        """등록은 식별을 확보할 뿐이다. 수집은 실행이 판정한다 (005 FR-047)."""
        lid = await listing_id(client, "삼성전자")
        await client.post("/api/stocks/selection", json={"source": "listing", "listingId": lid})
        async with session_factory() as s:
            jobs = (await s.execute(
                select(func.count()).select_from(StockCollectionJob))).scalar()
        assert jobs == 0
