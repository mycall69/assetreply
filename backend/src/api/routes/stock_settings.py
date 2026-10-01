"""수수료·세율 설정 (T061) — 005 FR-015, FR-016, FR-017.

002의 스프레드 설정과 같은 자리에 둔다.

**설정이 바뀌면 이미 표시된 결과가 다시 제시되어야 한다**(FR-017). 서버는 저장만
하고 재산출은 화면이 다시 요청해서 얻는다 — 결과를 저장하지 않으므로
(research R5-9) 무효화할 캐시가 없다.

값을 **문자열로 주고받는다.** JSON `number`는 IEEE 754라 `Decimal` 정밀도가
손실되며, 이는 헌법 원칙 VI를 API 경계에서 무력화한다.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Annotated

from fastapi import APIRouter, Body, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.errors import InvalidSetting
from src.db.session import get_session
from src.repository.stock_setting import get_settings, save_settings

router = APIRouter(prefix="/api/stocks", tags=["stocks"])

Json = dict[str, object]

#: 비율의 허용 범위. 100% 이상의 수수료·세율은 현실에 없고, 음수는 돈을 받는다는 뜻이다.
_MIN = Decimal("0")
_MAX = Decimal("1")


def _rate(raw: object, field: str) -> Decimal:
    """비율을 읽고 범위를 본다.

    숫자가 아닐 때 **조용히 0으로 떨어뜨리지 않는다.** 0이면 수수료·세금이 사라진
    결과가 나오는데 값은 그럴듯하고 오류도 없다.
    """
    try:
        value = Decimal(str(raw))
    except (InvalidOperation, ValueError) as exc:
        raise InvalidSetting(f"{field}가 숫자가 아닙니다: {raw}") from exc
    if not (_MIN <= value < _MAX):
        raise InvalidSetting(f"{field}는 0 이상 1 미만이어야 합니다: {value}")
    return value


@router.get("/settings")
async def read_settings(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Json:
    """현재 수수료·세율 (FR-015, FR-016)."""
    settings = await get_settings(session)
    return {
        "tradeFeeRate": str(settings.trade_fee_rate),
        "dividendTaxRate": str(settings.dividend_tax_rate),
        # 002 FR-033과 같은 규약 — 기본값에서 벗어났음을 사용자가 알아야 한다.
        "isDefault": settings.is_default,
    }


@router.put("/settings")
async def update_settings(
    session: Annotated[AsyncSession, Depends(get_session)],
    payload: Annotated[Json, Body()],
) -> Json:
    """수수료·세율을 저장한다."""
    fee = _rate(payload.get("tradeFeeRate"), "매매 수수료")
    tax = _rate(payload.get("dividendTaxRate"), "배당 소득세")
    await save_settings(session, trade_fee_rate=fee, dividend_tax_rate=tax)
    await session.commit()
    return await read_settings(session)
