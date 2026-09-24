"""통화별 단일 작업 잠금 (T093, T065, research R6·R2-8).

**표준 SQL만 사용한다.** 기본 키 INSERT 충돌이 곧 "이미 진행 중"이며, 이는 모든 RDBMS에서
동일하게 동작하는 유일한 이식 가능 수단이다. MySQL 생성 컬럼이나 PostgreSQL 부분
유니크 인덱스는 어느 쪽을 택해도 다른 DB에서 깨진다 (헌법 v5.0.0).

**범위(scope)** — 대량 수집과 오늘 새로고침은 서로를 막지 않아야 한다(FR-036a). 두 작업의
대상 구간이 겹치지 않기 때문이다(수집은 어제까지, 새로고침은 오늘만). 범위를 기본 키에
넣어 같은 통화에서 두 잠금이 공존하게 한다. 범위 안에서는 여전히 하나만 실행된다(FR-036b).
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import FxCollectionLock

# 하트비트가 이보다 오래되면 프로세스가 죽은 것으로 보고 회수한다
DEFAULT_STALE_SECONDS = 900

#: 대량 수집 (청크별 하트비트로 수 분~수 시간 이어진다)
SCOPE_COLLECTION = "collection"
#: 오늘 새로고침 (단일 호출이라 수 초 내에 끝난다)
SCOPE_TODAY_REFRESH = "today_refresh"


async def acquire_lock(
    session: AsyncSession, currency_code: str, job_id: int,
    *, scope: str = SCOPE_COLLECTION,
) -> int | None:
    """잠금을 시도한다. 성공하면 `None`, 이미 잠겨 있으면 기존 작업 ID를 돌려준다.

    반환값이 있으면 호출자는 새 작업을 만들지 않고 그 작업에 합류한다 (FR-015b).
    """
    session.add(FxCollectionLock(
        scope=scope, currency_code=currency_code, job_id=job_id))
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        existing = (await session.execute(
            select(FxCollectionLock.job_id).where(
                FxCollectionLock.scope == scope,
                FxCollectionLock.currency_code == currency_code))).scalar_one_or_none()
        return existing
    return None


async def release_lock(
    session: AsyncSession, currency_code: str, *, scope: str = SCOPE_COLLECTION
) -> None:
    """작업 종료 시 해제한다. 잠금이 남으면 재시도가 영영 막힌다."""
    await session.execute(
        delete(FxCollectionLock).where(
            FxCollectionLock.scope == scope,
            FxCollectionLock.currency_code == currency_code))


async def heartbeat(
    session: AsyncSession, currency_code: str, *,
    at: dt.datetime | None = None, scope: str = SCOPE_COLLECTION,
) -> None:
    """생존 신호를 갱신한다. 수집기가 청크를 커밋할 때마다 호출한다 (추가 왕복 없음)."""
    row = (await session.execute(
        select(FxCollectionLock).where(
            FxCollectionLock.scope == scope,
            FxCollectionLock.currency_code == currency_code))).scalar_one_or_none()
    if row is not None:
        row.heartbeat_at = at or dt.datetime.now()


async def stale_locks(
    session: AsyncSession, *,
    older_than_seconds: int = DEFAULT_STALE_SECONDS,
    scope: str = "collection",
) -> list[FxCollectionLock]:
    """하트비트가 끊긴 잠금을 **지우지 않고** 돌려준다 (003 T028).

    회수 전에 그 작업을 부분 완료로 확정해야 하므로 `job_id`가 필요하다. 기존
    `reclaim_stale_locks`는 통화 코드만 돌려주고 행을 지워, 작업을 찾을 근거가 사라진다.

    001이 정한 900초 기준은 변경하지 않는다. 화면에 멈춤을 알리는 기준(60초)은 이것과
    별개다 — 경고는 사람에게 빨리 알리고 회수는 안전해진 뒤 한다 (FR-006a).
    """
    cutoff = dt.datetime.now() - dt.timedelta(seconds=older_than_seconds)
    return list((await session.execute(
        select(FxCollectionLock)
        .where(FxCollectionLock.heartbeat_at < cutoff)
        .where(FxCollectionLock.scope == scope))).scalars())


async def reclaim_stale_locks(
    session: AsyncSession, *,
    older_than_seconds: int = DEFAULT_STALE_SECONDS,
    scope: str | None = None,
) -> list[str]:
    """하트비트가 끊긴 잠금을 회수한다. 회수한 통화 목록을 돌려준다.

    새로고침은 수 초 내에 끝나므로 수집보다 짧은 만료를 쓴다. 길게 잡으면 프로세스가
    죽었을 때 새로고침이 오래 막힌다 (research R2-8).
    """
    cutoff = dt.datetime.now() - dt.timedelta(seconds=older_than_seconds)
    stmt = select(FxCollectionLock).where(FxCollectionLock.heartbeat_at < cutoff)
    if scope is not None:
        stmt = stmt.where(FxCollectionLock.scope == scope)
    rows = list((await session.execute(stmt)).scalars())
    for row in rows:
        await session.delete(row)
    return [r.currency_code for r in rows]
