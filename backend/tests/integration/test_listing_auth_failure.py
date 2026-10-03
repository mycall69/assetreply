"""인증 실패 (T024) — 006 FR-013b, FR-028a, FR-060, FR-062, SC-005a, SC-014.

**목록 갱신만 실패한다.** 인증 실패가 화면 전체의 오류로 번지면, 목록 하나 때문에 이미 받아 둔
시세로 할 수 있는 시뮬레이션까지 막힌다. **같은 날 다시 시도하지 않는다** — 나을 수 없는 요청으로
한도만 쓴다. 다만 인증 정보를 고치고 다시 띄우면 같은 날이라도 시도한다.
"""
from __future__ import annotations

import datetime as dt

import pytest
from httpx2 import ASGITransport, AsyncClient
from sqlalchemy import select

from src.api.main import create_app
from src.api.services.listing_refresh import get_auth_blocker, refresh_unit
from src.db.models import Stock, StockListingRefresh
from src.db.session import get_session
from src.ingestion.kiwoom.errors import KiwoomAuthError, classify_failure
from src.ingestion.yahoo.parse import StockQuote
from src.worker.listing_queue import ListingQueue
from tests.integration.listing_support import (
    APP_KEY,
    APP_SECRET,
    KOSPI_ROWS,
    NOW,
    YESTERDAY_NOW,
    StubListingSource,
    listing_settings,
    reset_listing_state,
    seed,
)


@pytest.fixture(autouse=True)
def _listing_state():
    reset_listing_state()
    yield
    reset_listing_state()


class JapanSource:
    async def search(self, query: str, limit: int):  # type: ignore[no-untyped-def]
        return [StockQuote("TSE", "7203.T", "Toyota Motor Corporation", "JPY")], "{}", 200

    async def __aenter__(self):  # type: ignore[no-untyped-def]
        return self

    async def __aexit__(self, *_: object) -> None:
        return None


@pytest.fixture
def queue() -> ListingQueue:
    return ListingQueue()


@pytest.fixture
def make_client(session_factory, queue):  # type: ignore[no-untyped-def]
    def _make(*, now: dt.datetime = NOW, credentials: bool = True) -> AsyncClient:
        from src.api.routes import stock_search

        app = create_app()

        async def _session():  # type: ignore[no-untyped-def]
            async with session_factory() as s:
                yield s

        app.dependency_overrides[get_session] = _session
        app.dependency_overrides[stock_search.get_source] = JapanSource
        app.dependency_overrides[stock_search.get_now] = lambda: now
        app.dependency_overrides[stock_search.get_listing_settings] = (
            lambda: listing_settings(credentials=credentials))
        app.dependency_overrides[stock_search.get_listing_queue] = lambda: queue
        return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    return _make


def auth_failure() -> KiwoomAuthError:
    """실제 오류 응답(픽스처 `error_auth_token.json`)을 판정한 결과 그대로."""
    exc = classify_failure(200, {
        "return_msg": "인증에 실패했습니다[8001:App Key와 Secret Key 검증에 실패했습니다]",
        "return_code": 3})
    assert isinstance(exc, KiwoomAuthError)
    return exc


async def fail_auth(session_factory, *, at: dt.datetime = NOW - dt.timedelta(hours=2)) -> None:  # type: ignore[no-untyped-def]
    source = StubListingSource({"KOSPI": [auth_failure()]})
    result = await refresh_unit(session_factory, source, "KOSPI", settings=listing_settings(),
                                now=lambda: at, blocker=get_auth_blocker())
    assert result.outcome == "failed" and result.kind == "auth"


@pytest.fixture
async def previous(session_factory) -> None:
    """어제 받은 목록이 있다."""
    await seed(session_factory, "KOSPI", KOSPI_ROWS, now=YESTERDAY_NOW)


