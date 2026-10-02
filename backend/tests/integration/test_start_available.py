"""시작 가능 날짜 (T059) — 006 FR-005, FR-005a, SC-013, SC-013a, research R6-8, R6-17.

**검색 → 등록 → 실행 경로를 탄다**(R6-17). 픽스처가 `stock` 행이나 `first_available_date`를 넣으면
005의 실제 경로 결함(휴일 시작 거절)이 다시 가려진다.

판정은 두 단계다.

1. **수집 전** — 목록의 상장일은 하한이다. 시작일이 그보다 이르면 시세를 받지 않고 막는다
   (`basis: listing`). 막지 않으면 상장 이전이 확실한 시작일까지 수집을 기다린다.
2. **수집 후** — 시작 월에 일봉이 하나도 없으면 막고 시세가 실제로 시작하는 날을 알린다
   (`basis: price_start`). 상장일을 시작 가능 날짜로 믿으면 첫 매수가 시세 시작일로 **몰래 밀린다**.
"""
from __future__ import annotations

import asyncio
import datetime as dt
from decimal import Decimal

import pytest
from httpx2 import ASGITransport, AsyncClient
from sqlalchemy import func, select

from src.api.main import create_app
from src.api.routes import stock_search
from src.db.models import Stock, StockCollectionJob
from src.db.session import get_session
from src.ingestion.yahoo.parse import ChartData, DailyPrice
from src.worker.listing_queue import ListingQueue
from src.worker.stock_queue import get_stock_queue
from src.worker.stock_worker import run_stock_job
from tests.integration.listing_support import (
    NOW,
    SAMSUNG,
    kr_row,
    listing_settings,
    reset_listing_state,
    seed,
)

D = dt.date.fromisoformat

#: 2021-05-03 상장. 시세는 7월부터만 있다 — 상장일과 시세 시작일이 다른 종목.
LATE = kr_row("123450", "늦은시세", "거래소", "20210503")


@pytest.fixture(autouse=True)
def _listing_state():
    reset_listing_state()
    yield
    reset_listing_state()


class StubChart:
    """주어진 거래일만 돌려주는 시세 출처. 요청 구간 안의 날만 준다."""

    def __init__(self, days: list[str]) -> None:
        self.days = [D(d) for d in days]
        self.calls: list[tuple[dt.date, dt.date]] = []

    async def fetch_chart(self, symbol: str, date_from: dt.date, date_to: dt.date):  # type: ignore[no-untyped-def]
        self.calls.append((date_from, date_to))
        return (ChartData(currency="KRW", first_trade_date=None, prices=[
            DailyPrice(quote_date=d, open_raw=Decimal("10000"), close_raw=Decimal("10000"),
                       close_adjusted=Decimal("10000"))
            for d in self.days if date_from <= d <= date_to]), "{}", 200)

    async def delay_between_chunks(self) -> None:
        return None


@pytest.fixture
async def client(session_factory):  # type: ignore[no-untyped-def]
    await seed(session_factory, "KOSPI", [SAMSUNG, LATE])
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


async def choose(client: AsyncClient, q: str) -> dict:  # type: ignore[type-arg]
    """검색에서 고르고 등록한다 — 사용자가 하는 그대로."""
    found = (await client.get("/api/stocks/search", params={"q": q})).json()
    lid = found["results"][0]["listingId"]
    res = await client.post("/api/stocks/selection", json={"source": "listing", "listingId": lid})
    assert res.status_code == 200, res.text
    return res.json()


def params(stock: dict, start: str, end: str) -> dict[str, str]:  # type: ignore[type-arg]
    return {"market": stock["market"], "symbol": stock["symbol"], "start": start, "end": end,
            "principal": "1000000", "principalCurrency": "KRW", "reinvest": "true"}


async def collect(session_factory, chart: StubChart) -> None:  # type: ignore[no-untyped-def]
    work = await asyncio.wait_for(get_stock_queue().pop(), timeout=1)
    await run_stock_job(session_factory, chart, work)
    get_stock_queue().done(work.stock_id)


async def jobs(session_factory) -> int:  # type: ignore[no-untyped-def]
    async with session_factory() as s:
        return int((await s.execute(
            select(func.count()).select_from(StockCollectionJob))).scalar_one())


