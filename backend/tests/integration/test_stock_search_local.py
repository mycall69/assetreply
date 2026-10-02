"""로컬 목록 검색 API (T021) — 006 FR-017, FR-024, FR-025, FR-028, FR-028a, FR-029, SC-006,
contracts/rest-api `GET /api/stocks/search`.

**목록이 없어도 오류가 아니다.** 200에 `lists`로 알린다 — 오류로 내면 화면이 "검색 실패"로만
보이고 무엇을 해야 하는지 말할 자리가 없다. **외부 출처를 부르지 않고, 갱신을 기다리지 않는다.**
"""
from __future__ import annotations

import datetime as dt

import pytest
from httpx2 import ASGITransport, AsyncClient

from src.api.main import create_app
from src.api.services.listing_refresh import AuthBlocker, refresh_unit
from src.db.session import get_session
from src.ingestion.kiwoom.errors import KiwoomUnavailable
from src.repository import stock_listing as repo
from src.worker.listing_queue import ListingQueue
from tests.integration.listing_support import (
    KOSDAQ_ROWS,
    KOSPI_ROWS,
    NOW,
    YESTERDAY_NOW,
    StubListingSource,
    kr_row,
    listing_settings,
    reset_listing_state,
    seed,
)


@pytest.fixture(autouse=True)
def _listing_state():
    reset_listing_state()
    yield
    reset_listing_state()


class ForbiddenSource:
    """외부 출처 스텁. 로컬 검색이 이것을 부르면 실패다 (FR-027)."""

    def __init__(self) -> None:
        self.calls = 0

    async def search(self, query: str, limit: int):  # type: ignore[no-untyped-def]
        self.calls += 1
        raise AssertionError("로컬 검색이 외부 출처를 불렀습니다")

    async def __aenter__(self):  # type: ignore[no-untyped-def]
        self.calls += 1
        return self

    async def __aexit__(self, *_: object) -> None:
        return None


@pytest.fixture
def queue() -> ListingQueue:
    return ListingQueue()


@pytest.fixture
def external() -> ForbiddenSource:
    return ForbiddenSource()


@pytest.fixture
def make_client(session_factory, queue, external):  # type: ignore[no-untyped-def]
    def _make(*, now: dt.datetime = NOW, credentials: bool = True) -> AsyncClient:
        from src.api.routes import stock_search

        app = create_app()

        async def _session():  # type: ignore[no-untyped-def]
            async with session_factory() as s:
                yield s

        app.dependency_overrides[get_session] = _session
        app.dependency_overrides[stock_search.get_source] = lambda: external
        app.dependency_overrides[stock_search.get_now] = lambda: now
        app.dependency_overrides[stock_search.get_listing_settings] = (
            lambda: listing_settings(credentials=credentials))
        app.dependency_overrides[stock_search.get_listing_queue] = lambda: queue
        return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    return _make


async def search(make_client, q: str, **kwargs) -> dict:  # type: ignore[no-untyped-def]
    params = {"q": q, **{k: v for k, v in kwargs.items() if k == "limit"}}
    client_kwargs = {k: v for k, v in kwargs.items() if k != "limit"}
    async with make_client(**client_kwargs) as ac:
        res = await ac.get("/api/stocks/search", params=params)
    assert res.status_code == 200, res.text
    return res.json()


def lists_by_unit(body: dict) -> dict[str, dict]:
    return {item["unit"]: item for item in body["lists"]}


@pytest.fixture
async def seeded(session_factory) -> None:
    await seed(session_factory, "KOSPI", KOSPI_ROWS)
    await seed(session_factory, "KOSDAQ", KOSDAQ_ROWS)


