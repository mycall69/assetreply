"""통화별 단일 수집 작업 잠금 (T093, research R6).

**표준 SQL만 사용한다.** 기본 키 INSERT 충돌이 곧 "이미 진행 중"이며, 이는 모든 RDBMS에서
동일하게 동작하는 유일한 이식 가능 수단이다. MySQL 생성 컬럼이나 PostgreSQL 부분
유니크 인덱스는 어느 쪽을 택해도 다른 DB에서 깨진다 (헌법 v4.0.0).
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import FxCollectionLock

# 하트비트가 이보다 오래되면 프로세스가 죽은 것으로 보고 회수한다
DEFAULT_STALE_SECONDS = 900


async def acquire_lock(
    session: AsyncSession, currency_code: str, job_id: int
) -> int | None:
    """잠금을 시도한다. 성공하면 `None`, 이미 잠겨 있으면 기존 작업 ID를 돌려준다.

    반환값이 있으면 호출자는 새 작업을 만들지 않고 그 작업에 합류한다 (FR-015b).
    """
    session.add(FxCollectionLock(currency_code=currency_code, job_id=job_id))
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        existing = (await session.execute(
            select(FxCollectionLock.job_id).where(
                FxCollectionLock.currency_code == currency_code))).scalar_one_or_none()
        return existing
    return None


async def release_lock(session: AsyncSession, currency_code: str) -> None:
    """작업 종료 시 해제한다. 잠금이 남으면 재시도가 영영 막힌다."""
    await session.execute(
        delete(FxCollectionLock).where(FxCollectionLock.currency_code == currency_code))


async def heartbeat(
    session: AsyncSession, currency_code: str, *, at: dt.datetime | None = None
) -> None:
    """생존 신호를 갱신한다. 수집기가 청크를 커밋할 때마다 호출한다 (추가 왕복 없음)."""
    row = (await session.execute(
        select(FxCollectionLock).where(
            FxCollectionLock.currency_code == currency_code))).scalar_one_or_none()
    if row is not None:
        row.heartbeat_at = at or dt.datetime.now()


async def reclaim_stale_locks(
    session: AsyncSession, *, older_than_seconds: int = DEFAULT_STALE_SECONDS
) -> list[str]:
    """하트비트가 끊긴 잠금을 회수한다. 회수한 통화 목록을 돌려준다."""
    cutoff = dt.datetime.now() - dt.timedelta(seconds=older_than_seconds)
    rows = list((await session.execute(
        select(FxCollectionLock).where(
            FxCollectionLock.heartbeat_at < cutoff))).scalars())
    for row in rows:
        await session.delete(row)
    return [r.currency_code for r in rows]
