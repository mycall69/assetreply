"""이력 보관 기간 (012 T052) — FR-012, data-model 1.2.

**전역 단일 행이고 모든 자산군이 함께 쓴다.** 행이 없으면 기본 30일이다 — 기본값을 코드에 둔다(다른
설정과 같다). 보관 기간은 열거 값이다 — NULL에
"기본값"과 "무기한" 두 뜻을 싣지 않는다(research R12-9).
"""

from __future__ import annotations

from typing import Final

from sqlalchemy.ext.asyncio import AsyncSession

from src.db.dialect import upsert
from src.db.models import HISTORY_RETENTIONS, HistorySetting

DEFAULT_RETENTION: Final = "days_30"
_ROW_ID = 1


async def get_retention(session: AsyncSession) -> str:
    """보관 기간(`days_7` … `days_365` · `unlimited`). 행이 없으면 기본값이다."""
    row = await session.get(HistorySetting, _ROW_ID, populate_existing=True)
    return DEFAULT_RETENTION if row is None else row.retention


async def save_retention(session: AsyncSession, retention: str) -> None:
    """보관 기간을 저장한다. 값은 서비스가 검증해 넘긴다 — 여기서 기본값으로 바꾸지 않는다."""
    if retention not in HISTORY_RETENTIONS:
        raise ValueError(f"모르는 보관 기간: {retention}")
    await upsert(session, HistorySetting, [{"id": _ROW_ID, "retention": retention}], preserve=())
