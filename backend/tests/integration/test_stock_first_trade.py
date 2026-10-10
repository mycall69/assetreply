"""종목의 첫 거래일 저장 (014 반복 2026-10-10f T159) — FR-033, SC-018, data-model §12, R14-26.

Yahoo 첫 거래일(차트 meta — 출처가 시세를 가진 첫 날)를 새 열 `stock.first_trade_date`에 둔다 —
**표시 전용**이다. 시작일 하한(`first_available_date`)에 쓰면 메뉴의 시작일 거절이 바뀐다(FR-026).

- 등록(`POST /api/stocks/selection`): 모르면 한 번 받는다. 알면 부르지 않는다. 출처 실패·시간
  초과여도 등록은 성공하고 응답은 그대로다. 앱 수명주기의 공유 클라이언트가 없으면(이 테스트처럼
  lifespan 없이 돌면) 부르지 않는다
- 주식 수집(`collect_range`): 청크 응답에 있으면 비었을 때만 쓴다 — 덮어쓰지 않는다
"""
from __future__ import annotations

import asyncio
import datetime as dt
from decimal import Decimal

import pytest
from alembic.script import ScriptDirectory
from httpx2 import ASGITransport, AsyncClient
from sqlalchemy import select, text

from src.api.main import create_app
from src.api.routes import stock_search, stock_selection
from src.api.services.stock_selection import FirstTradeLookup
from src.db.dialect import upsert
from src.db.migrate import _alembic_config
from src.db.models import Stock
from src.db.session import get_session
from src.ingestion.yahoo.errors import StockSourceUnavailable
from src.ingestion.yahoo.parse import ChartData, ChartFetch, DailyPrice, RawBody
from src.worker.listing_queue import ListingQueue
from src.worker.stock_runner import collect_range
from tests.integration.listing_support import (
    KOSPI_ROWS,
    NOW,
    SPY,
    listing_settings,
    reset_listing_state,
    seed,
    seed_us,
)

D = dt.date.fromisoformat
#: 출처의 국내 시세 시작일(T158) — 키움 상장일(1975-06-11)과 다르다
SAMSUNG_FIRST_TRADE = D("2000-01-04")


class FirstTradeStub:
    """첫 거래일 출처 대역 — 네트워크를 쓰지 않는다(헌법 원칙 III)."""

    def __init__(self, day: dt.date | None = SAMSUNG_FIRST_TRADE, *,
                 error: Exception | None = None,
                 delay: float = 0.0) -> None:
        self.day = day
        self.error = error
        self.delay = delay
        self.calls: list[str] = []

    async def fetch_first_trade_date(self, symbol: str) -> dt.date | None:
        self.calls.append(symbol)
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.error is not None:
            raise self.error
        return self.day


@pytest.fixture(autouse=True)
def _listing_state():  # type: ignore[no-untyped-def]
    reset_listing_state()
    yield
    reset_listing_state()


@pytest.fixture
async def seeded(session_factory):  # type: ignore[no-untyped-def]
    await seed(session_factory, "KOSPI", KOSPI_ROWS)
    await seed_us(session_factory, "NYSE", [SPY])
    return session_factory


def make_client(session_factory, lookup: FirstTradeLookup | None):  # type: ignore[no-untyped-def]
    app = create_app()

    async def _override():  # type: ignore[no-untyped-def]
        async with session_factory() as s:
            yield s

    app.dependency_overrides[get_session] = _override
    app.dependency_overrides[stock_search.get_now] = lambda: NOW
    app.dependency_overrides[stock_search.get_listing_settings] = listing_settings
    app.dependency_overrides[stock_search.get_listing_queue] = ListingQueue
    if lookup is not None:
        app.dependency_overrides[stock_selection.get_first_trade] = lambda: lookup
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def pick(client: AsyncClient, q: str) -> dict[str, object]:
    found = (await client.get("/api/stocks/search", params={"q": q})).json()
    res = await client.post("/api/stocks/selection",
                            json={"source": "listing",
                                  "listingId": found["results"][0]["listingId"]})
    assert res.status_code == 200, res.text
    body: dict[str, object] = res.json()
    return body


async def stock_row(session_factory, symbol: str) -> Stock:  # type: ignore[no-untyped-def]
    async with session_factory() as s:
        row = (await s.execute(select(Stock).where(Stock.symbol == symbol))).scalar_one()
        return row


SAMSUNG_SELECTED = {"market": "KRX", "symbol": "005930.KS", "name": "삼성전자", "currency": "KRW",
                    "listedOn": "1975-06-11"}


class Test스키마:
    async def test_표시_전용_열이다(self, session_factory) -> None:  # type: ignore[no-untyped-def]
        async with session_factory() as s:
            row = (await s.execute(text(
                "SELECT data_type, is_nullable FROM information_schema.columns "
                "WHERE table_schema = DATABASE() AND table_name = 'stock' "
                "AND column_name = 'first_trade_date'"))).one()
        assert (row[0], row[1]) == ("date", "YES")

    def test_리비전은_시가_리비전_뒤의_머리다(self) -> None:
        script = ScriptDirectory.from_config(_alembic_config())
        head = script.get_revision(script.get_current_head())
        assert head is not None
        assert head.down_revision == "d5e1a7c3b2f8"
        assert "첫 거래일" in (head.doc or "")


