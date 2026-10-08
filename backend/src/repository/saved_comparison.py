"""저장한 비교 저장소 (013 T070) — FR-016, FR-018, data-model 1.1.

이름·조건 글·시각만 다룬다 — 조건을 해석하지 않는다(검증·정규화는
`api/services/comparison_conditions`). 서비스의 `SavedComparisonRepository` Protocol을 이 모듈이
채운다(헌법 원칙 IV — 서비스는 이 모듈을 모른다). 시각은 UTC(시간대 없는 값)다.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import SavedComparison


@dataclass(frozen=True, slots=True)
class StoredComparison:
    id: int
    name: str
    asset: str
    condition: str
    saved_at: dt.datetime


def _stored(row: SavedComparison) -> StoredComparison:
    return StoredComparison(row.id, row.name, row.asset_class, row.condition, row.saved_at)


async def list_entries(session: AsyncSession) -> list[StoredComparison]:
    """모든 항목 — 저장 시각 내림차순, 같은 초는 `id` 내림차순."""
    rows = (
        (
            await session.execute(
                select(SavedComparison)
                .order_by(SavedComparison.saved_at.desc(), SavedComparison.id.desc())
                .execution_options(populate_existing=True)
            )
        )
        .scalars()
        .all()
    )
    return [_stored(r) for r in rows]


async def add(
    session: AsyncSession, *, name: str, asset: str, condition: str, saved_at: dt.datetime
) -> int:
    """새 행을 넣고 그 `id`를 돌려준다 — 같은 조건·이름이어도 새 행이다."""
    row = SavedComparison(name=name, asset_class=asset, condition=condition, saved_at=saved_at)
    session.add(row)
    await session.flush()
    return row.id


async def remove(session: AsyncSession, comparison_id: int) -> None:
    """없는 `id`도 조용히 지나간다(멱등 — 두 창에서 지워도 오류가 아니다)."""
    await session.execute(delete(SavedComparison).where(SavedComparison.id == comparison_id))