class Test목록_갱신만_실패:
    async def test_이전_목록으로_계속_찾는다(self, make_client, session_factory, previous) -> None:
        """FR-062, SC-004."""
        await fail_auth(session_factory)
        async with make_client() as ac:
            body = (await ac.get("/api/stocks/search", params={"q": "삼성"})).json()
        assert [r["name"] for r in body["results"]][:2] == ["삼성전자", "삼성전자우"]
        kospi = next(i for i in body["lists"] if i["unit"] == "KOSPI")
        assert kospi["state"] == "auth_blocked"
        assert kospi["reason"] == "auth_failed"
        assert kospi["action"] == "set_credentials"
        assert kospi["asOf"] == "2026-10-01T00:05:12Z"

    async def test_일본_검색은_그대로다(self, make_client, session_factory, previous) -> None:
        await fail_auth(session_factory)
        async with make_client() as ac:
            res = await ac.get("/api/stocks/search/external", params={"q": "toyota"})
        assert res.status_code == 200
        assert res.json()["results"][0]["symbol"] == "7203.T"

    async def test_시뮬레이션은_그대로다(self, make_client, session_factory, previous) -> None:
        await fail_auth(session_factory)
        async with session_factory() as s:
            s.add(Stock(market="TSE", symbol="7203.T", name="Toyota", currency="JPY"))
            await s.commit()
        async with make_client() as ac:
            res = await ac.get("/api/stocks/simulation", params={
                "market": "TSE", "symbol": "7203.T", "start": "2021-08-02",
                "end": "2021-08-31", "principal": "1000000", "principalCurrency": "JPY",
                "reinvest": "true"})
        # 아직 시세가 없으니 수집을 시작한다 — 목록의 인증 실패와 무관하다.
        assert res.status_code == 202


class Test다시_시도하지_않는다:
    async def test_같은_날에는_간격이_지나도_요청하지_않는다(
            self, make_client, session_factory, queue, previous) -> None:
        """FR-013b, SC-005a — 실패는 두 시간 전이라 간격(30분)은 지났다."""
        await fail_auth(session_factory)
        async with make_client() as ac:
            for _ in range(3):
                await ac.get("/api/stocks/search", params={"q": "삼성"})
        assert not queue.is_active("KOSPI")
        assert queue.is_active("KOSDAQ")        # 다른 단위는 막히지 않는다

    async def test_재시작하면_같은_날이라도_다시_요청한다(
            self, make_client, session_factory, queue, previous) -> None:
        """FR-013b — 고쳤는데 다음 날까지 기다려야 하면 고친 것이 효과가 없다고 읽는다."""
        await fail_auth(session_factory)
        get_auth_blocker().reset()               # 프로세스 재시작 흉내
        async with make_client() as ac:
            await ac.get("/api/stocks/search", params={"q": "삼성"})
        assert queue.is_active("KOSPI")


class Test인증_정보_미설정:
    async def test_시도하지_않고_할_일을_말한다(self, make_client, queue) -> None:
        """FR-028a — 시도하면 실패가 확실하다. 사유와 할 일을 함께 말한다."""
        async with make_client(credentials=False) as ac:
            body = (await ac.get("/api/stocks/search", params={"q": "삼성"})).json()
        assert queue.size == 0
        for item in body["lists"]:
            assert (item["state"], item["reason"], item["action"]) == (
                "never", "auth_missing", "set_credentials")

    async def test_클라이언트는_인증_정보가_없으면_부르지_않는다(self, session_factory) -> None:
        """워커가 잘못 불러도 출처를 부르지 않고 `auth_missing`으로 끝난다."""
        from src.ingestion.kiwoom.client import KiwoomClient

        client = KiwoomClient(listing_settings(credentials=False))
        result = await refresh_unit(session_factory, client, "KOSPI",
                                    settings=listing_settings(credentials=False),
                                    now=lambda: NOW, blocker=get_auth_blocker())
        assert result.outcome == "failed" and result.kind == "auth"
        async with session_factory() as s:
            refresh = await s.get(StockListingRefresh, "KOSPI")
        assert refresh is not None and refresh.last_error_kind == "auth"


class Test비밀:
    async def test_갱신_기록_사유에_키가_없다(self, session_factory, previous) -> None:
        """FR-060, SC-014 — 저장 계층의 검사(T012가 넘긴 부분)."""
        await fail_auth(session_factory)
        async with session_factory() as s:
            rows = (await s.execute(select(StockListingRefresh))).scalars().all()
        assert rows
        for row in rows:
            for secret in (APP_KEY, APP_SECRET):
                assert secret not in (row.last_error or "")

    async def test_예외_문구에_비밀이_섞여도_기록에는_남지_않는다(
            self, session_factory, previous) -> None:
        """출처가 요청 값을 문구에 되돌려 보내는 경우까지 막는다."""
        leaking = KiwoomAuthError(f"거절됨 appkey={APP_KEY} token=Ab12Cd34Ef56Gh78Ij90")
        source = StubListingSource({"KOSPI": [leaking]})
        await refresh_unit(session_factory, source, "KOSPI", settings=listing_settings(),
                           now=lambda: NOW, blocker=get_auth_blocker())
        async with session_factory() as s:
            refresh = await s.get(StockListingRefresh, "KOSPI")
        assert refresh is not None
        assert APP_KEY not in (refresh.last_error or "")
        assert "Ab12Cd34Ef56Gh78Ij90" not in (refresh.last_error or "")
