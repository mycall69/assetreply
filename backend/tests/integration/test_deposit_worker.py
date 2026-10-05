"""예금 금리 수집 줄 (T015) — 008 FR-011~FR-013, SC-012, research R8-6·R8-9.

**실행 주체를 거친다**(006 D1). 수집 엔진을 만들어 두고 부르는 주체를 두지 않으면 작업이 "진행
중"으로 박힌다(003·005의 교훈). 예금 수집은 **환율 수집과 다른 줄**이다 — 같은 ECOS 출처라 호출
한도는 관문으로 함께 지키지만(contract test_ecos_gate), 한쪽 작업이 다른 쪽을 기다리지는 않는다.
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
from src.config.settings import load_settings
from src.db.models import DepositCollectionJob, JobStatus
from src.db.session import get_session
from src.ingestion.protocols import FetchResult
from src.repository import deposit_job
from src.worker import deposit_worker
from src.worker.deposit_queue import DepositQueue, DepositWork, get_deposit_queue
from src.worker.queue import StartQueue
from src.worker.runner import worker_loop
from tests.integration.conftest import StubSource
from tests.integration.deposit_support import NOW_UTC, TODAY, StubDepositSource

D = dt.date.fromisoformat


def test_lifespan이_예금_수집_줄과_기동_정리를_등록한다() -> None:
    """등록을 빠뜨리면 요청이 큐에 쌓이기만 하고 실행되지 않는다. 태스크는 8개다(FX·정리·주식·목록·
    코인 목록·코인 시세·예금 금리·부동산 — 009가 마지막을 더했다)."""
    body = inspect.getsource(main.lifespan)
    assert "deposit_worker_loop(" in body
    assert "deposit_startup(" in body
    assert body.count("asyncio.create_task(") == 8


async def test_기동_시_남은_예금_점유를_회수한다(session_factory) -> None:  # type: ignore[no-untyped-def]
    async with session_factory() as s:
        job_id, _ = await deposit_job.acquire_or_get_running(
            s, "saemaul", D("2020-01-01"), D("2026-10-01"), months_total=82)
        await s.commit()
    await deposit_worker.startup(session_factory)
    async with session_factory() as s:
        assert await deposit_job.running_job_id(s, "saemaul") is None
        job = await s.get(DepositCollectionJob, job_id)
    assert job is not None and job.status is JobStatus.FAILED
    assert deposit_job.split_error(job.last_error)[0] == "network"


@pytest.fixture
async def client(session_factory, monkeypatch):  # type: ignore[no-untyped-def]
    monkeypatch.setattr("src.api.services.deposit_simulation.kst_today", lambda: TODAY)
    app = create_app()

    async def _session():  # type: ignore[no-untyped-def]
        async with session_factory() as s:
            yield s

    app.dependency_overrides[get_session] = _session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        yield c


async def test_시뮬레이션_요청이_큐를_거쳐_수집을_끝내고_결과가_나온다(  # type: ignore[no-untyped-def]
        client, session_factory) -> None:
    """내부 함수를 직접 부르지 않는다 — 202가 넣은 일감을 수집 줄이 꺼내 돌린다."""
    params = {"institution": "commercial_bank", "start": "2020-01-15", "principal": "10000000"}
    first = await client.get("/api/deposit/simulation", params=params)
    assert first.status_code == 202
    queue = get_deposit_queue()
    task = asyncio.create_task(deposit_worker.deposit_worker_loop(
        session_factory, StubDepositSource(), queue, settings=load_settings(),
        clock=lambda: NOW_UTC))
    try:
        async with asyncio.timeout(5):
            while queue.is_active("commercial_bank"):  # noqa: ASYNC110 — 큐에 완료 사건이 없다
                await asyncio.sleep(0.02)
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
    second = await client.get("/api/deposit/simulation", params=params)
    assert second.status_code == 200
    assert second.json()["summary"]["profit"] == "1557207"


class _GatedFxSource(StubSource):
    """환율 출처 — 문이 열릴 때까지 응답하지 않는다."""

    def __init__(self) -> None:
        super().__init__({"USD": [("2026-09-01", "1350.0")]})
        self.gate = asyncio.Event()
        self.entered = asyncio.Event()

    async def fetch_daily_rates(self, currency_code: str, date_from: dt.date,
                                date_to: dt.date) -> FetchResult:
        self.entered.set()
        await self.gate.wait()
        return await super().fetch_daily_rates(currency_code, date_from, date_to)


async def test_환율_수집이_막혀도_예금_수집은_끝난다(session_factory) -> None:  # type: ignore[no-untyped-def]
    async with session_factory() as s:
        job_id, _ = await deposit_job.acquire_or_get_running(
            s, "commercial_bank", D("2020-01-01"), D("2026-10-01"), months_total=82)
        await s.commit()
    fx_source, fx_queue, deposit_queue = _GatedFxSource(), StartQueue(), DepositQueue()
    await fx_queue.request("USD")
    deposit_queue.request(DepositWork(job_id=job_id, institution="commercial_bank",
                                      start_month=D("2020-01-01"), end_month=D("2026-10-01")))
    settings = load_settings()
    tasks = [
        asyncio.create_task(worker_loop(session_factory, fx_source, fx_queue, settings=settings)),
        asyncio.create_task(deposit_worker.deposit_worker_loop(
            session_factory, StubDepositSource(), deposit_queue, settings=settings,
            clock=lambda: NOW_UTC)),
    ]
    try:
        await asyncio.wait_for(fx_source.entered.wait(), timeout=3)
        async with asyncio.timeout(5):
            while deposit_queue.is_active("commercial_bank"):  # noqa: ASYNC110
                await asyncio.sleep(0.02)
        assert not fx_source.gate.is_set(), "환율은 아직 출처에서 기다린다"
        fx_source.gate.set()
    finally:
        for task in tasks:
            task.cancel()
        for task in tasks:
            with contextlib.suppress(asyncio.CancelledError):
                await task
    async with session_factory() as s:
        job = await s.get(DepositCollectionJob, job_id)
    assert job is not None and job.status is JobStatus.SUCCEEDED
