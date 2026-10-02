"""외환 백그라운드 수집 요청 (T091) — 006 FR-046, FR-046a, research R6-10, analyze N1.

**001의 `ensure_background_job`은 작업을 실행시키지 않았다.** 작업 행과 점유를 만들고 반환할 뿐
워커의 큐에 넣지 않았다. 워커의 `run_once`는 점유를 새로 잡으려다 이미 잡혀 있으면 조용히 끝나므로,
그 작업은 **아무도 실행하지 않는 채 점유만 쥐고** 정리 루프가 회수할 때까지 그 통화의 수집을 막았다.
외환 화면의 자동 수집은 202를 돌려주고 진행 표시를 띄웠지만 실제로는 아무 일도 일어나지 않았다.

이 파일은 그 결함을 먼저 재현하고(고치기 전에는 실패한다), 고친 뒤의 **수집 표**를 검증한다.
"""
from __future__ import annotations

import asyncio
import contextlib
import datetime as dt

import pytest
from httpx2 import ASGITransport, AsyncClient
from sqlalchemy import func, select

from src.api.main import create_app
from src.api.services.collection_gate import ensure_background_job
from src.db.models import FxCollectionJob, FxCollectionLock, FxCoverage, JobStatus
from src.db.session import get_session
from src.worker.queue import StartQueue, get_queue
from src.worker.runner import worker_loop

from .conftest import StubSource

D = dt.date.fromisoformat
YESTERDAY = dt.date.today() - dt.timedelta(days=1)


async def count(session_factory, model) -> int:  # type: ignore[no-untyped-def]
    async with session_factory() as s:
        return int((await s.execute(select(func.count()).select_from(model))).scalar_one())


@pytest.fixture
async def client(session_factory, monkeypatch):  # type: ignore[no-untyped-def]
    # 수집 범위를 짧게 잡는다 — 스텁 출처라도 수십 년치 청크를 돌면 테스트가 느려진다.
    monkeypatch.setenv("ECOS_PROBE_START_USD", (YESTERDAY - dt.timedelta(days=200)).isoformat())
    app = create_app()

    async def _override():  # type: ignore[no-untyped-def]
        async with session_factory() as s:
            yield s

    app.dependency_overrides[get_session] = _override
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


async def chart_202(client: AsyncClient) -> dict:  # type: ignore[type-arg]
    res = await client.get("/api/fx/series", params={
        "currency": "USD", "from": (YESTERDAY - dt.timedelta(days=200)).isoformat(),
        "to": YESTERDAY.isoformat()})
    assert res.status_code == 202, res.text
    return res.json()


class Test결함_재현:
    async def test_202_뒤에_고아_점유가_남지_않는다(self, client, session_factory) -> None:
        """고치기 전: 작업과 점유가 생기고 큐는 비어 있다 — 아무도 실행하지 않는다."""
        await chart_202(client)
        assert await count(session_factory, FxCollectionLock) == 0
        assert await count(session_factory, FxCollectionJob) == 0
        assert get_queue().in_progress == "USD"

    async def test_202_뒤에_워커가_실제로_수집한다(self, client, session_factory, settings) -> None:
        """FR-046a — 외환 화면의 자동 수집이 이때부터 실제로 돈다."""
        await chart_202(client)
        queue = get_queue()
        source = StubSource({"USD": [(YESTERDAY.isoformat(), "1350.00")]})
        task = asyncio.create_task(worker_loop(session_factory, source, queue, settings=settings))
        try:
            async with asyncio.timeout(5):
                # 003 큐에는 완료 사건이 없어 상태를 본다.
                while queue.in_progress is not None:  # noqa: ASYNC110
                    await asyncio.sleep(0.05)
        finally:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

        assert source.requests, "202를 돌려주고도 수집하지 않았다"
        async with session_factory() as s:
            jobs = list((await s.execute(select(FxCollectionJob))).scalars())
            coverage = await s.get(FxCoverage, "USD")
        assert [j.status for j in jobs] == [JobStatus.SUCCEEDED]
        assert coverage is not None and coverage.covered_through == YESTERDAY
        assert await count(session_factory, FxCollectionLock) == 0


