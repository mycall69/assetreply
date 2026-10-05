"""부동산 수집 작업과 점유 (009 T022, FR-011, FR-012, FR-014, data-model 6절).

008 `deposit_job`과 같은 수단이다. 점유는 (종류, 대상) 단위 — 실거래는 시·군·구, 행정구역은
`regions`, 단지 기본 정보는 법정동이다. **기본 키 INSERT 충돌이 곧 "이미 진행 중"이다**(헌법 DB 운영
규약).

진행은 종류마다 분모가 달라도 `done`·`total` 한 쌍이다(실거래는 달, 기본 정보는 단지, 행정구역은
쪽). `last_error`에는 **사유 종류**(`auth`·`rate_limited`·`format`·`network`)를 앞에 붙인다(FR-014).
"""

from __future__ import annotations

import datetime as dt
from typing import Final

from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import AptCollectionJob, AptCollectionLock, JobStatus

#: 실패 종류(FR-014). 할 일이 다르다 — 인증은 설정을 고치고, 한도는 기다리고, 형식은 어댑터를
#: 고치고, 연결은 다시 하면 된다.
FAILURE_KINDS: Final = ("auth", "rate_limited", "format", "network")
_SEPARATOR = ": "


def job_error(kind: str, message: str) -> str:
    return f"{kind}{_SEPARATOR}{message}"


def split_error(last_error: str | None) -> tuple[str | None, str | None]:
    """`last_error`를 (종류, 사람이 읽을 사유)로 나눈다. 종류가 없으면 종류는 `None`."""
    if last_error is None:
        return None, None
    head, sep, rest = last_error.partition(_SEPARATOR)
    if sep and head in FAILURE_KINDS:
        return head, rest
    return None, last_error


async def get_job(session: AsyncSession, job_id: int) -> AptCollectionJob | None:
    return (await session.execute(
        select(AptCollectionJob).where(AptCollectionJob.id == job_id)
        .execution_options(populate_existing=True))).scalar_one_or_none()


async def running_job_id(session: AsyncSession, kind: str, target: str) -> int | None:
    return (await session.execute(select(AptCollectionLock.job_id).where(
        AptCollectionLock.kind == kind, AptCollectionLock.target == target))).scalar_one_or_none()


async def acquire_or_get_running(session: AsyncSession, kind: str, target: str, *,
                                 total: int) -> tuple[int, bool]:
    """점유를 얻거나, 이미 진행 중이면 그 작업 ID를 돌려준다. `(작업 ID, 새로 만들었는가)`.

    `total`은 그 실행에 받을 몫이다 — 처음 받을 때도 진행의 분모를 안다(실거래는 첫 달 또는 탐색
    시작 달부터 이번 달까지).
    """
    existing = await running_job_id(session, kind, target)
    if existing is not None:
        return existing, False
    job = AptCollectionJob(kind=kind, target=target, total=total, done=0,
                           status=JobStatus.RUNNING)
    session.add(job)
    await session.flush()
    try:
        session.add(AptCollectionLock(kind=kind, target=target, job_id=int(job.id)))
        await session.flush()
    except IntegrityError:
        # 그 사이에 다른 요청이 점유를 가져갔다. 기본 키 충돌이 그 신호다.
        await session.rollback()
        taken = await running_job_id(session, kind, target)
        if taken is None:  # pragma: no cover — 충돌했으므로 있어야 한다
            raise
        return taken, False
    return int(job.id), True


async def set_progress(session: AsyncSession, job_id: int, *, done: int,
                       total: int | None = None) -> None:
    """진행을 기록하고 점유의 심장박동을 갱신한다."""
    values: dict[str, object] = {"done": done}
    if total is not None:
        values["total"] = total
    await session.execute(update(AptCollectionJob).where(
        AptCollectionJob.id == job_id).values(**values))
    await session.execute(update(AptCollectionLock).where(
        AptCollectionLock.job_id == job_id).values(heartbeat_at=func.now()))


async def finish_job(session: AsyncSession, job_id: int, status: JobStatus, *,
                     error: str | None = None, now: dt.datetime | None = None) -> None:
    """작업을 끝내고 점유를 푼다. **실패 사유를 남긴다** — 조용히 끝나면 왜 멈췄는지 알 수 없다."""
    await session.execute(update(AptCollectionJob).where(AptCollectionJob.id == job_id).values(
        status=status, finished_at=func.now() if now is None else now, last_error=error))
    await session.execute(delete(AptCollectionLock).where(AptCollectionLock.job_id == job_id))
    await session.flush()


async def last_finished(session: AsyncSession, kind: str,
                        target: str) -> AptCollectionJob | None:
    """그 대상의 마지막으로 끝난 작업(성공·실패)."""
    return (await session.execute(
        select(AptCollectionJob)
        .where(AptCollectionJob.kind == kind, AptCollectionJob.target == target,
               AptCollectionJob.status != JobStatus.RUNNING)
        .order_by(AptCollectionJob.finished_at.desc(), AptCollectionJob.id.desc())
        .limit(1).execution_options(populate_existing=True))).scalar_one_or_none()


async def last_failure_since(session: AsyncSession, kind: str, target: str,
                             since_utc: dt.datetime) -> AptCollectionJob | None:
    """`since_utc` 뒤에 끝난 그 대상의 마지막 작업이 실패였으면 그 작업."""
    job = await last_finished(session, kind, target)
    if job is None or job.finished_at is None or job.finished_at < since_utc:
        return None
    return job if job.status is JobStatus.FAILED else None


async def release_orphans(session: AsyncSession, *, reason: str) -> int:
    """남은 점유를 모두 풀고 그 작업을 실패로 마감한다. 기동 시 부른다 — 프로세스가 하나라 남은
    점유는 죽은 프로세스의 것이다. 풀지 않으면 그 대상은 다시 받을 수 없고 화면은 "받고 있습니다"에
    머문다."""
    jobs = list((await session.execute(select(AptCollectionLock.job_id))).scalars())
    for job_id in jobs:
        await finish_job(session, int(job_id), JobStatus.FAILED,
                         error=job_error("network", reason))
    return len(jobs)
