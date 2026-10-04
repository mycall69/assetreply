"""가상자산 수집 작업과 점유 (T030) — 007 FR-013, FR-014, FR-020, data-model 8절.

005 `stock_job`과 같은 모양이다(종목 자리에 코인). **기본 키 INSERT 충돌이 곧 "이미 진행
중"이다**(헌법 DB 운영 규약). 점유는 코인 단위이고 자산군을 가로질러 공유하지 않는다 — 주식 수집
중에 가상자산 수집을 막을 이유가 없다(SC-012).

`last_error`에는 **사유 종류**(`blocked`·`format`·`network`·`empty`)를 앞에 붙인다(FR-020) —
테이블에 열을 더하지 않고 화면이 종류마다 다른 말을 하게 한다.
"""

from __future__ import annotations

import datetime as dt
from typing import Final

from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import CryptoCollectionJob, CryptoCollectionLock, JobStatus

#: 실패 종류 (FR-020). 할 일이 다르다 — 차단은 기다려도 풀리지 않고, 형식 변경은 고쳐야 하고,
#: 네트워크는 다시 하면 된다.
FAILURE_KINDS: Final = ("blocked", "format", "network", "empty")
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


async def get_job(session: AsyncSession, job_id: int) -> CryptoCollectionJob | None:
    return (await session.execute(
        select(CryptoCollectionJob).where(CryptoCollectionJob.id == job_id)
        .execution_options(populate_existing=True))).scalar_one_or_none()


async def running_job_id(session: AsyncSession, coin_id: int) -> int | None:
    return (await session.execute(select(CryptoCollectionLock.job_id).where(
        CryptoCollectionLock.coin_id == coin_id))).scalar_one_or_none()


async def acquire_or_get_running(
    session: AsyncSession, coin_id: int, start: dt.date, end: dt.date, *, chunks_total: int,
) -> tuple[int, bool]:
    """점유를 얻거나, 이미 진행 중이면 그 작업 ID를 돌려준다. `(작업 ID, 새로 만들었는가)`.

    **새 작업을 만들지 않는 것이 핵심이다.** 중복 수집은 오류 없이 성공하면서 출처 호출만 두 배로
    쓴다.
    """
    existing = await running_job_id(session, coin_id)
    if existing is not None:
        return existing, False
    job = CryptoCollectionJob(
        coin_id=coin_id, range_start=start, range_end=end, status=JobStatus.RUNNING,
        chunks_total=chunks_total, chunks_done=0)
    session.add(job)
    await session.flush()
    try:
        session.add(CryptoCollectionLock(coin_id=coin_id, job_id=int(job.id)))
        await session.flush()
    except IntegrityError:
        # 그 사이에 다른 요청이 점유를 가져갔다. 기본 키 충돌이 그 신호다.
        await session.rollback()
        taken = await running_job_id(session, coin_id)
        if taken is None:  # pragma: no cover — 충돌했으므로 있어야 한다
            raise
        return taken, False
    return int(job.id), True


async def advance_chunk(session: AsyncSession, job_id: int) -> None:
    """청크 하나를 마쳤음을 기록하고 점유의 심장박동을 갱신한다."""
    await session.execute(update(CryptoCollectionJob).where(
        CryptoCollectionJob.id == job_id).values(chunks_done=CryptoCollectionJob.chunks_done + 1))
    await session.execute(update(CryptoCollectionLock).where(
        CryptoCollectionLock.job_id == job_id).values(heartbeat_at=func.now()))


async def finish_job(
    session: AsyncSession, job_id: int, status: JobStatus, *, error: str | None = None
) -> None:
    """작업을 끝내고 점유를 푼다. **실패 사유를 남긴다** — 조용히 끝나면 왜 멈췄는지 알 수 없다."""
    await session.execute(update(CryptoCollectionJob).where(
        CryptoCollectionJob.id == job_id).values(
        status=status, finished_at=func.now(), last_error=error))
    await session.execute(delete(CryptoCollectionLock).where(
        CryptoCollectionLock.job_id == job_id))
    await session.flush()


async def release_orphans(session: AsyncSession, *, reason: str) -> int:
    """남은 점유를 모두 풀고 그 작업을 실패로 마감한다. 기동 시 부른다 — 프로세스가 하나라 남은
    점유는 죽은 프로세스의 것이다.

    풀지 않으면 그 코인은 다시 받을 수 없고, 화면은 "받고 있습니다"에 머문다.
    """
    jobs = list((await session.execute(select(CryptoCollectionLock.job_id))).scalars())
    for job_id in jobs:
        await finish_job(session, int(job_id), JobStatus.FAILED,
                         error=job_error("network", reason))
    return len(jobs)
