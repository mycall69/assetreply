"""수집 이력 보관 정책 (T100).

FR-038a: 실패·부분 성공 이력은 기한 없이 보관한다 — 원인 조사에 필요하다.
FR-038b: 성공 이력만 보관 기간 경과 후 정리한다.
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import FxCollectionJob, JobStatus


async def purge_succeeded_jobs(session: AsyncSession, *, retention_days: int) -> int:
    """보관 기간이 지난 **성공** 이력만 지운다. 지운 건수를 돌려준다."""
    cutoff = dt.datetime.now() - dt.timedelta(days=retention_days)
    condition = (
        (FxCollectionJob.status == JobStatus.SUCCEEDED)
        & (FxCollectionJob.finished_at.is_not(None))
        & (FxCollectionJob.finished_at < cutoff)
    )
    count = (await session.execute(
        select(func.count()).select_from(FxCollectionJob).where(condition))).scalar_one()
    if count:
        await session.execute(delete(FxCollectionJob).where(condition))
    return int(count)
