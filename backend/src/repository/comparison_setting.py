"""투자 비교 설정 (014 반복 2026-10-13 T216) — FR-044, data-model 18.1.

**전역 단일 행이다.** 읽기는 행을 만들지 않는다 — 없으면 `None`이고 기본값(20)은 서비스가 정한다(한
곳). 저장은 한 행 upsert다. 범위는 저장소가 모른다 — 서비스가 검증해 넘긴다(012 `history_setting`과
같은 나눔).
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from src.db.dialect import upsert
from src.db.models import ComparisonSetting

_ROW_ID = 1


async def get_max_targets(session: AsyncSession) -> int | None:
    """저장된 최대 대상 수. 행이 없으면 `None`이다."""
    row = await session.get(ComparisonSetting, _ROW_ID, populate_existing=True)
    return None if row is None else row.max_targets


async def save_max_targets(session: AsyncSession, value: int) -> None:
    """최대 대상 수를 저장한다. 값은 서비스가 검증해 넘긴다 — 여기서 범위로 자르지 않는다."""
    await upsert(session, ComparisonSetting, [{"id": _ROW_ID, "max_targets": value}], preserve=())
