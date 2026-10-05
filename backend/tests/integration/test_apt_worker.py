"""부동산 수집 줄 (T019) — 009 FR-011, FR-012.

**실행 주체를 거친다**(006 D1). 앱 기동이 부동산 수집 태스크를 띄우고(태스크 8개), 동 선택 요청이
넣은 일감을 그 태스크가 꺼내 돌린다 — 내부 함수를 직접 부르지 않는다. 태스크 안에서 실거래 줄과 목록
줄은 서로 기다리지 않는다(실거래 전체 이력 약 280회가 행정구역 갱신을 막지 않는다). 다른 자산군
수집과도 서로 기다리지 않는다. 시뮬레이션 요청(202)이 큐를 거치는 경로는 시뮬레이션 API와 함께
본다(Phase 4).
"""
from __future__ import annotations

import asyncio
import contextlib
import datetime as dt
import inspect

import pytest
from httpx2 import ASGITransport, AsyncClient

from src.api import main
from src.api.main import create_app
from src.api.services import realestate_lists
from src.config.settings import load_settings
from src.db.models import AptCollectionJob, DepositCollectionJob, JobStatus
from src.db.session import get_session
from src.repository import apt_job, deposit_job
from src.worker import apt_worker, deposit_worker
from src.worker.apt_queue import AptQueue, AptWork, get_apt_list_queue, get_apt_trade_queue
from src.worker.deposit_queue import DepositQueue, DepositWork
from tests.integration.apt_support import NOW_UTC, FakePortal, apt_settings, portal_client
from tests.integration.deposit_support import NOW_UTC as DEPOSIT_NOW
from tests.integration.deposit_support import StubDepositSource

D = dt.date.fromisoformat
SETTINGS = apt_settings(apt_trade_probe_start=D("2023-01-01"))  # 2023-01 ~ 2023-10


def test_lifespan이_부동산_수집_태스크와_기동_정리를_등록한다() -> None:
    """등록을 빠뜨리면 요청이 큐에 쌓이기만 하고 실행되지 않는다. 태스크는 8개다(FX·정리·주식·목록·
    코인 목록·코인 시세·예금 금리·부동산)."""
    body = inspect.getsource(main.lifespan)
    assert "apt_worker_loop(" in body
    assert "apt_startup(" in body
    assert body.count("asyncio.create_task(") == 8


async def test_기동_시_남은_부동산_점유를_회수한다(session_factory) -> None:  # type: ignore[no-untyped-def]
    async with session_factory() as s:
        trade, _ = await apt_job.acquire_or_get_running(s, "trade", "11710", total=10)
        region, _ = await apt_job.acquire_or_get_running(s, "region", "regions", total=0)
        await s.commit()
    await apt_worker.startup(session_factory)
    async with session_factory() as s:
        assert await apt_job.running_job_id(s, "trade", "11710") is None
        assert await apt_job.running_job_id(s, "region", "regions") is None
        jobs = [await s.get(AptCollectionJob, job_id) for job_id in (trade, region)]
    for job in jobs:
        assert job is not None and job.status is JobStatus.FAILED
        kind, reason = apt_job.split_error(job.last_error)
        assert kind == "network" and reason is not None and "점유 회수" in reason


class Gate:
    """실거래 응답을 문이 열릴 때까지 붙잡는다."""

    def __init__(self) -> None:
        self.open, self.entered = asyncio.Event(), asyncio.Event()

    def install(self, portal: FakePortal) -> None:
        gate = self
        original = portal._default

        class Held:
            def __init__(self, inner) -> None:  # type: ignore[no-untyped-def]
                self.inner, self.status = inner, inner.status

            async def text(self) -> str:
                gate.entered.set()
                await gate.open.wait()
                return await self.inner.text()  # type: ignore[no-any-return]

            async def __aenter__(self):  # type: ignore[no-untyped-def]
                return self

            async def __aexit__(self, *exc: object) -> None:
                return None

        portal.overrides.append(
            lambda api, q: Held(original(api, q)) if api == "trade" else None)  # type: ignore[arg-type,return-value]


async def run_loop(session_factory, source, trade_queue: AptQueue, list_queue: AptQueue):  # type: ignore[no-untyped-def]
    return asyncio.create_task(apt_worker.apt_worker_loop(
        session_factory, source, trade_queue, list_queue, settings=SETTINGS,
        clock=lambda: NOW_UTC))


async def stop(*tasks: asyncio.Task) -> None:  # type: ignore[type-arg]
    for task in tasks:
        task.cancel()
    for task in tasks:
        with contextlib.suppress(asyncio.CancelledError):
            await task


async def idle(queue: AptQueue, kind: str, target: str, seconds: float = 15) -> None:
    async with asyncio.timeout(seconds):
        while queue.is_active(kind, target):  # noqa: ASYNC110 — 큐에 완료 사건이 없다
            await asyncio.sleep(0.02)


