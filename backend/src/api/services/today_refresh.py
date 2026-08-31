"""오늘 새로고침 오케스트레이션 (T066).

FR-036a: **대량 수집과 독립적으로 동작한다.** 수집이 진행 중이라는 이유로 거부하지
않는다. 두 작업의 대상 구간이 겹치지 않기 때문이다(수집은 어제까지, 새로고침은 오늘만).
`scope='today_refresh'` 잠금을 써서 수집 잠금과 충돌하지 않게 한다 (research R2-8).

FR-036b: 같은 통화의 새로고침은 동시에 하나만. 중복 요청은 새 요청을 만들지 않고
진행 중인 것의 결과를 쓴다 — 버튼을 연타해도 호출이 늘지 않는다(SC-008).
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from src.config.settings import load_settings
from src.ingestion.protocols import FxRateSource
from src.ingestion.today import fetch_today
from src.repository.collection_lock import (
    SCOPE_TODAY_REFRESH,
    acquire_lock,
    reclaim_stale_locks,
    release_lock,
)
from src.repository.fx_rate import get_rate
from src.repository.job import create_job


@dataclass(frozen=True, slots=True)
class RefreshResult:
    currency: str
    status: str  # "updated" | "no_quote_today"
    date: dt.date
    base_rate: Decimal | None
    fetched_at: dt.datetime
    joined_existing: bool


async def refresh_today(
    session: AsyncSession,
    source: FxRateSource,
    currency_code: str,
    *,
    today: dt.date | None = None,
    release: bool = True,
) -> RefreshResult:
    """오늘 하루치를 다시 받아 잠정으로 저장한다.

    `release=False`는 테스트에서 "진행 중" 상태를 만들 때만 쓴다. 운영 경로에서는
    성공·실패와 무관하게 잠금을 푼다 — 남으면 재시도가 영영 막힌다.
    """
    day = today or dt.date.today()
    settings = load_settings()

    # 프로세스가 죽어 남은 잠금을 먼저 회수한다. 새로고침은 수 초면 끝나므로
    # 수집보다 짧은 만료를 쓴다.
    await reclaim_stale_locks(
        session,
        older_than_seconds=settings.today_refresh_lock_ttl_seconds,
        scope=SCOPE_TODAY_REFRESH,
    )
    await session.commit()

    job = await create_job(session, currency_code, day, day, chunks_total=1)
    existing = await acquire_lock(
        session, currency_code, job.id, scope=SCOPE_TODAY_REFRESH)

    if existing is not None:
        # 이미 진행 중이다. 새 요청을 만들지 않고 현재 저장된 값을 그대로 쓴다.
        await session.rollback()
        row = await get_rate(session, currency_code, day)
        return RefreshResult(
            currency=currency_code,
            status="updated" if row is not None else "no_quote_today",
            date=day,
            base_rate=row.base_rate if row is not None else None,
            fetched_at=row.updated_at if row is not None else dt.datetime.now(),
            joined_existing=True,
        )

    await session.commit()
    try:
        row = await fetch_today(session, source, currency_code, day)
    finally:
        if release:
            await release_lock(session, currency_code, scope=SCOPE_TODAY_REFRESH)
            await session.commit()

    return RefreshResult(
        currency=currency_code,
        status="updated" if row is not None else "no_quote_today",
        date=day,
        base_rate=row.base_rate if row is not None else None,
        fetched_at=row.updated_at if row is not None else dt.datetime.now(),
        joined_existing=False,
    )
