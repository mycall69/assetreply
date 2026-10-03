"""코인 검색 API·목록 갱신 진행 (T015) — 007 FR-003~FR-006, FR-005b, SC-002, SC-002a,
contracts/rest-api `GET /api/crypto/search`·`GET /api/crypto/list/progress`.

**목록이 없어도 오류가 아니다.** 200에 `list`로 알린다 — 화면이 "결과 없음"과 "목록 없음"을 가른다.
**출처를 부르지 않고, 갱신을 기다리지 않는다**(006 FR-017과 같다). 실제 갱신은 `lifespan`이 띄운
목록 갱신 줄이 한다 — 이 경로를 거치지 않는 테스트는 줄을 등록하지 않아도 통과한다(006 plan
Complexity Tracking D1). 그래서 앱 수명을 거치는 테스트를 하나 둔다.
"""
from __future__ import annotations

import asyncio
import dataclasses
import datetime as dt
import json
from typing import Self

import pytest
from httpx2 import ASGITransport, AsyncClient

from src.api.main import create_app
from src.api.services.crypto_index import get_coin_index
from src.api.services.crypto_list_refresh import refresh_coins
from src.db.session import get_session
from src.ingestion.investing.errors import InvestingBlocked, InvestingNetworkError
from src.repository import crypto_list_lock as locks
from src.search.hangul import choseong_string
from src.worker.crypto_list_queue import CryptoListQueue
from tests.integration.crypto_support import (
    EN,
    KO,
    NOW,
    StubCoinSource,
    compact_bodies,
    crypto_settings,
    fixture,
    reset_crypto_list_state,
    seed,
)

LATER = NOW + dt.timedelta(days=8)


@pytest.fixture(autouse=True)
def _list_state():
    reset_crypto_list_state()
    yield
    reset_crypto_list_state()


@pytest.fixture
def queue() -> CryptoListQueue:
    return CryptoListQueue()


@pytest.fixture
def make_client(session_factory, queue):  # type: ignore[no-untyped-def]
    def _make(*, now: dt.datetime = NOW) -> AsyncClient:
        from src.api.routes import crypto_list_progress, crypto_search

        app = create_app()

        async def _session():  # type: ignore[no-untyped-def]
            async with session_factory() as s:
                yield s

        app.dependency_overrides[get_session] = _session
        app.dependency_overrides[crypto_search.get_now] = lambda: now
        # 함수를 그대로 넘기면 FastAPI가 `**over`를 쿼리 매개변수로 읽는다
        app.dependency_overrides[crypto_search.get_crypto_list_settings] = (
            lambda: crypto_settings())
        app.dependency_overrides[crypto_search.get_crypto_list_queue] = lambda: queue
        app.dependency_overrides[crypto_list_progress.get_crypto_list_queue] = lambda: queue
        return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    return _make


async def search(make_client, q: str, *, now: dt.datetime = NOW, **params: object) -> dict:  # type: ignore[no-untyped-def]
    async with make_client(now=now) as client:
        response = await client.get("/api/crypto/search", params={"q": q, **params})
    assert response.status_code == 200, response.text
    return response.json()


async def seed_compact(session_factory) -> None:  # type: ignore[no-untyped-def]
    en, ko = compact_bodies()
    await seed(session_factory, en=en, ko=ko)


