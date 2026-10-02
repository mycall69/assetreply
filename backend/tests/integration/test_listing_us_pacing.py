"""미국 목록 — 쪽 간격·상태·국내와의 독립 (T068) — 006 FR-015, FR-017, FR-018, FR-028, FR-063,
research R6-2, R6-3.

미국 목록은 **계좌·토큰별 분당 5회** 제한이 있다. 쪽 사이 간격은 설정이다(기본 12초). 실측으로는
단위마다 한 쪽에 끝나지만, 나뉘어 오게 되면 간격이 한도를 지킨다.

**국내 단위가 미국 단위를 기다리지 않는다.** 미국 목록이 한도에 걸려 오래 걸리는 동안 국내 목록의
갱신이 그 뒤에 줄 서면, 국내 종목까지 그날 첫 검색이 늦어진다.
"""
from __future__ import annotations

import asyncio
import contextlib
import json
from pathlib import Path

import pytest
from httpx2 import ASGITransport, AsyncClient
from sqlalchemy import select

from src.api.main import create_app
from src.api.services.listing_refresh import AuthBlocker, refresh_unit
from src.db.models import StockListing, StockListingRefresh
from src.db.session import get_session
from src.ingestion.kiwoom.client import KiwoomClient
from src.worker.listing_queue import ListingQueue
from src.worker.listing_worker import listing_worker_loop
from tests.contract.test_kiwoom_client import KR, TOKEN, TOKEN_OK, US, Resp, Session
from tests.integration.listing_support import (
    APPLE,
    KOSPI_ROWS,
    NOW,
    SPY,
    TESLA,
    YESTERDAY_NOW,
    StubListingSource,
    kr_body,
    listing_settings,
    page,
    reset_listing_state,
    seed_us,
    us_body,
)

FIXTURES = Path(__file__).resolve().parent.parent / "contract" / "fixtures" / "kiwoom"


@pytest.fixture(autouse=True)
def _listing_state():
    reset_listing_state()
    yield
    reset_listing_state()


