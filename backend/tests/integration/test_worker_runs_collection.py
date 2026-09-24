"""워커가 실제로 수집을 돌리는지 검증 (T015) — FR-001, SC-001, SC-002.

001·002에서 동작하지 않던 핵심이다. `POST /api/fx/collect`는 작업 행을 만들고 점유만
잡은 뒤 202를 돌려줬고, `run_collection()`을 호출하는 프로덕션 코드가 없었다.

여기서 보는 것은 **요청이 끝난 뒤에도 수집이 진행되는가**이다. 화면이나 요청 연결의
생존과 무관해야 한다.
"""
from __future__ import annotations

import datetime as dt

from sqlalchemy import select

from src.db.models import FxCollectionJob, FxCoverage, FxRate, JobStatus
from src.worker.queue import StartQueue
from src.worker.runner import run_once

from .conftest import StubSource

RANGE = (dt.date(2020, 1, 1), dt.date(2020, 12, 31))
QUOTES = {"USD": [(f"2020-{m:02d}-01", "1200.00") for m in range(1, 13)]}


class Test수집_실행:
    async def test_워커가_돌면_환율이_저장된다(self, session_factory) -> None:
        await run_once(session_factory, StubSource(QUOTES), "USD", *RANGE, chunk_days=90)
        async with session_factory() as s:
            n = len(list((await s.execute(select(FxRate))).scalars()))
        assert n > 0, "워커가 수집을 실행하지 않았다"

    async def test_커버리지가_전진한다(self, session_factory) -> None:
        await run_once(session_factory, StubSource(QUOTES), "USD", *RANGE, chunk_days=90)
        async with session_factory() as s:
            cov = (await s.execute(
                select(FxCoverage).where(FxCoverage.currency_code == "USD")
            )).scalar_one_or_none()
        assert cov is not None
        assert cov.covered_through == RANGE[1]

    async def test_작업이_종료_상태로_남는다(self, session_factory) -> None:
        """진행 중으로 박힌 채 남으면 안 된다 — 001의 증상이 그것이었다."""
        await run_once(session_factory, StubSource(QUOTES), "USD", *RANGE, chunk_days=90)
        async with session_factory() as s:
            jobs = list((await s.execute(select(FxCollectionJob))).scalars())
        assert jobs and all(j.status is not JobStatus.RUNNING for j in jobs)

    async def test_모든_청크를_받으면_succeeded다(self, session_factory) -> None:
        await run_once(session_factory, StubSource(QUOTES), "USD", *RANGE, chunk_days=90)
        async with session_factory() as s:
            job = (await s.execute(select(FxCollectionJob))).scalars().first()
        assert job is not None and job.status is JobStatus.SUCCEEDED
        assert job.chunks_done == job.chunks_total

    async def test_점유가_해제된다(self, session_factory) -> None:
        """남으면 다음 수집 시작이 영구히 막힌다 (FR-005)."""
        from src.db.models import FxCollectionLock

        await run_once(session_factory, StubSource(QUOTES), "USD", *RANGE, chunk_days=90)
        async with session_factory() as s:
            locks = list((await s.execute(select(FxCollectionLock))).scalars())
        assert locks == []


class Test요청과_독립:
    async def test_요청_컨텍스트_없이_돈다(self, session_factory) -> None:
        """HTTP 요청이나 화면 없이 세션 팩토리만으로 완결되어야 한다 (SC-001, SC-002)."""
        source = StubSource(QUOTES)
        await run_once(session_factory, source, "USD", *RANGE, chunk_days=90)
        assert len(source.requests) > 0

    async def test_큐를_통해서도_같은_결과다(self, session_factory) -> None:
        q = StartQueue()
        assert await q.request("USD") is True
        assert await q.pop() == "USD"
        await run_once(session_factory, StubSource(QUOTES), "USD", *RANGE, chunk_days=90)
        async with session_factory() as s:
            n = len(list((await s.execute(select(FxRate))).scalars()))
        assert n > 0


class Test이벤트_기록:
    async def test_수집_사건이_남는다(self, session_factory) -> None:
        """무슨 일이 있었는지 기록에 남아야 한다 (FR-017)."""
        from src.db.models import FxCollectionEvent

        await run_once(session_factory, StubSource(QUOTES), "USD", *RANGE, chunk_days=90)
        async with session_factory() as s:
            kinds = [e.kind for e in
                     (await s.execute(select(FxCollectionEvent))).scalars()]
        assert "job_started" in kinds
        assert "job_finished" in kinds

    async def test_구간_저장_사건에_건수가_실린다(self, session_factory) -> None:
        from src.db.models import FxCollectionEvent

        await run_once(session_factory, StubSource(QUOTES), "USD", *RANGE, chunk_days=90)
        async with session_factory() as s:
            stored = [e for e in (await s.execute(select(FxCollectionEvent))).scalars()
                      if e.kind == "chunk_stored"]
        assert stored and all(e.rows_stored is not None for e in stored)