class Test찾기:
    @pytest.mark.parametrize("q", ["btc", "BTC", "Bitcoin", "bitcoin", "비트코인", "ㅂㅌㅋㅇ"])
    async def test_비트코인이_맨_위다(self, session_factory, make_client, q: str) -> None:
        await seed(session_factory)
        body = await search(make_client, q)
        top = body["results"][0]
        assert (top["symbol"], top["name"], top["nameKo"], top["currency"], top["rank"]) == (
            "BTC", "Bitcoin", "비트코인", "USD", 1)
        assert top["listStatus"] == "listed"
        assert top["slug"] == "bitcoin"
        assert top["firstAvailableDate"] is None
        assert top["match"] in ("exact", "prefix")

    async def test_결과_한_줄의_식별자는_코인_id다(self, session_factory, make_client) -> None:
        await seed(session_factory)
        a = (await search(make_client, "btc"))["results"][0]
        b = (await search(make_client, "비트코인"))["results"][0]
        assert isinstance(a["coinId"], int) and a["coinId"] == b["coinId"]

    async def test_한글_이름이_없으면_null이다(self, session_factory, make_client) -> None:
        await seed(session_factory)
        top = (await search(make_client, "bnb"))["results"][0]
        assert (top["symbol"], top["nameKo"]) == ("BNB", None)

    async def test_같은_심볼은_순위순으로_따로_보인다(self, session_factory, make_client) -> None:
        """FR-004 — "max"를 치면 MAX 심볼 코인 다섯이 이름·순위로 구별된다. 순위는 픽스처(T001)의
        값이다 — ui-wireframes C2의 예시는 계획 때 따로 잰 값이라 조금 다르다."""
        await seed_compact(session_factory)
        results = (await search(make_client, "max"))["results"][:5]
        assert [r["symbol"] for r in results] == ["MAX"] * 5
        assert [r["rank"] for r in results] == [764, 1340, 2758, 3085, 5403]
        assert len({r["coinId"] for r in results}) == 5
        assert results[0]["name"] == "MAX Exchange Token"

    async def test_목록에서_빠진_코인은_남기고_표시한다(self, session_factory, make_client) -> None:
        await seed(session_factory)
        await refresh_coins(session_factory, StubCoinSource({"en": [[EN[0]]], "ko": [KO]}),
                            settings=crypto_settings(), now=lambda: LATER)
        last = json.loads(fixture("coins_en_last.json"))["coins"][0]
        body = await search(make_client, last["name"], now=LATER)
        found = [r for r in body["results"] if r["name"] == last["name"]]
        assert found and found[0]["listStatus"] == "missing"

    @pytest.mark.parametrize("q", ["", "   "])
    async def test_검색어가_비면_400이다(self, make_client, q: str) -> None:
        async with make_client() as client:
            response = await client.get("/api/crypto/search", params={"q": q})
        assert response.status_code == 400
        assert response.json()["status"] == "invalid_query"

    async def test_한도를_넘으면_잘렸다고_알린다(self, session_factory, make_client) -> None:
        await seed(session_factory)
        body = await search(make_client, "c", limit=3)
        assert len(body["results"]) == 3 and body["truncated"] is True