class Test결과:
    async def test_외부_출처를_부르지_않는다(self, make_client, seeded, external) -> None:
        """FR-027 — 로컬 결과가 외부를 기다리면 로컬 목록을 둔 이유가 사라진다."""
        body = await search(make_client, "삼성")
        assert body["results"]
        assert external.calls == 0

    async def test_결과_필드(self, make_client, seeded) -> None:
        body = await search(make_client, "삼성전자")
        assert body["query"] == "삼성전자"
        first = body["results"][0]
        assert isinstance(first.pop("listingId"), int)
        assert first == {
            "country": "KR", "market": "KRX", "symbol": "005930.KS", "code": "005930",
            "name": "삼성전자", "nameEn": None, "currency": "KRW", "kind": "stock",
            "listedOn": "1975-06-11", "listingStatus": "listed", "match": "exact",
        }

    async def test_초성으로_보통주와_우선주를_함께_찾는다(self, make_client, seeded) -> None:
        body = await search(make_client, "ㅅㅅㅈㅈ")
        assert [r["name"] for r in body["results"]][:2] == ["삼성전자", "삼성전자우"]

    async def test_ETF와_리츠를_표시한다(self, make_client, seeded) -> None:
        """FR-025."""
        kodex = (await search(make_client, "kodex 200"))["results"][0]
        reit = (await search(make_client, "대신밸류"))["results"][0]
        assert (kodex["kind"], kodex["symbol"]) == ("etf", "069500.KS")
        assert (reit["kind"], reit["symbol"]) == ("reit", "0030R0.KS")

    async def test_코스닥은_KQ다(self, make_client, seeded) -> None:
        first = (await search(make_client, "에코프로"))["results"][0]
        assert (first["market"], first["symbol"]) == ("KRX", "247540.KQ")

    async def test_목록에서_빠진_종목을_표시한다(self, make_client, session_factory) -> None:
        """FR-019, FR-025 — 결과에 남기되 빠졌다는 사실을 드러낸다."""
        await seed(session_factory, "KOSPI", KOSPI_ROWS, now=YESTERDAY_NOW)
        await seed(session_factory, "KOSPI", KOSPI_ROWS[:3])
        first = (await search(make_client, "대신밸류"))["results"][0]
        assert first["listingStatus"] == "missing"

    async def test_상한을_넘으면_잘렸다고_알린다(self, make_client, seeded) -> None:
        """FR-024."""
        body = await search(make_client, "ㅅ", limit=2)
        assert len(body["results"]) == 2
        assert body["truncated"] is True
        assert (await search(make_client, "삼성전자"))["truncated"] is False


