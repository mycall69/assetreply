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
