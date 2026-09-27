"""워커 수명 검증 (T016, T032) — FR-001, FR-002, FR-007.

두 가지를 본다.

1. 앱이 기동해도 **사용자 조작 없이는 수집이 시작되지 않는다** (FR-002). 자동 시작은
   아무도 안 보는 사이 일일 한도를 소진시킬 수 있다.
2. 종료 시 진행 중이던 작업이 **부분 완료로 확정된다** (FR-007). 진행 중으로 남기면
   다음 기동까지 점유가 수집을 막는다.
"""
from __future__ import annotations

import asyncio
import datetime as dt

from sqlalchemy import select

from src.db.models import FxCollectionJob, FxCollectionLock, FxRate, JobStatus
from src.repository.collection_lock import acquire_lock
from src.repository.job import create_job
from src.worker.queue import StartQueue
from src.worker.runner import _finalize_on_shutdown, worker_loop

from .conftest import StubSource

RANGE = (dt.date(2020, 1, 1), dt.date(2020, 12, 31))
QUOTES = {"USD": [(f"2020-{m:02d}-01", "1200.00") for m in range(1, 13)]}


class Test명시적_시작:
    async def test_큐가_비면_아무것도_하지_않는다(self, session_factory, settings) -> None:
        """FR-002 — 기동만으로 수집이 시작되면 안 된다."""
        queue = StartQueue()
        task = asyncio.create_task(
            worker_loop(session_factory, StubSource(QUOTES), queue, settings=settings))
        await asyncio.sleep(0.05)
        task.cancel()
        with __import__("contextlib").suppress(asyncio.CancelledError):
            await task

        async with session_factory() as s:
            rates = list((await s.execute(select(FxRate))).scalars())
            jobs = list((await s.execute(select(FxCollectionJob))).scalars())
        assert rates == [] and jobs == []

    async def test_요청을_넣어야_돈다(self, session_factory, settings) -> None:
        queue = StartQueue()
        task = asyncio.create_task(
            worker_loop(session_factory, StubSource(QUOTES), queue, settings=settings))
        await queue.request("USD")
        await asyncio.sleep(0.4)
        task.cancel()
        with __import__("contextlib").suppress(asyncio.CancelledError):
            await task

        async with session_factory() as s:
            jobs = list((await s.execute(select(FxCollectionJob))).scalars())
        assert jobs, "요청을 넣었는데 워커가 돌지 않았다"


class Test종료_처리:
    async def test_진행_중_작업이_부분_완료로_확정된다(self, session_factory) -> None:
        """FR-007 — 진행 중으로 남기면 다음 기동까지 점유가 수집을 막는다."""
        async with session_factory() as s:
            job = await create_job(s, "USD", *RANGE, chunks_total=4)
            job.chunks_done = 2
            await acquire_lock(s, "USD", job.id)
            await s.commit()
            job_id = job.id

        await _finalize_on_shutdown(session_factory, "USD")

        async with session_factory() as s:
            job = await s.get(FxCollectionJob, job_id)
        assert job is not None and job.status is JobStatus.PARTIAL

    async def test_종료_사유가_남는다(self, session_factory) -> None:
        async with session_factory() as s:
            job = await create_job(s, "USD", *RANGE, chunks_total=4)
            job.chunks_done = 1
            await acquire_lock(s, "USD", job.id)
            await s.commit()
            job_id = job.id

        await _finalize_on_shutdown(session_factory, "USD")

        async with session_factory() as s:
            job = await s.get(FxCollectionJob, job_id)
        assert job is not None and job.last_error
        assert "종료" in job.last_error

    async def test_점유가_풀린다(self, session_factory) -> None:
        async with session_factory() as s:
            job = await create_job(s, "USD", *RANGE, chunks_total=4)
            await acquire_lock(s, "USD", job.id)
            await s.commit()

        await _finalize_on_shutdown(session_factory, "USD")

        async with session_factory() as s:
            locks = list((await s.execute(select(FxCollectionLock))).scalars())
        assert locks == []

    async def test_진행_중_작업이_없어도_안전하다(self, session_factory) -> None:
        """정상 종료 경로에서 늘 불리므로 빈 상태에서도 예외가 없어야 한다."""
        await _finalize_on_shutdown(session_factory, "USD")


class Test소스_수명:
    """워커는 데이터 소스의 수명을 **직접 관리해야 한다.**

    `EcosClient`는 `async with`로 열어야 HTTP 세션이 생긴다. 열지 않은 채 넘기면
    첫 호출에서 `RuntimeError`가 나고, `run_once`는 `SourceError`만 잡으므로 그 예외가
    `worker_loop`의 광범위 `except`까지 올라가 "수집에 실패했습니다"로만 남는다.

    실제로 이 상태였다 — 수집이 한 번도 성공하지 못했는데 화면에는 작업이 생기고
    끝나는 것처럼 보였다.
    """

    async def test_열지_않은_소스는_거부한다(self, session_factory, settings) -> None:
        class 미개방소스:
            """`async with` 없이 쓰면 예외를 내는 소스."""

            def __init__(self) -> None:
                self.opened = False

            async def __aenter__(self):
                self.opened = True
                return self

            async def __aexit__(self, *exc: object) -> None:
                self.opened = False

            async def fetch_daily_rates(self, *a: object, **k: object):
                if not self.opened:
                    raise RuntimeError("열어야 합니다")
                return await StubSource(QUOTES).fetch_daily_rates(*a, **k)  # type: ignore[arg-type]

            async def verify_item_mapping(self, currency_code: str):
                return await StubSource().verify_item_mapping(currency_code)

        queue = StartQueue()
        source = 미개방소스()
        task = asyncio.create_task(
            worker_loop(session_factory, source, queue, settings=settings))
        await queue.request("USD")
        await asyncio.sleep(0.5)
        task.cancel()
        with __import__("contextlib").suppress(asyncio.CancelledError):
            await task

        # 워커가 소스를 열었다면 수집이 진행된다.
        async with session_factory() as s:
            rates = list((await s.execute(select(FxRate))).scalars())
        assert rates, "워커가 소스를 열지 않아 수집이 한 건도 되지 않았다"

    async def test_종료_시_소스를_닫는다(self, session_factory, settings) -> None:
        """HTTP 세션이 남으면 프로세스가 깨끗하게 끝나지 않는다."""
        closed: list[bool] = []

        class 추적소스(StubSource):
            async def __aenter__(self):
                return self

            async def __aexit__(self, *exc: object) -> None:
                closed.append(True)

        queue = StartQueue()
        task = asyncio.create_task(
            worker_loop(session_factory, 추적소스(QUOTES), queue, settings=settings))
        await asyncio.sleep(0.05)
        task.cancel()
        with __import__("contextlib").suppress(asyncio.CancelledError):
            await task
        assert closed, "종료 시 소스를 닫지 않았다"
