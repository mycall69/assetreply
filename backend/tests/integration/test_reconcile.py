"""미해결 작업 정리 검증 (T017) — FR-005·005a, SC-010, SC-014.

프로세스가 비정상 종료하면 작업이 `running`인 채로, 점유가 잡힌 채로 남는다. 그대로
두면 **다음 수집 시작이 영구히 막힌다.**

정리는 기동 시 1회와 주기 실행 두 경로로 돈다. 조회 시점 지연 판정을 쓰지 않는 이유는
아무도 화면을 열지 않으면 영원히 고쳐지지 않기 때문이다 (research R3-2).
"""
from __future__ import annotations

import datetime as dt

from sqlalchemy import select

from src.db.models import FxCollectionJob, FxCollectionLock, JobStatus
from src.repository.collection_lock import DEFAULT_STALE_SECONDS, acquire_lock
from src.repository.job import create_job
from src.worker.reconcile import reconcile_on_startup, reconcile_once

RANGE = (dt.date(2020, 1, 1), dt.date(2020, 12, 31))


async def _stale_job(session_factory, *, chunks_done: int = 2, age_seconds: int = 1200):
    """하트비트가 끊긴 진행 중 작업을 만든다."""
    async with session_factory() as s:
        job = await create_job(s, "USD", *RANGE, chunks_total=4)
        job.chunks_done = chunks_done
        await acquire_lock(s, "USD", job.id)
        await s.commit()
        lock = (await s.execute(
            select(FxCollectionLock).where(FxCollectionLock.currency_code == "USD")
        )).scalar_one()
        lock.heartbeat_at = dt.datetime.now() - dt.timedelta(seconds=age_seconds)
        await s.commit()
        return job.id


class Test스테일_회수:
    async def test_진행_중으로_남은_작업이_0건이_된다(self, session_factory) -> None:
        """SC-014의 직접 검증."""
        await _stale_job(session_factory)
        async with session_factory() as s:
            await reconcile_once(s, stale_seconds=DEFAULT_STALE_SECONDS)
            await s.commit()
        async with session_factory() as s:
            running = [j for j in (await s.execute(select(FxCollectionJob))).scalars()
                       if j.status is JobStatus.RUNNING]
        assert running == []

    async def test_부분_완료로_확정된다(self, session_factory) -> None:
        """일부라도 받았으면 실패가 아니라 부분 완료다 (FR-005a)."""
        job_id = await _stale_job(session_factory, chunks_done=2)
        async with session_factory() as s:
            await reconcile_once(s, stale_seconds=DEFAULT_STALE_SECONDS)
            await s.commit()
        async with session_factory() as s:
            job = await s.get(FxCollectionJob, job_id)
        assert job is not None and job.status is JobStatus.PARTIAL

    async def test_한_구간도_못_받았으면_failed다(self, session_factory) -> None:
        job_id = await _stale_job(session_factory, chunks_done=0)
        async with session_factory() as s:
            await reconcile_once(s, stale_seconds=DEFAULT_STALE_SECONDS)
            await s.commit()
        async with session_factory() as s:
            job = await s.get(FxCollectionJob, job_id)
        assert job is not None and job.status is JobStatus.FAILED

    async def test_사유가_남는다(self, session_factory) -> None:
        """왜 끝났는지 없으면 나중에 되짚을 수 없다."""
        job_id = await _stale_job(session_factory)
        async with session_factory() as s:
            await reconcile_once(s, stale_seconds=DEFAULT_STALE_SECONDS)
            await s.commit()
        async with session_factory() as s:
            job = await s.get(FxCollectionJob, job_id)
        assert job is not None and job.last_error

    async def test_점유가_회수된다(self, session_factory) -> None:
        await _stale_job(session_factory)
        async with session_factory() as s:
            await reconcile_once(s, stale_seconds=DEFAULT_STALE_SECONDS)
            await s.commit()
        async with session_factory() as s:
            locks = list((await s.execute(select(FxCollectionLock))).scalars())
        assert locks == []

    async def test_회수_뒤_새_수집을_시작할_수_있다(self, session_factory) -> None:
        """SC-010 — 회수가 안 되면 기능이 영구히 막힌다."""
        await _stale_job(session_factory)
        async with session_factory() as s:
            await reconcile_once(s, stale_seconds=DEFAULT_STALE_SECONDS)
            await s.commit()
        async with session_factory() as s:
            new_job = await create_job(s, "USD", *RANGE, chunks_total=4)
            existing = await acquire_lock(s, "USD", new_job.id)
            await s.commit()
        assert existing is None, "점유가 남아 새 수집이 막혔다"


class Test정상_작업_보호:
    async def test_하트비트가_살아있으면_건드리지_않는다(self, session_factory) -> None:
        """돌고 있는 작업을 정리가 죽이면 수집이 끊긴다."""
        job_id = await _stale_job(session_factory, age_seconds=5)
        async with session_factory() as s:
            await reconcile_once(s, stale_seconds=DEFAULT_STALE_SECONDS)
            await s.commit()
        async with session_factory() as s:
            job = await s.get(FxCollectionJob, job_id)
        assert job is not None and job.status is JobStatus.RUNNING

    async def test_이미_끝난_작업은_건드리지_않는다(self, session_factory) -> None:
        async with session_factory() as s:
            job = await create_job(s, "USD", *RANGE, chunks_total=4)
            job.status = JobStatus.SUCCEEDED
            job.finished_at = dt.datetime.now()
            await s.commit()
            job_id = job.id
        # DB가 초 단위로 저장하므로 저장된 값을 다시 읽어 비교 기준으로 삼는다.
        async with session_factory() as s:
            stored = await s.get(FxCollectionJob, job_id)
            assert stored is not None
            before = stored.finished_at
        async with session_factory() as s:
            await reconcile_once(s, stale_seconds=DEFAULT_STALE_SECONDS)
            await s.commit()
        async with session_factory() as s:
            job = await s.get(FxCollectionJob, job_id)
        assert job is not None
        assert job.status is JobStatus.SUCCEEDED and job.finished_at == before

    async def test_정리할_것이_없으면_0을_돌려준다(self, session_factory) -> None:
        async with session_factory() as s:
            assert await reconcile_once(s, stale_seconds=DEFAULT_STALE_SECONDS) == 0


class Test기동_시_정리:
    """기동 시에는 하트비트 나이를 보지 않는다.

    방금 뜬 프로세스에 진행 중인 수집이 있을 수 없으므로, 남아 있는 `running` 작업은
    정의상 전부 고아다. 주기 정리와 같은 900초를 기다리면 프로세스가 죽은 직후
    재기동해도 15분간 수집을 시작할 수 없다 — FR-005가 막으려던 상태 그대로다.
    """

    async def test_방금_죽은_작업도_즉시_정리한다(self, session_factory) -> None:
        await _stale_job(session_factory, age_seconds=5)
        assert await reconcile_on_startup(session_factory) == 1
        async with session_factory() as s:
            running = [j for j in (await s.execute(select(FxCollectionJob))).scalars()
                       if j.status is JobStatus.RUNNING]
        assert running == []

    async def test_정리_직후_수집을_시작할_수_있다(self, session_factory) -> None:
        await _stale_job(session_factory, age_seconds=5)
        await reconcile_on_startup(session_factory)
        async with session_factory() as s:
            job = await create_job(s, "USD", *RANGE, chunks_total=4)
            assert await acquire_lock(s, "USD", job.id) is None
            await s.commit()

    async def test_정리할_것이_없으면_0이다(self, session_factory) -> None:
        assert await reconcile_on_startup(session_factory) == 0