class Test수집_표:
    """research R6-10의 표. 작업 번호는 점유가 있을 때만 있다 (analyze N1)."""

    async def test_큐가_받으면_queued와_통화별_스트림(self, session_factory) -> None:
        queue = StartQueue()
        async with session_factory() as s:
            ticket = await ensure_background_job(s, "USD", queue=queue)
        assert (ticket.state, ticket.job_id, ticket.busy_with) == ("queued", None, None)
        assert ticket.progress_url == "/api/fx/collection/stream?currency=USD"
        assert queue.in_progress == "USD"

    async def test_이미_큐에_있으면_queued(self, session_factory) -> None:
        queue = StartQueue()
        await queue.request("USD")
        async with session_factory() as s:
            ticket = await ensure_background_job(s, "USD", queue=queue)
        assert ticket.state == "queued"
        assert queue.size == 1

    async def test_점유가_있으면_collecting과_작업_번호(self, session_factory) -> None:
        async with session_factory() as s:
            job = FxCollectionJob(currency_code="USD", range_start=D("2020-01-01"),
                                  range_end=YESTERDAY, status=JobStatus.RUNNING,
                                  chunks_total=4, chunks_done=1)
            s.add(job)
            await s.flush()
            s.add(FxCollectionLock(scope="collection", currency_code="USD", job_id=job.id))
            await s.commit()
            job_id = int(job.id)
        queue = StartQueue()
        async with session_factory() as s:
            ticket = await ensure_background_job(s, "USD", queue=queue)
        assert (ticket.state, ticket.job_id) == ("collecting", job_id)
        assert ticket.progress_url == f"/api/fx/progress?jobId={job_id}"
        assert queue.size == 0

    async def test_다른_통화_처리_중이면_waiting과_그_통화(self, session_factory) -> None:
        queue = StartQueue()
        await queue.request("JPY")
        async with session_factory() as s:
            ticket = await ensure_background_job(s, "USD", queue=queue)
        assert (ticket.state, ticket.busy_with, ticket.job_id) == ("waiting", "JPY", None)
        assert ticket.progress_url == "/api/fx/collection/stream?currency=USD"

    async def test_큐가_거절해도_아무것도_남기지_않는다(self, session_factory) -> None:
        """미리 작업을 만들면 실행되지 않는 작업이 다시 생긴다."""
        queue = StartQueue()
        await queue.request("JPY")
        async with session_factory() as s:
            await ensure_background_job(s, "USD", queue=queue)
        assert await count(session_factory, FxCollectionJob) == 0
        assert await count(session_factory, FxCollectionLock) == 0


class Test외환_화면의_202:
    """contracts/rest-api 6a절 — `jobId`가 `null`일 수 있고 `state`·`busyWith`가 더해진다."""

    async def test_차트(self, client) -> None:
        body = await chart_202(client)
        assert body["state"] == "queued"
        assert body["jobId"] is None
        assert body["busyWith"] is None
        assert body["progressUrl"] == "/api/fx/collection/stream?currency=USD"

    @pytest.mark.parametrize(("module", "path", "params"), [
        ("daily", "/api/fx/daily", {"currency": "USD"}),
        ("latest", "/api/fx/latest", {"currency": "USD"}),
        ("rates", "/api/fx/rates/USD", {"date": "2026-01-02"}),
    ])
    async def test_일별표_최신_날짜_조회(
            self, client, monkeypatch, module: str, path: str, params: dict[str, str]) -> None:
        """세 경로는 하루치만 보므로 결측이 임계값을 넘지 않는다 — 백그라운드 경로로 고정한다
        (`test_daily_period_contract`와 같은 방법)."""
        import importlib

        from src.api.services.collection_gate import CollectionDecision

        route = importlib.import_module(f"src.api.routes.{module}")
        monkeypatch.setattr(
            route, "decide_collection", lambda **_: CollectionDecision.BACKGROUND)
        res = await client.get(path, params=params)
        assert res.status_code == 202, res.text
        body = res.json()
        assert body["state"] == "queued" and body["jobId"] is None
        assert body["progressUrl"] == "/api/fx/collection/stream?currency=USD"

    async def test_다른_통화_처리_중이면_waiting(self, client) -> None:
        assert await get_queue().request("JPY")
        body = await chart_202(client)
        assert body["state"] == "waiting" and body["busyWith"] == "JPY"


class Test대기_해소_신호:
    """`waiting`인 화면은 통화별 스트림을 구독하다 다른 통화의 수집이 끝나면 다시 요청한다(R6-10).

    003의 스트림은 `busyWith`를 **연결할 때 한 번만** 읽어 끝까지 같은 값을 보냈다. 그러면 다른
    통화가 끝나도 화면은 그 사실을 알 길이 없다.
    """

    async def test_스트림의_busyWith가_프레임마다_바뀐다(self, session_factory, settings,
                                                          monkeypatch) -> None:
        import json

        from src.api import collection_stream

        monkeypatch.setattr(collection_stream, "HEARTBEAT_SECONDS", 0.01)
        queue = StartQueue()
        await queue.request("JPY")
        frames: list[dict] = []  # type: ignore[type-arg]
        async with session_factory() as s:
            stream = collection_stream.stream_body(
                s, "USD", settings, busy_with_fn=lambda: queue.in_progress, max_frames=3)
            async for frame in stream:
                if frame.startswith("event: idle"):
                    frames.append(json.loads(frame.split("data: ", 1)[1]))
                    if len(frames) == 1:
                        queue.done("JPY")
        assert frames[0]["busyWith"] == "JPY"
        assert frames[-1]["busyWith"] is None
