"""예금 이자 소득세율 설정 (T025) — 008 FR-030, FR-031, contracts/rest-api `GET`·`PUT
/api/deposit/settings`.

**주식·가상자산 설정과 따로다.** 값을 **문자열로** 주고받는다(헌법 원칙 VI) — JSON 숫자는 IEEE 754라
받지 않는다. 숫자가 아니거나 범위 밖이면 **조용히 0으로 떨어뜨리지 않는다** — 세금이 사라진 결과가
나오는데 값은 그럴듯하다(005와 같다).
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Annotated

from fastapi import APIRouter, Body, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.errors import InvalidSetting
from src.db.session import get_session
from src.repository.deposit_setting import get_settings, save_settings

router = APIRouter(prefix="/api/deposit", tags=["deposit"])

Json = dict[str, object]

#: 세율의 저장 자릿수(비율, `DECIMAL(9,6)`).
_PLACES = 6


def _rate(raw: object) -> Decimal:
    """0 이상 1 미만의 비율 문자열. 100% 이상의 세금은 없고, 음수는 세금을 돌려받는다는 뜻이다."""
    value: Decimal | None = None
    if isinstance(raw, str):
        try:
            value = Decimal(raw)
        except InvalidOperation:
            value = None
    if value is None or not value.is_finite() or not (Decimal(0) <= value < Decimal(1)):
        raise InvalidSetting(f"이자 소득세율은 0 이상 1 미만의 수(문자열)여야 합니다: {raw}")
    exponent = value.normalize().as_tuple().exponent
    if isinstance(exponent, int) and -exponent > _PLACES:
        # 저장 자릿수(DECIMAL(9,6))를 넘으면 조용히 반올림되어 넣은 세율과 달라진다
        # (FR-030, 반복 #2).
        raise InvalidSetting(f"이자 소득세율은 소수 {_PLACES}자리(백분율 4자리)까지입니다: {raw}")
    return value


@router.get("/settings")
async def read_settings(session: Annotated[AsyncSession, Depends(get_session)]) -> Json:
    settings = await get_settings(session)
    return {"interestTaxRate": format(settings.interest_tax_rate, "f"),
            "isDefault": settings.is_default}


@router.put("/settings")
async def update_settings(
    session: Annotated[AsyncSession, Depends(get_session)],
    payload: Annotated[Json, Body()],
) -> Json:
    """세율을 저장한다. 다음 시뮬레이션이 새 값을 쓴다 — 결과를 저장하지 않으므로 무효화할 것이
    없다."""
    await save_settings(session, interest_tax_rate=_rate(payload.get("interestTaxRate")))
    await session.commit()
    return await read_settings(session)
