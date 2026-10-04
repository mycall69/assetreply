"""예금 수집 작업과 점유 (T018) — 008 FR-011, FR-012, FR-016, data-model 4·5절.

007 `crypto_job`과 같은 모양이다(코인 자리에 투자처). **기본 키 INSERT 충돌이 곧 "이미 진행
중"이다**(헌법 DB 운영 규약). 점유는 투자처 단위이고 환율 수집과 공유하지 않는다 — 같은 ECOS
출처라도 호출 한도는 관문이 지키고, 점유가 지킬 것은 같은 투자처의 중복 수집이다.

`last_error`에는 **사유 종류**(`auth`·`rate_limited`·`format`·`network`)를 앞에 붙인다(FR-016).
"""

from __future__ import annotations

import datetime as dt
from typing import Final

from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import DepositCollectionJob, DepositCollectionLock, JobStatus

#: 실패 종류(FR-016). 할 일이 다르다 — 인증은 설정을 고치고, 한도는 기다리고, 형식은 어댑터를
#: 고치고, 연결은 다시 하면 된다.
FAILURE_KINDS: Final = ("auth", "rate_limited", "format", "network")
_SEPARATOR = ": "


def job_error(kind: str, message: str) -> str:
    """`last_error`에 남길 문구. 종류를 앞에 붙인다."""
    return f"{kind}{_SEPARATOR}{message}"


def split_error(last_error: str | None) -> tuple[str | None, str | None]:
    """`last_error`를 (종류, 사람이 읽을 사유)로 나눈다. 종류가 없으면 종류는 `None`."""
    if last_error is None:
        return None, None
    head, sep, rest = last_error.partition(_SEPARATOR)
    if sep and head in FAILURE_KINDS:
        return head, rest
    return None, last_error


async def get_job(session: AsyncSession, job_id: int) -> DepositCollectionJob | None:
    return (await session.execute(
        select(DepositCollectionJob).where(DepositCollectionJob.id == job_id)
        .execution_options(populate_existing=True))).scalar_one_or_none()


async def running_job_id(session: AsyncSession, institution: str) -> int | None:
    return (await session.execute(select(DepositCollectionLock.job_id).where(
        DepositCollectionLock.institution == institution))).scalar_one_or_none()


async def acquire_or_get_running(
    session: AsyncSession, institution: str, start: dt.date, end: dt.date, *, months_total: int,
) -> tuple[int, bool]:
    """점유를 얻거나, 이미 진행 중이면 그 작업 ID를 돌려준다. `(작업 ID, 새로 만들었는가)`.

    구간은 **그 실행에 필요한 구간**(시작 달 ~ 이번 달)이고 `months_total`은 그 달 수다 — 처음 받을
    때도 진행의 분모를 안다(analyze I1).
    """
    existing = await running_job_id(session, institution)
    if existing is not None:
        return existing, False
    job = DepositCollectionJob(
        institution=institution, range_start=start, range_end=end, status=JobStatus.RUNNING,
        months_total=months_total, months_done=0)
    session.add(job)
    await session.flush()
    try:
        session.add(DepositCollectionLock(institution=institution, job_id=int(job.id)))
        await session.flush()
    except IntegrityError:
        # 그 사이에 다른 요청이 점유를 가져갔다. 기본 키 충돌이 그 신호다.
        await session.rollback()
        taken = await running_job_id(session, institution)
        if taken is None:  # pragma: no cover — 충돌했으므로 있어야 한다
            raise
        return taken, False
    return int(job.id), True


async def set_months_done(session: AsyncSession, job_id: int, months_done: int) -> None:
    """받은 달 수를 기록하고 점유의 심장박동을 갱신한다."""
    await session.execute(update(DepositCollectionJob).where(
        DepositCollectionJob.id == job_id).values(months_done=months_done))
    await session.execute(update(DepositCollectionLock).where(
        DepositCollectionLock.job_id == job_id).values(heartbeat_at=func.now()))


async def finish_job(
    session: AsyncSession, job_id: int, status: JobStatus, *, error: str | None = None,
    now: dt.datetime | None = None,
) -> None:
    """작업을 끝내고 점유를 푼다. **실패 사유를 남긴다** — 조용히 끝나면 왜 멈췄는지 알 수 없다.

    `now`(UTC)를 주면 그 시각으로 마감한다 — "오늘(한국 시간) 확인이 실패했는가"를 이 시각으로
    판정한다(FR-016).
    """
    await session.execute(update(DepositCollectionJob).where(
        DepositCollectionJob.id == job_id).values(
        status=status, finished_at=func.now() if now is None else now, last_error=error))
    await session.execute(delete(DepositCollectionLock).where(
        DepositCollectionLock.job_id == job_id))
    await session.flush()


async def last_failure_since(
    session: AsyncSession, institution: str, since_utc: dt.datetime,
) -> DepositCollectionJob | None:
    """`since_utc` 뒤에 끝난 그 투자처의 마지막 작업이 실패였으면 그 작업. 성공했으면 `None`이다 —
    실패 뒤 성공한 확인이 있으면 실패를 알릴 까닭이 없다."""
    job = (await session.execute(
        select(DepositCollectionJob)
        .where(DepositCollectionJob.institution == institution,
               DepositCollectionJob.status != JobStatus.RUNNING,
               DepositCollectionJob.finished_at >= since_utc)
        .order_by(DepositCollectionJob.finished_at.desc(), DepositCollectionJob.id.desc())
        .limit(1).execution_options(populate_existing=True))).scalar_one_or_none()
    return job if job is not None and job.status is JobStatus.FAILED else None


async def release_orphans(session: AsyncSession, *, reason: str) -> int:
    """남은 점유를 모두 풀고 그 작업을 실패로 마감한다. 기동 시 부른다 — 프로세스가 하나라 남은
    점유는 죽은 프로세스의 것이다. 풀지 않으면 그 투자처는 다시 받을 수 없고 화면은 "받고
    있습니다"에 머문다."""
    jobs = list((await session.execute(select(DepositCollectionLock.job_id))).scalars())
    for job_id in jobs:
        await finish_job(session, int(job_id), JobStatus.FAILED,
                         error=job_error("network", reason))
    return len(jobs)
