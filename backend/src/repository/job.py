"""수집 작업 이력 리포지토리 (T094).

data-model.md 상태 전이: running → succeeded | partial | failed.
`partial`과 `failed`의 구분 기준은 `chunks_done > 0`이다.
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import FxCollectionJob, JobStatus


async def create_job(
    session: AsyncSession,
    currency_code: str,
    range_start: dt.date,
    range_end: dt.date,
    *,
    chunks_total: int,
) -> FxCollectionJob:
    job = FxCollectionJob(
        currency_code=currency_code,
        range_start=range_start,
        range_end=range_end,
        status=JobStatus.RUNNING,
        chunks_total=chunks_total,
        chunks_done=0,
    )
    session.add(job)
    await session.flush()
    return job


async def finish_job(
    session: AsyncSession,
    job: FxCollectionJob,
    *,
    chunks_done: int,
    error: str | None = None,
) -> FxCollectionJob:
    """작업을 종료 상태로 전이시킨다.

    오류가 있어도 이미 처리한 청크가 있으면 `partial`이다 — 완전 실패와 구분해야
    사용자가 "얼마나 건졌는지"를 알 수 있다 (FR-013).
    """
    job.chunks_done = chunks_done
    job.finished_at = dt.datetime.now()
    if error is None:
        job.status = JobStatus.SUCCEEDED
    else:
        job.status = JobStatus.PARTIAL if chunks_done > 0 else JobStatus.FAILED
        job.last_error = error
    return job


async def finalize_as_partial(
    session: AsyncSession, job: FxCollectionJob, *, reason: str
) -> FxCollectionJob:
    """중단된 작업을 종료 상태로 확정한다 (003 FR-005a, FR-007).

    **진행 중으로 남는 작업이 있어서는 안 된다.** 남으면 화면의 작업 목록에서 끝나지
    않는 작업으로 계속 보이고, 성공도 실패도 아닌 채로 조용히 멈춰 있게 된다.

    한 구간도 받지 못했으면 `failed`, 일부라도 받았으면 `partial`이다 — 받은 데이터는
    유효하므로 완전 실패와 구별해야 사용자가 "얼마나 건졌는지"를 알 수 있다.
    """
    if job.status is not JobStatus.RUNNING:
        return job
    job.finished_at = dt.datetime.now()
    job.status = JobStatus.PARTIAL if job.chunks_done > 0 else JobStatus.FAILED
    job.last_error = reason
    return job


async def get_job(session: AsyncSession, job_id: int) -> FxCollectionJob | None:
    return (await session.execute(
        select(FxCollectionJob).where(FxCollectionJob.id == job_id))).scalar_one_or_none()


async def list_jobs(
    session: AsyncSession,
    *,
    currency_code: str | None = None,
    status: JobStatus | None = None,
    limit: int = 50,
) -> list[FxCollectionJob]:
    stmt = select(FxCollectionJob).order_by(FxCollectionJob.started_at.desc()).limit(limit)
    if currency_code is not None:
        stmt = stmt.where(FxCollectionJob.currency_code == currency_code)
    if status is not None:
        stmt = stmt.where(FxCollectionJob.status == status)
    return list((await session.execute(stmt)).scalars())


async def running_jobs(session: AsyncSession) -> list[FxCollectionJob]:
    return list((await session.execute(
        select(FxCollectionJob).where(
            FxCollectionJob.status == JobStatus.RUNNING))).scalars())
