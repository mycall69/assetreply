"""수집 작업 상태 전이·한도 소진·보관 정책 테스트 (T088, T089, T091)."""
from __future__ import annotations

import datetime as dt

from sqlalchemy import func, select

from src.db.models import FxCollectionJob, JobStatus
from src.db.retention import purge_succeeded_jobs
from src.ingestion.ecos.errors import SourceRateLimited
from src.ingestion.orchestrator import run_collection
from src.repository.job import create_job, finish_job, list_jobs

from .conftest import StubSource

RANGE = (dt.date(2020, 1, 1), dt.date(2020, 12, 31))
QUOTES = {"USD": [(f"2020-{m:02d}-01", "1200.00") for m in range(1, 13)]}


class Test상태_전이:
    async def test_생성_직후는_running이다(self, session_factory) -> None:
        async with session_factory() as s:
            job = await create_job(s, "USD", *RANGE, chunks_total=4)
            await s.commit()
        assert job.status is JobStatus.RUNNING

    async def test_전부_성공하면_succeeded다(self, session_factory) -> None:
        async with session_factory() as s:
            job = await create_job(s, "USD", *RANGE, chunks_total=4)
            await finish_job(s, job, chunks_done=4)
            await s.commit()
        assert job.status is JobStatus.SUCCEEDED
        assert job.finished_at is not None

    async def test_일부만_성공하면_partial이다(self, session_factory) -> None:
        """구분 기준은 chunks_done > 0."""
        async with session_factory() as s:
            job = await create_job(s, "USD", *RANGE, chunks_total=4)
            await finish_job(s, job, chunks_done=2, error="한도 초과")
            await s.commit()
        assert job.status is JobStatus.PARTIAL
        assert job.last_error == "한도 초과"

    async def test_하나도_못하면_failed다(self, session_factory) -> None:
        async with session_factory() as s:
            job = await create_job(s, "USD", *RANGE, chunks_total=4)
            await finish_job(s, job, chunks_done=0, error="인증 실패")
            await s.commit()
        assert job.status is JobStatus.FAILED


class Test한도_소진:
    """FR-013: 중단하되 이미 저장된 데이터는 유효하게 남는다."""

    async def test_중단되면_partial로_기록된다(self, session_factory) -> None:
        src = StubSource(QUOTES)
        src.raise_after = 2
        src.raise_on_call = SourceRateLimited("일일 트래픽 초과")
        async with session_factory() as s:
            job = await run_collection(s, src, "USD", *RANGE, chunk_days=90)
        assert job.status in (JobStatus.PARTIAL, JobStatus.FAILED)
        assert "트래픽" in (job.last_error or "")

    async def test_커밋된_구간은_유효하게_남는다(self, session_factory) -> None:
        from src.db.models import FxCoverage

        src = StubSource(QUOTES)
        src.raise_after = 2
        src.raise_on_call = SourceRateLimited("일일 트래픽 초과")
        async with session_factory() as s:
            await run_collection(s, src, "USD", *RANGE, chunk_days=90)
            cov = (await s.execute(select(FxCoverage))).scalar_one_or_none()
        assert cov is not None, "이미 커밋된 커버리지가 사라졌다"

    async def test_중단_후_잠금이_해제된다(self, session_factory) -> None:
        from src.db.models import FxCollectionLock

        src = StubSource(QUOTES)
        src.raise_after = 1
        src.raise_on_call = SourceRateLimited("일일 트래픽 초과")
        async with session_factory() as s:
            await run_collection(s, src, "USD", *RANGE, chunk_days=90)
            n = (await s.execute(
                select(func.count()).select_from(FxCollectionLock))).scalar()
        assert n == 0, "잠금이 남으면 재시도가 영영 막힌다"

    async def test_성공하면_succeeded로_끝난다(self, session_factory) -> None:
        async with session_factory() as s:
            job = await run_collection(s, StubSource(QUOTES), "USD", *RANGE, chunk_days=90)
        assert job.status is JobStatus.SUCCEEDED


class Test중복_요청:
    async def test_진행_중이면_기존_작업을_돌려준다(self, session_factory) -> None:
        """FR-015b."""
        from src.repository.collection_lock import acquire_lock

        async with session_factory() as s:
            first = await create_job(s, "USD", *RANGE, chunks_total=4)
            await acquire_lock(s, "USD", first.id)
            await s.commit()
            job = await run_collection(s, StubSource(QUOTES), "USD", *RANGE, chunk_days=90)
        assert job.id == first.id


class Test보관_정책:
    """FR-038a: 실패·부분 성공은 영구 보관. FR-038b: 성공만 기간 경과 후 정리."""

    async def _seed(self, session, status: JobStatus, days_ago: int) -> None:
        job = await create_job(session, "USD", *RANGE, chunks_total=4)
        job.status = status
        job.finished_at = dt.datetime.now() - dt.timedelta(days=days_ago)
        await session.commit()

    async def test_오래된_성공_이력은_정리된다(self, session_factory) -> None:
        async with session_factory() as s:
            await self._seed(s, JobStatus.SUCCEEDED, 120)
            removed = await purge_succeeded_jobs(s, retention_days=90)
            await s.commit()
            n = (await s.execute(
                select(func.count()).select_from(FxCollectionJob))).scalar()
        assert removed == 1 and n == 0

    async def test_최근_성공_이력은_남는다(self, session_factory) -> None:
        async with session_factory() as s:
            await self._seed(s, JobStatus.SUCCEEDED, 30)
            await purge_succeeded_jobs(s, retention_days=90)
            await s.commit()
            n = (await s.execute(
                select(func.count()).select_from(FxCollectionJob))).scalar()
        assert n == 1

    async def test_실패_이력은_아무리_오래돼도_남는다(self, session_factory) -> None:
        """FR-038a: 원인 조사에 필요하므로 영구 보관한다."""
        async with session_factory() as s:
            await self._seed(s, JobStatus.FAILED, 3650)
            await self._seed(s, JobStatus.PARTIAL, 3650)
            await purge_succeeded_jobs(s, retention_days=90)
            await s.commit()
            rows = await list_jobs(s)
        assert {r.status for r in rows} == {JobStatus.FAILED, JobStatus.PARTIAL}

    async def test_진행_중_작업은_정리하지_않는다(self, session_factory) -> None:
        async with session_factory() as s:
            await create_job(s, "USD", *RANGE, chunks_total=4)
            await s.commit()
            await purge_succeeded_jobs(s, retention_days=0)
            await s.commit()
            n = (await s.execute(
                select(func.count()).select_from(FxCollectionJob))).scalar()
        assert n == 1
