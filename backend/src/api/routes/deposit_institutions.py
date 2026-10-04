"""예금 투자처 목록 (T020) — 008 FR-003, FR-006, contracts/rest-api `GET /api/deposit/institutions`.

라디오 버튼의 이름·설명과 받아 둔 범위다. **받기 전에는 시작 가능 날짜를 모른다**(research R8-12) —
상수로 박지 않는다. 출처의 통계표·항목 코드는 싣지 않는다(헌법 원칙 II).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.services.deposit_collect import month_text
from src.api.services.deposit_simulation import INSTITUTIONS, SOURCE_BASIS, SOURCE_NAME
from src.db.session import get_session
from src.repository import deposit_rate

router = APIRouter(prefix="/api/deposit", tags=["deposit"])

Json = dict[str, object]


@router.get("/institutions")
async def get_institutions(session: Annotated[AsyncSession, Depends(get_session)]) -> Json:
    coverage = await deposit_rate.all_coverage(session)
    items: list[Json] = []
    for institution in INSTITUTIONS:
        known = coverage.get(institution.key)
        items.append({
            "key": institution.key, "name": institution.name,
            "description": institution.description,
            "firstMonth": None if known is None else month_text(known.first_month),
            "latestMonth": None if known is None else month_text(known.latest_month),
            "checkedOn": None if known is None else known.checked_on.isoformat(),
        })
    return {"institutions": items, "source": SOURCE_NAME, "basis": SOURCE_BASIS}