class Test목록_상태:
    async def test_받은_적이_없으면_never이고_갱신을_요청만_한다(self, make_client, queue) -> None:
        body = await search(make_client, "btc")
        assert body["results"] == []
        assert body["list"]["state"] == "never"
        assert body["list"]["asOf"] is None
        assert body["list"]["koreanNames"]["state"] == "never"
        assert queue.is_active("coins")

    async def test_받아_두었으면_ready와_기준_시각이다(
        self, session_factory, make_client, queue
    ) -> None:
        await seed(session_factory)
        body = await search(make_client, "btc")
        assert body["list"]["state"] == "ready"
        assert body["list"]["asOf"] == "2026-10-03T00:05:12Z"
        assert body["list"]["koreanNames"] == {"state": "ready", "asOf": "2026-10-03T00:05:12Z"}
        assert not queue.is_active("coins")

    async def test_7일이_지나면_이전_목록으로_찾으며_갱신_중이다(
        self, session_factory, make_client, queue
    ) -> None:
        await seed(session_factory)
        body = await search(make_client, "btc", now=LATER)
        assert body["results"][0]["symbol"] == "BTC"
        assert (body["list"]["state"], body["list"]["asOf"]) == (
            "refreshing", "2026-10-03T00:05:12Z")
        assert queue.is_active("coins")

    async def test_갱신_중이면_refreshing이다(self, session_factory, make_client) -> None:
        await seed(session_factory)
        async with session_factory() as s:
            assert await locks.try_lock(s, NOW)
        body = await search(make_client, "btc")
        assert body["list"]["state"] == "refreshing"

    async def test_갱신이_실패했으면_사유와_이전_기준_시각이다(
        self, session_factory, make_client
    ) -> None:
        await seed(session_factory)
        await refresh_coins(session_factory, StubCoinSource({"en": [[InvestingBlocked("막힘")]]}),
                            settings=crypto_settings(), now=lambda: LATER)
        body = await search(make_client, "btc", now=LATER)
        assert body["results"][0]["symbol"] == "BTC"
        assert body["list"] == {
            "state": "failed", "asOf": "2026-10-03T00:05:12Z", "reason": "blocked",
            "koreanNames": {"state": "ready", "asOf": "2026-10-03T00:05:12Z"}}

    async def test_한국어_판만_실패했으면_그_사실을_따로_알린다(
        self, session_factory, make_client
    ) -> None:
        await seed(session_factory)
        await refresh_coins(
            session_factory, StubCoinSource({"en": [EN], "ko": [[InvestingNetworkError("끊김")]]}),
            settings=crypto_settings(), now=lambda: LATER)
        body = await search(make_client, "비트코인", now=LATER)
        assert body["results"][0]["symbol"] == "BTC"
        assert body["list"]["state"] == "ready"
        assert body["list"]["koreanNames"] == {
            "state": "failed", "asOf": "2026-10-03T00:05:12Z", "reason": "network"}


def events(frames: list[str]) -> list[tuple[str, dict]]:
    """SSE 프레임을 (이름, 본문)으로."""
    parsed: list[tuple[str, dict]] = []
    for frame in frames:
        lines = dict(line.split(": ", 1) for line in frame.strip().splitlines())
        parsed.append((lines["event"], json.loads(lines["data"])))
    return parsed


async def stream(  # type: ignore[no-untyped-def]
    session_factory, queue: CryptoListQueue, *, max_frames: int = 1
) -> list[tuple[str, dict]]:
    from src.api.routes.crypto_list_progress import stream_body

    async with session_factory() as s:
        return events([f async for f in stream_body(s, queue=queue, max_frames=max_frames)])


