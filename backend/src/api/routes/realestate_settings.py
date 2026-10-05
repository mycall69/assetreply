"""부동산 보유세 기준 비율 설정 (009 T043, FR-034, contracts/rest-api `GET`·`PUT
/api/realestate/settings`).

**다른 자산군 설정과 따로다.** 값을 **문자열로** 주고받는다(헌법 원칙 VI) — JSON 숫자는 IEEE 754라
받지 않는다. 0 < 비율 ≤ 1, 소수 6자리(백분율 4자리)까지. 아니면 422 — 조용히 기본값으로 떨어뜨리거나
반올림해 저장하지 않는다 (넣은 값과 다른 보유세가 그럴듯한 값으로 나온다).
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Annotated

from fastapi import APIRouter, Body, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.errors import InvalidSetting
from src.db.session import get_session
from src.repository.apt_setting import get_settings, save_settings

router = APIRouter(prefix="/api/realestate", tags=["realestate"])

Json = dict[str, object]

#: 비율의 저장 자릿수(`DECIMAL(9,6)`).
_PLACES = 6


def _ratio(raw: object) -> Decimal:
    value: Decimal | None = None
    if isinstance(raw, str):
        try:
            value = Decimal(raw)
        except InvalidOperation:
            value = None
    if value is None or not value.is_finite() or not (Decimal(0) < value <= Decimal(1)):
        raise InvalidSetting(f"보유세 기준 비율은 0보다 크고 1 이하인 수(문자열)여야 합니다: {raw}")
    exponent = value.normalize().as_tuple().exponent
    if isinstance(exponent, int) and -exponent > _PLACES:
        raise InvalidSetting(
            f"보유세 기준 비율은 소수 {_PLACES}자리(백분율 4자리)까지입니다: {raw}")
    return value


@router.get("/settings")
async def read_settings(session: Annotated[AsyncSession, Depends(get_session)]) -> Json:
    settings = await get_settings(session)
    return {"holdingTaxBaseRatio": format(settings.holding_tax_base_ratio, ".6f"),
            "isDefault": settings.is_default}


@router.put("/settings")
async def update_settings(
    session: Annotated[AsyncSession, Depends(get_session)],
    payload: Annotated[Json, Body()],
) -> Json:
    """비율을 저장한다. 다음 시뮬레이션이 새 값을 쓴다 — 결과를 저장하지 않으므로 무효화할 것이
    없다."""
    await save_settings(session, holding_tax_base_ratio=_ratio(payload.get("holdingTaxBaseRatio")))
    await session.commit()
    return await read_settings(session)