@pytest.fixture
def sleeps(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    """쪽 사이 대기를 기록한다(가짜 시계). 클라이언트 모듈의 `asyncio.sleep`만 바꾼다."""
    import src.ingestion.kiwoom.client as client_module

    recorded: list[float] = []
    real_sleep = asyncio.sleep

    async def fake(seconds: float) -> None:
        recorded.append(seconds)
        await real_sleep(0)

    monkeypatch.setattr(client_module.asyncio, "sleep", fake)
    return recorded


def kiwoom(session: Session) -> KiwoomClient:
    return KiwoomClient(listing_settings(), session=session)  # type: ignore[arg-type]


class Test쪽_사이_간격:
    async def test_미국은_설정한_간격을_둔다(self, session_factory, sleeps) -> None:
        """FR-063 — 기본 12초. 분당 5회 제한을 넘지 않는다."""
        s = Session({TOKEN: [Resp(TOKEN_OK)],
                     US: [Resp(us_body([APPLE]), headers={"cont-yn": "Y", "next-key": "K"}),
                          Resp(us_body([TESLA]), headers={"cont-yn": "N"})]})
        result = await refresh_unit(session_factory, kiwoom(s), "NASDAQ",
                                    settings=listing_settings(), now=lambda: NOW,
                                    blocker=AuthBlocker())
        assert result.outcome == "replaced" and result.rows == 2
        assert 12 in sleeps

    async def test_국내는_국내_간격을_둔다(self, session_factory, sleeps) -> None:
        s = Session({TOKEN: [Resp(TOKEN_OK)],
                     KR: [Resp(kr_body(KOSPI_ROWS[:2]), headers={"cont-yn": "Y", "next-key": "K"}),
                          Resp(kr_body(KOSPI_ROWS[2:]), headers={"cont-yn": "N"})]})
        await refresh_unit(session_factory, kiwoom(s), "KOSPI", settings=listing_settings(),
                           now=lambda: NOW, blocker=AuthBlocker())
        assert 1 in sleeps and 12 not in sleeps


class Test한도에_걸려_중단:
    async def test_받은_쪽까지로_교체하지_않는다(self, session_factory, sleeps) -> None:
        """FR-018 — 반쯤 받은 목록으로 바꾸면 뒤쪽 쪽의 종목이 사라진다."""
        await seed_us(session_factory, "NASDAQ", [APPLE, TESLA], now=YESTERDAY_NOW)
        limited = (FIXTURES / "error_rate_limit.json").read_text(encoding="utf-8")
        s = Session({TOKEN: [Resp(TOKEN_OK)],
                     US: [Resp(us_body([APPLE]), headers={"cont-yn": "Y", "next-key": "K"}),
                          Resp(limited)]})
        result = await refresh_unit(session_factory, kiwoom(s), "NASDAQ",
                                    settings=listing_settings(), now=lambda: NOW,
                                    blocker=AuthBlocker())
        assert result.outcome == "failed" and result.kind == "rate_limit"
        async with session_factory() as db:
            rows = {r.code: r.status for r in (await db.execute(select(StockListing))).scalars()}
            refresh = await db.get(StockListingRefresh, "NASDAQ")
        assert rows == {"AAPL": "listed", "TSLA": "listed"}
        assert refresh is not None and refresh.as_of == YESTERDAY_NOW
        assert refresh.last_error_kind == "rate_limit"


@pytest.fixture
def make_client(session_factory):  # type: ignore[no-untyped-def]
    queue = ListingQueue()

    def _make() -> AsyncClient:
        from src.api.routes import stock_search

        app = create_app()

        async def _session():  # type: ignore[no-untyped-def]
            async with session_factory() as s:
                yield s

        app.dependency_overrides[get_session] = _session
        app.dependency_overrides[stock_search.get_now] = lambda: NOW
        app.dependency_overrides[stock_search.get_listing_settings] = listing_settings
        app.dependency_overrides[stock_search.get_listing_queue] = lambda: queue
        return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")

    _make.queue = queue  # type: ignore[attr-defined]
    return _make


class Test목록_상태:
    async def test_미국_목록이_없으면_결과_없음이_아니라_never(self, make_client) -> None:
        """FR-028 — 미국 3단위가 lists에 따로 실린다."""
        async with make_client() as ac:
            body = (await ac.get("/api/stocks/search", params={"q": "애플"})).json()
        lists = {i["unit"]: i for i in body["lists"]}
        assert {"NYSE", "NASDAQ", "AMEX"} <= set(lists)
        assert lists["NASDAQ"]["state"] == "never"
        assert lists["NASDAQ"]["action"] == "wait"
        assert make_client.queue.is_active("NASDAQ")

    async def test_받은_미국_목록으로_찾는다(self, make_client, session_factory) -> None:
        await seed_us(session_factory, "NASDAQ", [APPLE, TESLA])
        await seed_us(session_factory, "NYSE", [SPY])
        async with make_client() as ac:
            body = (await ac.get("/api/stocks/search", params={"q": "ㅇㅍ"})).json()
        first = body["results"][0]
        assert (first["country"], first["market"], first["symbol"], first["currency"]) == (
            "US", "NASDAQ", "AAPL", "USD")
        assert first["name"] == "애플"
        assert first["nameEn"] == "APPLE INC"
        assert first["listedOn"] is None


class Test국내와_미국의_독립:
    async def test_미국_갱신이_멈춰_있어도_국내가_먼저_끝난다(self, session_factory) -> None:
        """FR-015, FR-017 — 미국 목록이 한도에 걸려 오래 걸리는 동안 국내가 뒤에 줄 서지 않는다."""
        source = StubListingSource({
            "NYSE": [[page(us_body([SPY]))]],
            "KOSPI": [[page(kr_body(KOSPI_ROWS))]],
        })
        nyse_gate = asyncio.Event()
        original = source.fetch_unit

        async def fetch(unit: str):  # type: ignore[no-untyped-def]
            if unit == "NYSE":
                await nyse_gate.wait()
            return await original(unit)

        source.fetch_unit = fetch  # type: ignore[method-assign]
        queue = ListingQueue()
        task = asyncio.create_task(listing_worker_loop(
            session_factory, source, queue, settings=listing_settings()))
        try:
            queue.request("NYSE")
            await asyncio.sleep(0.05)
            queue.request("KOSPI")
            async with asyncio.timeout(3):
                while queue.is_active("KOSPI"):  # noqa: ASYNC110
                    await asyncio.sleep(0.02)
            assert queue.is_active("NYSE"), "미국 갱신은 아직 멈춰 있어야 한다"
            nyse_gate.set()
            async with asyncio.timeout(3):
                while queue.is_active("NYSE"):  # noqa: ASYNC110
                    await asyncio.sleep(0.02)
        finally:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
        async with session_factory() as db:
            codes = set((await db.execute(select(StockListing.code))).scalars())
        assert {"005930", "SPY"} <= codes

    async def test_두_줄이_동시에_받아도_토큰은_한_번_받는다(self, sleeps) -> None:
        """국내·미국이 같은 클라이언트를 함께 쓴다. 토큰을 둘 받으면 앞의 것이 무효가 될 수 있다.

        토큰 응답이 **양보해야** 경합이 생긴다 — 곧바로 끝나는 스텁이면 잠금이 없어도 통과한다.
        """

        class Yielding(Resp):
            async def text(self) -> str:
                await asyncio.sleep(0)
                await asyncio.sleep(0)
                return await super().text()

        s = Session({TOKEN: [Yielding(TOKEN_OK)],
                     KR: [Resp(json.dumps({"return_code": 0, "list": []}))],
                     US: [Resp(json.dumps({"return_code": 0, "list": []}))]})
        async with kiwoom(s) as c:
            await asyncio.gather(c.fetch_unit("KOSPI"), c.fetch_unit("NYSE"))
        assert s.count(TOKEN) == 1
