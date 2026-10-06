"""시뮬레이션 이력 저장소 (012 T052) — FR-011~FR-013, data-model 1.1.

조건 글과 시각만 다룬다 — 조건을 해석하거나 그것으로 계산하지 않는다(검증·식별자는
`api/services/history_conditions`). 시각은 UTC(시간대 없는 값)다.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.dialect import upsert
from src.db.models import SimulationHistory


@dataclass(frozen=True, slots=True)
class StoredHistory:
    key: str
    condition: str
    last_run_at: dt.datetime
    retain_from: dt.datetime


def _stored(row: SimulationHistory) -> StoredHistory:
    return StoredHistory(row.condition_key, row.condition, row.last_run_at, row.retain_from)


async def list_entries(session: AsyncSession, asset: str) -> list[StoredHistory]:
    """그 자산군의 항목 — 마지막 실행 내림차순(같으면 식별자 차례)."""
    rows = (
        (
            await session.execute(
                select(SimulationHistory)
                .where(SimulationHistory.asset_class == asset)
                .order_by(SimulationHistory.last_run_at.desc(), SimulationHistory.condition_key)
                .execution_options(populate_existing=True)
            )
        )
        .scalars()
        .all()
    )
    return [_stored(r) for r in rows]


async def find(session: AsyncSession, asset: str, keys: Sequence[str]) -> dict[str, StoredHistory]:
    if not keys:
        return {}
    rows = (
        (
            await session.execute(
                select(SimulationHistory)
                .where(
                    SimulationHistory.asset_class == asset,
                    SimulationHistory.condition_key.in_(list(keys)),
                )
                .execution_options(populate_existing=True)
            )
        )
        .scalars()
        .all()
    )
    return {r.condition_key: _stored(r) for r in rows}


async def save(session: AsyncSession, asset: str, entries: Sequence[StoredHistory]) -> None:
    """항목들을 넣거나 바꾼다 — 같은 조건(기본 키)이면 조건 글과 두 시각을 새 값으로 쓴다. 합칠 때의
    "늦은 쪽"은 부르는 쪽이 정한다."""
    await upsert(
        session,
        SimulationHistory,
        [
            {
                "asset_class": asset,
                "condition_key": e.key,
                "condition": e.condition,
                "last_run_at": e.last_run_at,
                "retain_from": e.retain_from,
            }
            for e in entries
        ],
        preserve=(),
    )


async def remove(session: AsyncSession, asset: str, key: str) -> None:
    await session.execute(
        delete(SimulationHistory).where(
            SimulationHistory.asset_class == asset, SimulationHistory.condition_key == key
        )
    )


async def purge(session: AsyncSession, cutoff: dt.datetime, asset: str | None = None) -> None:
    """보관 기준 시각이 `cutoff`보다 이른 항목을 지운다 — 경계(정확히 기간 전)는 남는다. `asset`이
    없으면 모든 자산군이다."""
    stmt = delete(SimulationHistory).where(SimulationHistory.retain_from < cutoff)
    if asset is not None:
        stmt = stmt.where(SimulationHistory.asset_class == asset)
    await session.execute(stmt)