class Test수집_전_상장일_하한:
    async def test_상장일보다_이르면_시세를_받지_않고_막는다(self, client, session_factory) -> None:
        """FR-005a — 막지 않으면 상장 이전이 확실한 구간까지 수집을 기다린다."""
        stock = await choose(client, "늦은시세")
        res = await client.get("/api/stocks/simulation",
                               params=params(stock, "2021-04-01", "2021-09-30"))
        assert res.status_code == 400
        body = res.json()
        assert body["status"] == "before_listing"
        assert body["basis"] == "listing"
        assert body["startableFrom"] == "2021-05-03"
        assert "2021-05-03" in body["message"]
        assert await jobs(session_factory) == 0

    async def test_상장일을_시작_가능_날짜로_복사하지_않는다(self, client, session_factory) -> None:
        """research R6-8 — 복사하면 상장일과 시세 시작일 사이의 시작일을 받아들인다."""
        await choose(client, "늦은시세")
        async with session_factory() as s:
            stock = (await s.execute(select(Stock))).scalar_one()
        assert stock.first_available_date is None


class Test수집_후_시작_월의_일봉:
    async def test_시작_월에_일봉이_없으면_시세_시작일을_알리고_막는다(
            self, client, session_factory) -> None:
        """FR-005, SC-013a — 첫 매수가 7월로 몰래 밀리지 않는다."""
        stock = await choose(client, "늦은시세")
        query = params(stock, "2021-05-10", "2021-09-30")
        first = await client.get("/api/stocks/simulation", params=query)
        assert first.status_code == 202
        await collect(session_factory, StubChart(["2021-07-01", "2021-07-02", "2021-08-02"]))

        res = await client.get("/api/stocks/simulation", params=query)
        assert res.status_code == 400, res.text
        body = res.json()
        assert body["status"] == "before_listing"
        assert body["basis"] == "price_start"
        assert body["startableFrom"] == "2021-07-01"
        assert "rows" not in body

    async def test_시세_시작일로_옮기면_계산한다(self, client, session_factory) -> None:
        stock = await choose(client, "늦은시세")
        await client.get("/api/stocks/simulation", params=params(stock, "2021-05-10", "2021-09-30"))
        await collect(session_factory, StubChart(["2021-07-01", "2021-08-02"]))
        res = await client.get("/api/stocks/simulation",
                               params=params(stock, "2021-07-01", "2021-09-30"))
        assert res.status_code == 200, res.text


class Test휴일_시작:
    async def test_기본값_2020_01_01은_휴일이어도_거절하지_않는다(
            self, client, session_factory) -> None:
        """SC-013 — 005는 실제 경로에서 휴일 시작을 거절했다(first_available_date가 비어 있어
        "받아 둔 첫 시세"로 판정). 기본값 그대로 실행하면 매번 거절된다."""
        stock = await choose(client, "삼성전자")
        query = params(stock, "2020-01-01", "2020-02-29")
        assert (await client.get("/api/stocks/simulation", params=query)).status_code == 202
        await collect(session_factory, StubChart(["2020-01-02", "2020-01-03", "2020-02-03"]))

        res = await client.get("/api/stocks/simulation", params=query)
        assert res.status_code == 200, res.text
        rows = res.json()["rows"]
        assert rows[-1]["date"] == "2020-01-02"           # 최신순 — 마지막이 첫 매수

    async def test_월말_휴일_시작은_다음_달_첫_거래일에_산다(self, client, session_factory) -> None:
        """시작 월에 일봉이 있으면(시작일 앞이라도) 휴장으로 설명된다 — 시세 시작 때문이 아니다."""
        stock = await choose(client, "삼성전자")
        query = params(stock, "2020-12-31", "2021-01-31")
        first = await client.get("/api/stocks/simulation", params=query)
        assert first.status_code == 202
        # 시작 월의 일봉(12-30)을 보려면 그 달 1일부터 받아야 한다.
        assert first.json()["missingFrom"] == "2020-12-01"
        await collect(session_factory, StubChart(["2020-12-30", "2021-01-04"]))

        res = await client.get("/api/stocks/simulation", params=query)
        assert res.status_code == 200, res.text
        assert res.json()["rows"][-1]["date"] == "2021-01-04"

    async def test_다시_요청해도_이미_받은_시세로_막지_않는다(
            self, client, session_factory) -> None:
        """005는 수집 전에 "받아 둔 첫 시세"로 판정해, 늦은 시작일로 한 번 받은 뒤에는 그보다
        이른 시작일을 상장 이전으로 거절했다 — 받으러 가지도 않고."""
        stock = await choose(client, "삼성전자")
        await client.get("/api/stocks/simulation", params=params(stock, "2021-08-02", "2021-08-31"))
        await collect(session_factory, StubChart(["2021-08-02", "2021-08-03"]))

        earlier = await client.get("/api/stocks/simulation",
                                   params=params(stock, "2020-01-01", "2021-08-31"))
        assert earlier.status_code == 202, earlier.text
        assert earlier.json()["missingFrom"] == "2020-01-01"