class Test진행_스트림:
    async def test_받은_적도_갱신_중도_아니면_idle을_보내고_닫는다(
        self, session_factory, queue
    ) -> None:
        assert await stream(session_factory, queue, max_frames=5) == [("idle", {})]

    async def test_갱신이_끝났으면_completed를_보내고_닫는다(self, session_factory, queue) -> None:
        await seed(session_factory)
        assert await stream(session_factory, queue, max_frames=5) == [(
            "completed", {"asOf": "2026-10-03T00:05:12Z", "coins": 154, "koreanNames": "ready"})]

    async def test_갱신이_실패했으면_사유를_보내고_닫는다(self, session_factory, queue) -> None:
        await refresh_coins(session_factory, StubCoinSource({"en": [[InvestingBlocked("막힘")]]}),
                            settings=crypto_settings(), now=lambda: NOW)
        [(name, body)] = await stream(session_factory, queue, max_frames=5)
        assert name == "failed"
        assert body["reason"] == "blocked" and body["message"]

    async def test_요청이_대기_중이면_0쪽으로_시작한다(self, session_factory, queue) -> None:
        queue.request("coins")
        assert await stream(session_factory, queue) == [("snapshot", {
            "edition": None, "pagesDone": 0, "pagesExpected": None, "coinsSeen": 0})]

    async def test_쪽마다_늘고_판이_바뀌면_0부터다(self, session_factory, queue) -> None:
        frames: list[tuple[str, dict]] = []

        async def look(edition: str, page_no: int) -> None:
            frames.extend(await stream(session_factory, queue))

        source = StubCoinSource({"en": [EN], "ko": [KO]})
        source.before_page = look
        await refresh_coins(session_factory, source, settings=crypto_settings(), now=lambda: NOW)
        assert frames == [
            ("snapshot", {"edition": "en", "pagesDone": 0, "pagesExpected": None, "coinsSeen": 0}),
            ("snapshot", {"edition": "en", "pagesDone": 1, "pagesExpected": None,
                          "coinsSeen": 100}),
            ("snapshot", {"edition": "ko", "pagesDone": 0, "pagesExpected": None, "coinsSeen": 0}),
        ]

    async def test_다시_받을_때는_이전_코인_수로_전체_쪽_수를_어림한다(
        self, session_factory, queue
    ) -> None:
        await seed(session_factory)
        frames: list[tuple[str, dict]] = []

        async def look(edition: str, page_no: int) -> None:
            if page_no == 1:
                frames.extend(await stream(session_factory, queue))

        source = StubCoinSource({"en": [EN], "ko": [KO]})
        source.before_page = look
        await refresh_coins(session_factory, source, settings=crypto_settings(), now=lambda: LATER)
        # 영문 154개 → 2쪽, 한국어 100개 → 1쪽
        assert [(b["edition"], b["pagesExpected"]) for _, b in frames] == [("en", 2), ("ko", 1)]

    async def test_스트림이_완료까지_이어진다(self, session_factory, queue, monkeypatch) -> None:
        """점유가 풀리면 끝난다 — 갱신 줄이 큐에서 아직 빼지 않았어도 "0쪽"으로 되돌아가지
        않는다."""
        from src.api.routes import crypto_list_progress

        monkeypatch.setattr(crypto_list_progress, "POLL_SECONDS", 0.01)
        gate = asyncio.Event()
        entered = asyncio.Event()

        async def hold(edition: str, page_no: int) -> None:
            entered.set()
            await gate.wait()

        source = StubCoinSource({"en": [EN], "ko": [KO]})
        source.before_page = hold
        # 갱신 줄이 꺼낸 요청 — 줄은 갱신이 끝난 뒤에야 큐에서 뺀다
        queue.request("coins")
        task = asyncio.create_task(refresh_coins(
            session_factory, source, settings=crypto_settings(), now=lambda: NOW))
        await asyncio.wait_for(entered.wait(), timeout=3)
        collected: list[str] = []

        async def consume() -> None:
            async with session_factory() as s:
                async for frame in crypto_list_progress.stream_body(s, queue=queue):
                    collected.append(frame)
                    if len(collected) == 2:
                        gate.set()

        await asyncio.wait_for(consume(), timeout=5)
        await task
        parsed = events(collected)
        assert parsed[0][0] == "snapshot" and parsed[-1][0] == "completed"
        assert all(body["edition"] is not None for name, body in parsed if name == "snapshot")

    async def test_머리글이_변환을_막는다(self, queue) -> None:
        from src.api.routes.crypto_list_progress import get_list_progress

        response = await get_list_progress(session=None, queue=queue)  # type: ignore[arg-type]
        assert "no-transform" in response.headers["cache-control"]
        assert response.headers["x-accel-buffering"] == "no"

    async def test_경로로_구독할_수_있다(self, session_factory, make_client) -> None:
        await seed(session_factory)
        async with make_client() as client:
            response = await client.get("/api/crypto/list/progress")
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        assert events([response.text])[0][0] == "completed"


