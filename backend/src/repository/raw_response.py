"""원본 응답 리포지토리 (T048).

FR-004a: 기한 없이 보관한다. 자동 정리를 하지 않는다 — 값이 갱신된 경우 갱신 전 값을
추적하는 유일한 근거이기 때문이다(FR-003b).
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import FxRawResponse


async def count_for_currency(session: AsyncSession, currency_code: str) -> int:
    return (await session.execute(
        select(func.count()).select_from(FxRawResponse)
        .where(FxRawResponse.currency_code == currency_code))).scalar_one()


async def recent(
    session: AsyncSession, currency_code: str, *, limit: int = 20
) -> list[FxRawResponse]:
    return list((await session.execute(
        select(FxRawResponse)
        .where(FxRawResponse.currency_code == currency_code)
        .order_by(FxRawResponse.received_at.desc())
        .limit(limit))).scalars())
