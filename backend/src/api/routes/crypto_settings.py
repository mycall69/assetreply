"""가상자산 거래 수수료율 설정 (T032) — 007 FR-032, FR-033, contracts/rest-api `GET`·`PUT
/api/crypto/settings`.

**주식 설정과 따로다.** 값을 문자열로 주고받는다(헌법 원칙 VI). 숫자가 아니거나 범위 밖이면 **조용히
0으로 떨어뜨리지 않는다** — 수수료가 사라진 결과가 나오는데 값은 그럴듯하다(005와 같다).
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Annotated

from fastapi import APIRouter, Body, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.errors import InvalidSetting
from src.db.session import get_session
from src.repository.crypto_setting import get_settings, save_settings

router = APIRouter(prefix="/api/crypto", tags=["crypto"])

Json = dict[str, object]


def _rate(raw: object) -> Decimal:
    """0 이상 1 미만의 비율. 100% 이상의 수수료는 없고, 음수는 돈을 받는다는 뜻이다."""
    try:
        value = Decimal(str(raw)) if isinstance(raw, str | int) else None
    except InvalidOperation:
        value = None
    if value is None or not value.is_finite() or not (Decimal(0) <= value < Decimal(1)):
        raise InvalidSetting(f"거래 수수료율은 0 이상 1 미만의 수여야 합니다: {raw}")
    return value


@router.get("/settings")
async def read_settings(session: Annotated[AsyncSession, Depends(get_session)]) -> Json:
    settings = await get_settings(session)
    return {"tradeFeeRate": format(settings.trade_fee_rate, "f"), "isDefault": settings.is_default}


@router.put("/settings")
async def update_settings(
    session: Annotated[AsyncSession, Depends(get_session)],
    payload: Annotated[Json, Body()],
) -> Json:
    """수수료율을 저장한다. 다음 시뮬레이션이 새 값을 쓴다 — 결과를 저장하지 않으므로 무효화할 것이
    없다."""
    await save_settings(session, trade_fee_rate=_rate(payload.get("tradeFeeRate")))
    await session.commit()
    return await read_settings(session)