class Test목록_상태:
    async def test_받은_목록의_기준_시각(self, make_client, seeded) -> None:
        """FR-029."""
        lists = lists_by_unit(await search(make_client, "삼성"))
        # 단위마다 따로 싣는다 — 미국 3단위는 US4에서 더해졌다.
        assert set(lists) == {"KOSPI", "KOSDAQ", "NYSE", "NASDAQ", "AMEX"}
        assert lists["KOSPI"]["state"] == "ready"
        assert lists["KOSPI"]["asOf"] == "2026-10-02T00:05:12Z"

    async def test_목록이_없으면_오류가_아니라_200과_상태(self, make_client) -> None:
        """FR-028, SC-006 — "결과 없음"과 "목록 없음"을 화면이 가를 근거."""
        body = await search(make_client, "삼성")
        assert body["results"] == []
        for item in body["lists"]:
            assert item["state"] == "never" and item["asOf"] is None
            assert item["action"] == "wait"

    async def test_인증_정보가_없으면_사유와_할_일(self, make_client, queue) -> None:
        """FR-028a."""
        body = await search(make_client, "삼성", credentials=False)
        for item in body["lists"]:
            assert item["state"] == "never"
            assert item["reason"] == "auth_missing"
            assert item["action"] == "set_credentials"
        assert queue.size == 0

    async def test_어제_목록은_stale이고_갱신을_요청한다(
            self, make_client, session_factory, queue) -> None:
        await seed(session_factory, "KOSPI", KOSPI_ROWS, now=YESTERDAY_NOW)
        body = await search(make_client, "삼성")
        assert lists_by_unit(body)["KOSPI"]["state"] == "stale"
        assert body["results"]                        # 어제 목록으로 답한다
        assert queue.is_active("KOSPI")

    async def test_갱신_중에는_기다리지_않고_이전_목록으로_답한다(
            self, make_client, session_factory, queue) -> None:
        """FR-017 — 기다리게 하면 그날 첫 검색이 수 분 걸린다."""
        await seed(session_factory, "KOSPI", KOSPI_ROWS, now=YESTERDAY_NOW)
        async with session_factory() as s:
            assert await repo.try_lock(s, "KOSPI", NOW)
        body = await search(make_client, "삼성")
        kospi = lists_by_unit(body)["KOSPI"]
        assert kospi["state"] == "refreshing"
        assert kospi["asOf"] == "2026-10-01T00:05:12Z"
        assert kospi["action"] == "wait"
        assert body["results"]
        assert not queue.is_active("KOSPI")           # 이미 갱신 중이면 요청하지 않는다

    async def test_실패하면_사유와_기준_시각(self, make_client, session_factory) -> None:
        await seed(session_factory, "KOSPI", KOSPI_ROWS, now=YESTERDAY_NOW)
        failing = StubListingSource({"KOSPI": [KiwoomUnavailable("연결 끊김")]})
        await refresh_unit(session_factory, failing, "KOSPI", settings=listing_settings(),
                           now=lambda: NOW - dt.timedelta(minutes=10), blocker=AuthBlocker())
        kospi = lists_by_unit(await search(make_client, "삼성"))["KOSPI"]
        assert kospi["state"] == "failed"
        assert kospi["reason"] == "network"
        assert kospi["action"] == "retry_later"
        assert kospi["asOf"] == "2026-10-01T00:05:12Z"


class Test갱신_요청:
    async def test_오늘_받았으면_요청하지_않는다(self, make_client, seeded, queue) -> None:
        """FR-013, SC-005 — 국내 두 단위는 오늘 받았다(미국은 받지 않아 요청된다)."""
        await search(make_client, "삼성")
        assert not queue.is_active("KOSPI") and not queue.is_active("KOSDAQ")

    async def test_그날_첫_검색이면_단위마다_요청한다(self, make_client, queue) -> None:
        await search(make_client, "삼성")
        assert queue.is_active("KOSPI") and queue.is_active("KOSDAQ")

    async def test_여러_번_검색해도_한_번만_요청한다(self, make_client, queue) -> None:
        """FR-014 — 큐의 중복 거르기는 비용 절약이고, 정합성은 DB 점유가 지킨다."""
        for _ in range(3):
            await search(make_client, "삼성")
        assert queue.size == 5                    # 단위마다 한 번

    async def test_다음_날_자정이_지나면_다시_요청한다(
            self, make_client, session_factory, queue) -> None:
        await seed(session_factory, "KOSPI", [kr_row("000001", "가")],
                   now=dt.datetime(2026, 10, 1, 14, 0))       # KST 10-01 23:00
        await search(make_client, "가", now=dt.datetime(2026, 10, 1, 14, 59))
        assert not queue.is_active("KOSPI")
        await search(make_client, "가", now=dt.datetime(2026, 10, 1, 15, 0))   # KST 10-02 00:00
        assert queue.is_active("KOSPI")


class Test질의_검증:
    async def test_빈_질의는_400이다(self, make_client) -> None:
        async with make_client() as ac:
            for q in ("", "   "):
                res = await ac.get("/api/stocks/search", params={"q": q})
                assert res.status_code == 400
                assert res.json()["status"] == "invalid_query"

    async def test_limit이_범위를_넘으면_거절한다(self, make_client) -> None:
        async with make_client() as ac:
            res = await ac.get("/api/stocks/search", params={"q": "삼성", "limit": 51})
        assert res.status_code == 422
