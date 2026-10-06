"""예금 투자처 목록 (T020) — 008 FR-003, FR-006, contracts/rest-api `GET /api/deposit/institutions`.

라디오 버튼의 이름·설명과 받아 둔 범위다. **받기 전에는 시작 가능 날짜를 모른다**(research R8-12) —
상수로 박지 않는다. 출처의 통계표·항목 코드는 싣지 않는다(헌법 원칙 II).

011 — 투자처마다 `installment`(정기 적금)를 더한다(contracts/rest-api §4). 적금이 없는 투자처는
사유다. 적금의 시작 가능 날짜는 두 계열(적금·정기예금)을 다 받았을 때만 있다. 금리 계열 키는
싣지 않는다.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.services.deposit_collect import month_text
from src.api.services.deposit_installment import INSTALLMENT_OPTIONS, UNAVAILABLE_REASON
from src.api.services.deposit_simulation import INSTITUTIONS, SOURCE_BASIS, SOURCE_NAME
from src.db.models import DepositCoverage
from src.db.session import get_session
from src.repository import deposit_rate
from src.simulation.installment_ladder import startable_from

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
            "installment": _installment(institution.key, coverage),
        })
    return {"institutions": items, "source": SOURCE_NAME, "basis": SOURCE_BASIS}


def _installment(key: str, coverage: dict[str, DepositCoverage]) -> Json:
    option = INSTALLMENT_OPTIONS.get(key)
    if option is None:
        return {"available": False, "reason": UNAVAILABLE_REASON}
    saving = coverage.get(option.series)
    held = coverage.get(key)
    startable = (None if saving is None or held is None
                 else startable_from(saving.first_month, held.first_month))
    return {
        "available": True, "description": option.description,
        "firstMonth": None if saving is None else month_text(saving.first_month),
        "latestMonth": None if saving is None else month_text(saving.latest_month),
        "checkedOn": None if saving is None else saving.checked_on.isoformat(),
        "startableFrom": None if startable is None else startable.isoformat(),
    }