class Test상위_50개:
    """SC-002 — 시가총액 상위 50개 각각을 영문 이름과 심볼로 찾으면 95% 이상이 맨 위다. 한글 이름이
    있는 코인은 한글과 초성으로도 95% 이상이다(analyze M1). 실제 목록(3,654개, T001)으로 잰다 —
    비율과 놓친 검색어를 실패 메시지에 싣는다."""

    async def test_영문_이름과_심볼(self, session_factory) -> None:
        await seed_compact(session_factory)
        async with session_factory() as s:
            index = await get_coin_index(s)
        top = sorted((v for v in index.views.values() if v.rank is not None),
                     key=lambda v: v.rank or 0)[:50]
        queries = [(v, q) for v in top for q in (v.name_en, v.symbol)]
        missed = [q for v, q in queries if index.search.search(q, 1).hits[0].entry.key != v.coin_id]
        ratio = 1 - len(missed) / len(queries)
        assert ratio >= 0.95, f"맨 위 비율 {ratio:.3f} — 놓친 검색어 {missed}"

    async def test_한글_이름과_초성(self, session_factory) -> None:
        await seed_compact(session_factory)
        async with session_factory() as s:
            index = await get_coin_index(s)
        top = sorted((v for v in index.views.values() if v.rank is not None),
                     key=lambda v: v.rank or 0)[:50]
        korean = [v for v in top if v.name_ko]
        assert korean, "상위 50개에 한글 이름이 하나도 없다 — 한국어 판을 짝짓지 못했다"
        queries = [(v, q) for v in korean
                   for q in (v.name_ko or "", choseong_string(v.name_ko or ""))]
        missed = [q for v, q in queries if index.search.search(q, 1).hits[0].entry.key != v.coin_id]
        ratio = 1 - len(missed) / len(queries)
        assert ratio >= 0.95, f"맨 위 비율 {ratio:.3f} — 놓친 검색어 {missed}"


class _Resp:
    def __init__(self, body: str) -> None:
        self._body = body
        self.status = 200

    async def text(self) -> str:
        return self._body

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *exc: object) -> None:
        return None


class _FakeSession:
    """출처 흉내. 목록 API만 답한다 — 판(`domain_id`)과 커서로 픽스처를 고른다."""

    def __init__(self) -> None:
        self.requests: list[dict[str, str]] = []

    def get(self, url: str, *, params: dict[str, str] | None = None, **_: object) -> _Resp:
        params = dict(params or {})
        self.requests.append(params)
        assert url.endswith("/v1/crypto/coins"), url
        if "cursor" in params:
            return _Resp(fixture("coins_en_last.json"))
        return _Resp(fixture("coins_ko_p1.json" if params["domain_id"] == "18"
                             else "coins_en_p1.json"))

    async def close(self) -> None:
        return None


class Test앱_수명:
    """**실행 주체**를 거친다 — 검색이 요청하고, `lifespan`이 띄운 목록 갱신 줄이 받아 끝낸다(006
    D1의 교훈)."""

    async def test_첫_검색은_기다리지_않고_갱신_줄이_목록을_받는다(
        self, session_factory, monkeypatch
    ) -> None:
        from fastapi.testclient import TestClient

        from src.api.routes import crypto_list_progress
        from src.ingestion.investing import client as investing_client
        from src.worker.crypto_list_queue import get_crypto_list_queue

        real = investing_client.InvestingClient
        fake = _FakeSession()

        async def no_sleep(_: float) -> None:
            return None

        def make(settings, **_: object):  # type: ignore[no-untyped-def]
            fast = dataclasses.replace(settings, investing_min_interval_ms=0)
            return real(fast, session=fake, sleep=no_sleep)  # type: ignore[arg-type]

        monkeypatch.setattr(investing_client, "InvestingClient", make)
        monkeypatch.setattr(crypto_list_progress, "POLL_SECONDS", 0.02)

        with TestClient(create_app()) as client:
            first = client.get("/api/crypto/search", params={"q": "btc"})
            assert first.status_code == 200
            assert first.json()["list"]["state"] in ("never", "refreshing")
            with client.stream("GET", "/api/crypto/list/progress") as response:
                text = "".join(response.iter_text())
            assert "event: completed" in text, text
            after = client.get("/api/crypto/search", params={"q": "비트코인"}).json()

        assert after["results"][0]["symbol"] == "BTC"
        assert after["list"]["state"] == "ready"
        assert not get_crypto_list_queue().is_active("coins")
        assert [p["domain_id"] for p in fake.requests] == ["1", "1", "18", "18"]