class Test등록:
    async def test_모르면_한_번_받아_저장하고_응답은_그대로다(self, seeded) -> None:  # type: ignore[no-untyped-def]
        stub = FirstTradeStub()
        async with make_client(seeded, FirstTradeLookup(stub, 3.0)) as client:
            assert await pick(client, "삼성전자") == SAMSUNG_SELECTED
            assert await pick(client, "삼성전자") == SAMSUNG_SELECTED
        assert stub.calls == ["005930.KS"]  # 알면 다시 부르지 않는다
        row = await stock_row(seeded, "005930.KS")
        assert row.first_trade_date == D("2000-01-04")
        assert row.first_available_date is None  # 시작일 하한은 그대로다

    async def test_미국_종목은_시세_티커로_받는다(self, seeded) -> None:  # type: ignore[no-untyped-def]
        stub = FirstTradeStub(D("1993-01-29"))
        async with make_client(seeded, FirstTradeLookup(stub, 3.0)) as client:
            await pick(client, "SPY")
        assert stub.calls == ["SPY"]
        assert (await stock_row(seeded, "SPY")).first_trade_date == D("1993-01-29")

    async def test_일본_외부_결과도_받는다(self, seeded) -> None:  # type: ignore[no-untyped-def]
        stub = FirstTradeStub(D("1999-05-06"))
        async with make_client(seeded, FirstTradeLookup(stub, 3.0)) as client:
            res = await client.post("/api/stocks/selection", json={
                "source": "external", "market": "TSE", "symbol": "7203.T",
                "name": "Toyota Motor Corporation", "currency": "JPY"})
        assert res.status_code == 200
        assert res.json() == {"market": "TSE", "symbol": "7203.T",
                              "name": "Toyota Motor Corporation",
                              "currency": "JPY", "listedOn": None}
        assert stub.calls == ["7203.T"]
        assert (await stock_row(seeded, "7203.T")).first_trade_date == D("1999-05-06")

    @pytest.mark.parametrize("stub", [
        FirstTradeStub(error=StockSourceUnavailable("출처 장애")),
        FirstTradeStub(delay=1.0),
        FirstTradeStub(None),
    ], ids=["출처_실패", "시간_초과", "출처가_주지_않음"])
    async def test_못_받아도_등록은_성공하고_비워_둔다(self, seeded, stub: FirstTradeStub) -> None:  # type: ignore[no-untyped-def]
        async with make_client(seeded, FirstTradeLookup(stub, 0.05)) as client:
            assert await pick(client, "삼성전자") == SAMSUNG_SELECTED
        assert (await stock_row(seeded, "005930.KS")).first_trade_date is None

    async def test_공유_클라이언트가_없으면_부르지_않는다(self, seeded) -> None:  # type: ignore[no-untyped-def]
        """lifespan 없이 돌면 공유 시세 클라이언트가 없다.

        006 등록 테스트가 실제 출처를 부르지 않는 까닭이다.
        """
        async with make_client(seeded, None) as client:
            assert await pick(client, "삼성전자") == SAMSUNG_SELECTED
        assert (await stock_row(seeded, "005930.KS")).first_trade_date is None


class ChartStub:
    def __init__(self, first_trade: dt.date | None) -> None:
        self.first_trade = first_trade

    async def fetch_chart(self, symbol: str, date_from: dt.date, date_to: dt.date) -> ChartFetch:
        return ChartFetch(
            data=ChartData(currency="KRW", first_trade_date=self.first_trade,
                           prices=[DailyPrice(date_from, Decimal("100"), Decimal("101"),
                                              Decimal("101"))]),
            raws=[RawBody("chart", "{}", 200, date_from, date_to)])

    async def delay_between_chunks(self) -> None:
        return None


class Test수집:
    async def _stock(self, session_factory, first_trade: dt.date | None) -> int:  # type: ignore[no-untyped-def]
        async with session_factory() as s:
            await upsert(s, Stock, [{"market": "KRX", "symbol": "005930.KS", "name": "삼성전자",
                                     "currency": "KRW", "first_trade_date": first_trade}])
            await s.commit()
            return int((await s.execute(select(Stock.id))).scalar_one())

    async def _collect(self, session_factory, stock_id: int, chart_first: dt.date | None) -> None:  # type: ignore[no-untyped-def]
        async with session_factory() as s:
            await collect_range(s, ChartStub(chart_first), stock_id, "005930.KS",
                                D("2021-08-02"), D("2021-08-06"))

    async def test_청크_응답에_있으면_비었을_때_기록한다(self, session_factory) -> None:  # type: ignore[no-untyped-def]
        stock_id = await self._stock(session_factory, None)
        await self._collect(session_factory, stock_id, D("2000-01-04"))
        row = await stock_row(session_factory, "005930.KS")
        assert row.first_trade_date == D("2000-01-04")
        assert row.first_available_date is None

    async def test_덮어쓰지_않는다(self, session_factory) -> None:  # type: ignore[no-untyped-def]
        stock_id = await self._stock(session_factory, D("1999-12-30"))
        await self._collect(session_factory, stock_id, D("2000-01-04"))
        assert (await stock_row(session_factory, "005930.KS")).first_trade_date == D("1999-12-30")

    async def test_응답에_없으면_그대로다(self, session_factory) -> None:  # type: ignore[no-untyped-def]
        stock_id = await self._stock(session_factory, None)
        await self._collect(session_factory, stock_id, None)
        assert (await stock_row(session_factory, "005930.KS")).first_trade_date is None
