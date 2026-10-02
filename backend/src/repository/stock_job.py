"""주식 수집 작업과 점유 (T021) — 005 FR-048, SC-028.

003의 `repository/job.py`·`collection_lock.py`와 같은 모양이다.

**기본 키 INSERT 충돌이 곧 "이미 진행 중"을 뜻한다.** 모든 RDBMS에서 동일하게 동작하는
유일한 이식 가능 수단이며, 생성 컬럼이나 부분 인덱스 같은 DB 종속 문법을 쓰지 않는다
(헌법 DB 운영 규약).

**점유는 종목 단위다.** 자산군을 가로질러 공유하지 않는다 — FX 수집 중에 주식 수집을
막을 이유가 없고 출처가 달라 호출 한도도 따로다 (research R5-7).
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import JobStatus, StockCollectionJob, StockCollectionLock

#: 시세 출처가 심볼을 모른다는 실패의 표지 (006 FR-032). `last_error` 앞에 붙인다 — 005·001의
#: 테이블 구조를 바꾸지 않는다(data-model). 이 표지가 없으면 다음 요청이 같은 수집을 다시 시작해
#: 화면은 "받고 있습니다"를 되풀이하고, 사유는 "시세 없음"과 구별되지 않는다.
SYMBOL_UNKNOWN = "price_symbol_unknown"
_SYMBOL_UNKNOWN_PREFIX = f"{SYMBOL_UNKNOWN}: "


def symbol_unknown_error(message: str) -> str:
    """`last_error`에 남길 문구. 표지를 붙인다."""
    return f"{_SYMBOL_UNKNOWN_PREFIX}{message}"


def split_error(last_error: str | None) -> tuple[str | None, str | None]:
    """`last_error`를 (표지, 사람이 읽을 사유)로 나눈다. 표지가 없으면 표지는 `None`."""
    if last_error is not None and last_error.startswith(_SYMBOL_UNKNOWN_PREFIX):
        return SYMBOL_UNKNOWN, last_error[len(_SYMBOL_UNKNOWN_PREFIX):]
    return None, last_error


async def symbol_unknown(session: AsyncSession, stock_id: int) -> bool:
    """그 종목의 **마지막 작업**이 "출처가 심볼을 모름"으로 끝났는가."""
    last = (await session.execute(
        select(StockCollectionJob.status, StockCollectionJob.last_error)
        .where(StockCollectionJob.stock_id == stock_id)
        .order_by(StockCollectionJob.id.desc()).limit(1))).first()
    if last is None or last[0] is not JobStatus.FAILED:
        return False
    return split_error(last[1])[0] == SYMBOL_UNKNOWN


async def get_job(
    session: AsyncSession, job_id: int
) -> StockCollectionJob | None:
    return (await session.execute(
        select(StockCollectionJob).where(StockCollectionJob.id == job_id)
    )).scalar_one_or_none()


async def running_job_id(session: AsyncSession, stock_id: int) -> int | None:
    """그 종목에서 진행 중인 작업의 ID. 없으면 `None`."""
    return (await session.execute(
        select(StockCollectionLock.job_id)
        .where(StockCollectionLock.stock_id == stock_id)
    )).scalar_one_or_none()


async def acquire_or_get_running(
    session: AsyncSession,
    stock_id: int,
    start: dt.date,
    end: dt.date,
    *,
    chunks_total: int,
) -> tuple[int, bool]:
    """점유를 얻거나, 이미 진행 중이면 그 작업 ID를 돌려준다 (FR-048).

    `(작업 ID, 새로 만들었는가)`를 돌려준다.

    **새 작업을 만들지 않는 것이 핵심이다.** 중복 수집은 오류 없이 성공하면서 출처
    호출만 두 배로 쓴다 — 출처가 한도를 공개하지 않아 그 대가를 미리 알 수 없다.
    """
    existing = await running_job_id(session, stock_id)
    if existing is not None:
        return existing, False

    job = StockCollectionJob(
        stock_id=stock_id, range_start=start, range_end=end,
        status=JobStatus.RUNNING, chunks_total=chunks_total, chunks_done=0)
    session.add(job)
    await session.flush()

    try:
        session.add(StockCollectionLock(stock_id=stock_id, job_id=int(job.id)))
        await session.flush()
    except IntegrityError:
        # 그 사이에 다른 요청이 점유를 가져갔다. 기본 키 충돌이 그 신호다.
        await session.rollback()
        taken = await running_job_id(session, stock_id)
        if taken is None:  # pragma: no cover — 충돌했으므로 있어야 한다
            raise
        return taken, False

    return int(job.id), True


async def advance_chunk(session: AsyncSession, job_id: int) -> None:
    """청크 하나를 마쳤음을 기록하고 점유의 심장박동을 갱신한다.

    심장박동이 없으면 프로세스가 비정상 종료했을 때 남은 점유를 회수할 근거가 없다.
    """
    await session.execute(
        update(StockCollectionJob)
        .where(StockCollectionJob.id == job_id)
        .values(chunks_done=StockCollectionJob.chunks_done + 1))
    await session.execute(
        update(StockCollectionLock)
        .where(StockCollectionLock.job_id == job_id)
        .values(heartbeat_at=func.now()))


async def finish_job(
    session: AsyncSession,
    job_id: int,
    status: JobStatus,
    *,
    error: str | None = None,
) -> None:
    """작업을 끝내고 점유를 푼다.

    **실패 사유를 남긴다.** 조용히 끝나면 왜 멈췄는지 알 수 없고, 다음 실행이 같은
    곳에서 또 멈춘다.
    """
    await session.execute(
        update(StockCollectionJob)
        .where(StockCollectionJob.id == job_id)
        .values(status=status, finished_at=func.now(), last_error=error))
    lock = (await session.execute(
        select(StockCollectionLock).where(StockCollectionLock.job_id == job_id)
    )).scalar_one_or_none()
    if lock is not None:
        await session.delete(lock)
    await session.flush()
