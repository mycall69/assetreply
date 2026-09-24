"""수집 이벤트 리포지토리 (T013) — FR-022, FR-023, research R3-9.

보관 범위는 **통화별 최근 N개 작업**이다. 기간이 아니라 작업 수로 자르는 이유는,
이 기록의 쓰임이 "시계열에 구멍이 왜 생겼는지"를 작업 단위로 되짚는 것이기 때문이다.
작업 수로 자르면 수집을 자주 돌리든 드물게 돌리든 최근 이력의 깊이가 일정하다.

**작업 행 자체는 지우지 않는다.** 사건만 정리 대상이다 — 작업 목록은 가볍고, 지우면
"언제 수집했는지"가 사라진다.
"""

from __future__ import annotations

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import FxCollectionEvent
from src.observability.events import CollectionEvent


async def record(session: AsyncSession, event: CollectionEvent) -> FxCollectionEvent:
    """사건 하나를 적재한다. 커밋은 호출자가 한다."""
    row = FxCollectionEvent(**event.as_row())
    session.add(row)
    await session.flush()
    return row


async def list_by_job(
    session: AsyncSession, job_id: int, *, limit: int = 100
) -> list[FxCollectionEvent]:
    """한 작업의 사건을 최근 순으로 돌려준다."""
    return list((await session.execute(
        select(FxCollectionEvent)
        .where(FxCollectionEvent.job_id == job_id)
        .order_by(FxCollectionEvent.occurred_at.desc(), FxCollectionEvent.id.desc())
        .limit(limit))).scalars())


async def list_by_currency(
    session: AsyncSession, currency_code: str, *, limit: int = 100
) -> list[FxCollectionEvent]:
    """한 통화의 사건을 최근 순으로 돌려준다. 여러 작업에 걸친다."""
    return list((await session.execute(
        select(FxCollectionEvent)
        .where(FxCollectionEvent.currency_code == currency_code)
        .order_by(FxCollectionEvent.occurred_at.desc(), FxCollectionEvent.id.desc())
        .limit(limit))).scalars())


async def dropped_for_currency(session: AsyncSession, currency_code: str, *,
                               keep_jobs: int) -> int:
    """보관 범위 안 작업들의 기록 누락 건수 합계 (FR-018b)."""
    from src.db.models import FxCollectionJob

    kept = await _recent_job_ids(session, currency_code, keep_jobs)
    if not kept:
        return 0
    return (await session.execute(
        select(func.coalesce(func.sum(FxCollectionJob.events_dropped), 0))
        .where(FxCollectionJob.id.in_(kept)))).scalar_one()


async def prune_to_recent_jobs(
    session: AsyncSession, currency_code: str, *, keep_jobs: int
) -> int:
    """통화별 최근 `keep_jobs`개 작업 밖의 사건을 지운다. 지운 건수를 돌려준다.

    **작업이 끝날 때 호출한다.** 새 작업이 생길 때만 보관 경계가 밀리므로, 그때 한 번
    정리하면 경계가 항상 맞는다. 주기 태스크는 아무 일도 없는 동안 헛돌고, 조회 시점
    정리는 읽기 경로에 쓰기를 섞는다 (research R3-9).
    """
    kept = await _recent_job_ids(session, currency_code, keep_jobs)
    stmt = delete(FxCollectionEvent).where(
        FxCollectionEvent.currency_code == currency_code)
    if kept:
        stmt = stmt.where(FxCollectionEvent.job_id.notin_(kept))
    result = await session.execute(stmt)
    return int(getattr(result, "rowcount", 0) or 0)


async def _recent_job_ids(
    session: AsyncSession, currency_code: str, keep_jobs: int
) -> list[int]:
    """통화의 최근 작업 ID를 먼저 조회한다.

    서브쿼리로 넘기지 않는 이유는 **MySQL이 `IN` 서브쿼리 안의 `LIMIT`을 지원하지
    않기** 때문이다. 파생 테이블로 감싸 우회할 수 있지만 그것도 DB마다 다르다. 왕복이
    한 번 늘어도 표준 SQL로 남기는 편이 이식성 규약에 맞다(헌법 DB 운영 규약).

    보관 범위는 20개 안팎이라 목록이 길어질 일이 없다.

    `started_at`이 아니라 `id` 기준으로 정렬한다 — 같은 초에 시작한 작업들의 순서가
    안정적이어야 경계가 흔들리지 않는다.
    """
    from src.db.models import FxCollectionJob

    return list((await session.execute(
        select(FxCollectionJob.id)
        .where(FxCollectionJob.currency_code == currency_code)
        .order_by(FxCollectionJob.id.desc())
        .limit(keep_jobs))).scalars())