@pytest.fixture
async def client(session_factory):  # type: ignore[no-untyped-def]
    portal = FakePortal()
    source = portal_client(portal, SETTINGS)
    app = create_app()

    async def _session():  # type: ignore[no-untyped-def]
        async with session_factory() as s:
            yield s

    app.dependency_overrides[get_session] = _session
    app.dependency_overrides[realestate_lists.get_realestate_now] = lambda: NOW_UTC
    app.dependency_overrides[realestate_lists.get_realestate_settings] = lambda: SETTINGS
    app.dependency_overrides[realestate_lists.get_realestate_source] = lambda: source
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as http:
        yield http, source


async def test_동_선택이_큐를_거쳐_실거래를_받는다(client, session_factory) -> None:  # type: ignore[no-untyped-def]
    http, source = client
    task = await run_loop(session_factory, source, get_apt_trade_queue(), get_apt_list_queue())
    try:
        first = await http.get("/api/realestate/regions")
        assert first.status_code == 202
        await idle(get_apt_list_queue(), "region", "regions")
        body = (await http.get("/api/realestate/complexes", params={"umd": "1171010700"})).json()
        assert body["trades"]["state"] == "collecting"
        await idle(get_apt_trade_queue(), "trade", "11710")
        await idle(get_apt_list_queue(), "complex_details", "1171010700")
    finally:
        await stop(task)
    after = (await http.get("/api/realestate/complexes", params={"umd": "1171010700"})).json()
    assert after["trades"]["state"] == "collected"
    assert after["details"]["pending"] is False
    assert any(i["sources"] == ["trade"] for i in after["items"])


async def test_실거래_수집_중에도_행정구역_갱신이_끝난다(session_factory) -> None:  # type: ignore[no-untyped-def]
    portal = FakePortal()
    gate = Gate()
    gate.install(portal)
    source = portal_client(portal, SETTINGS)
    trade_queue, list_queue = AptQueue(), AptQueue()
    async with session_factory() as s:
        trade_job, _ = await apt_job.acquire_or_get_running(s, "trade", "11710", total=10)
        region_job, _ = await apt_job.acquire_or_get_running(s, "region", "regions", total=0)
        await s.commit()
    trade_queue.request(AptWork(trade_job, "trade", "11710"))
    task = await run_loop(session_factory, source, trade_queue, list_queue)
    try:
        await asyncio.wait_for(gate.entered.wait(), timeout=5)
        list_queue.request(AptWork(region_job, "region", "regions"))
        await idle(list_queue, "region", "regions")
        assert trade_queue.is_active("trade", "11710"), "실거래는 아직 출처에서 기다린다"
        gate.open.set()
        await idle(trade_queue, "trade", "11710")
    finally:
        await stop(task)
    async with session_factory() as s:
        jobs = [await s.get(AptCollectionJob, j) for j in (trade_job, region_job)]
    assert [j.status for j in jobs if j is not None] == [JobStatus.SUCCEEDED, JobStatus.SUCCEEDED]


async def test_예금_수집과_서로_기다리지_않는다(session_factory) -> None:  # type: ignore[no-untyped-def]
    portal = FakePortal()
    gate = Gate()
    gate.install(portal)
    trade_queue, deposit_queue = AptQueue(), DepositQueue()
    async with session_factory() as s:
        trade_job, _ = await apt_job.acquire_or_get_running(s, "trade", "11710", total=10)
        deposit_id, _ = await deposit_job.acquire_or_get_running(
            s, "commercial_bank", D("2020-01-01"), D("2026-10-01"), months_total=82)
        await s.commit()
    trade_queue.request(AptWork(trade_job, "trade", "11710"))
    deposit_queue.request(DepositWork(job_id=deposit_id, institution="commercial_bank",
                                      start_month=D("2020-01-01"), end_month=D("2026-10-01")))
    tasks = [
        await run_loop(session_factory, portal_client(portal, SETTINGS), trade_queue, AptQueue()),
        asyncio.create_task(deposit_worker.deposit_worker_loop(
            session_factory, StubDepositSource(), deposit_queue, settings=load_settings(),
            clock=lambda: DEPOSIT_NOW)),
    ]
    try:
        await asyncio.wait_for(gate.entered.wait(), timeout=5)
        async with asyncio.timeout(10):
            while deposit_queue.is_active("commercial_bank"):  # noqa: ASYNC110
                await asyncio.sleep(0.02)
        assert trade_queue.is_active("trade", "11710")
        gate.open.set()
        await idle(trade_queue, "trade", "11710")
    finally:
        await stop(*tasks)
    async with session_factory() as s:
        deposit = await s.get(DepositCollectionJob, deposit_id)
    assert deposit is not None and deposit.status is JobStatus.SUCCEEDED
