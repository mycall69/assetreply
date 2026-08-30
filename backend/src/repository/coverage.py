"""수집 커버리지 리포지토리 (T049)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import FxCoverage


async def get_coverage(session: AsyncSession, currency_code: str) -> FxCoverage | None:
    return (await session.execute(
        select(FxCoverage).where(
            FxCoverage.currency_code == currency_code))).scalar_one_or_none()


async def list_coverage(session: AsyncSession) -> list[FxCoverage]:
    return list((await session.execute(
        select(FxCoverage).order_by(FxCoverage.currency_code))).scalars())
