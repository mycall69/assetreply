"""수수료·세율 설정 (T061) — 005 FR-015, FR-016, FR-017.

002의 스프레드 설정과 같은 자리에 둔다.

**설정이 바뀌면 이미 표시된 결과가 다시 제시되어야 한다**(FR-017). 서버는 저장만
하고 재산출은 화면이 다시 요청해서 얻는다 — 결과를 저장하지 않으므로
(research R5-9) 무효화할 캐시가 없다.

값을 **문자열로 주고받는다.** JSON `number`는 IEEE 754라 `Decimal` 정밀도가
손실되며, 이는 헌법 원칙 VI를 API 경계에서 무력화한다.
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from typing import Annotated, Final

from fastapi import APIRouter, Body, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.errors import InvalidSetting
from src.db.session import get_session
from src.repository.stock_setting import (
    DEFAULT_CAPITAL_GAINS_DEDUCTION,
    DEFAULT_CAPITAL_GAINS_RATE,
    DEFAULT_SALE_TAX_DOMESTIC,
    SaleTaxSettings,
    get_sale_tax,
    get_settings,
    save_sale_tax,
    save_settings,
)

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
    """현재 수수료·세율 (FR-015, FR-016). 배당 소득세는 국내·해외 두 값이다(006 FR-055)."""
    settings = await get_settings(session)
    return {
        "tradeFeeRate": str(settings.trade_fee_rate),
        "dividendTaxRateDomestic": str(settings.dividend_tax_rate_domestic),
        "dividendTaxRateForeign": str(settings.dividend_tax_rate_foreign),
        # 002 FR-033과 같은 규약 — 기본값에서 벗어났음을 사용자가 알아야 한다.
        "isDefault": settings.is_default,
    }


@router.put("/settings")
async def update_settings(
    session: Annotated[AsyncSession, Depends(get_session)],
    payload: Annotated[Json, Body()],
) -> Json:
    """수수료·세율을 저장한다."""
    # 세 값을 모두 받는다 — 빠진 값을 기본값으로 채우면 사용자가 넣지 않은 값으로 계산된다.
    fee = _rate(payload.get("tradeFeeRate"), "매매 수수료")
    domestic = _rate(payload.get("dividendTaxRateDomestic"), "배당 소득세(국내)")
    foreign = _rate(payload.get("dividendTaxRateForeign"), "배당 소득세(해외)")
    await save_settings(session, trade_fee_rate=fee, dividend_tax_rate_domestic=domestic,
                        dividend_tax_rate_foreign=foreign)
    await session.commit()
    return await read_settings(session)


# ── 011 — 매도 세금(FR-035~FR-037, contracts/rest-api §5) ─────────────────────

#: 세율의 소수 자릿수 상한 — DB 열(`SPREAD` Numeric(9,6))의 자릿수다. 넘으면 저장할 때 조용히
#: 반올림된다.
_RATE_PLACES: Final = 6
#: 공제(원) — 0 이상의 정수, DB 열(`WON` Numeric(15,0))의 자릿수 이하.
_DEDUCTION: Final = re.compile(r"^[0-9]{1,15}$")


def _sale_rate(raw: object, field: str) -> Decimal:
    """매도 세율 — 0 이상 1 미만, 소수 6자리 이하. `null`·숫자가 아닌 값은 막는다(0으로 떨어뜨리지
    않는다)."""
    if raw is None or isinstance(raw, bool):
        raise InvalidSetting(f"{field}가 비어 있습니다.")
    try:
        value = Decimal(str(raw))
    except (InvalidOperation, ValueError) as exc:
        raise InvalidSetting(f"{field}가 숫자가 아닙니다: {raw}") from exc
    # NaN·Infinity는 범위를 비교하기 전에 막는다 — NaN과의 비교는 예외다.
    if not value.is_finite():
        raise InvalidSetting(f"{field}가 숫자가 아닙니다: {raw}")
    if not (_MIN <= value < _MAX):
        raise InvalidSetting(f"{field}는 0 이상 1 미만이어야 합니다: {value}")
    exponent = value.as_tuple().exponent
    if isinstance(exponent, int) and exponent < -_RATE_PLACES:
        raise InvalidSetting(f"{field}는 소수 {_RATE_PLACES}자리까지입니다: {raw}")
    return value


def _deduction(raw: object) -> Decimal:
    """해외 기본공제 — 0 이상의 정수(원), 15자리 이하."""
    text = "" if raw is None or isinstance(raw, bool) else str(raw)
    if not _DEDUCTION.match(text):
        raise InvalidSetting(f"해외 기본공제는 0 이상의 정수(원), 15자리 이하여야 합니다: {raw}")
    return Decimal(text)


def _sale_tax_json(settings: SaleTaxSettings) -> Json:
    """값과 기본값. 기본값의 문자열은 010 반복 4의 표 값과 같다(`"0.0020"`·`"0.22"`·`"2500000"`)."""
    return {
        "saleTaxRateDomestic": str(settings.domestic),
        "capitalGainsRateForeign": str(settings.foreign_rate),
        "capitalGainsDeductionForeign": str(settings.foreign_deduction),
        "isDefault": settings.is_default,
        # 화면의 "기본값으로"가 이 값을 보낸다 — 화면에 기본값을 두 번 적지 않는다.
        "defaults": {
            "saleTaxRateDomestic": str(DEFAULT_SALE_TAX_DOMESTIC),
            "capitalGainsRateForeign": str(DEFAULT_CAPITAL_GAINS_RATE),
            "capitalGainsDeductionForeign": str(DEFAULT_CAPITAL_GAINS_DEDUCTION),
        },
    }


@router.get("/settings/sale-tax")
async def read_sale_tax(session: Annotated[AsyncSession, Depends(get_session)]) -> Json:
    """매도 세금 설정 — 국내 매도 세율·해외 양도소득세율·해외 기본공제(FR-035)."""
    return _sale_tax_json(await get_sale_tax(session))


@router.put("/settings/sale-tax")
async def update_sale_tax(
    session: Annotated[AsyncSession, Depends(get_session)],
    payload: Annotated[Json, Body()],
) -> Json:
    """매도 세금 설정을 저장한다. 세 값을 **모두** 받는다 — 빠진 값을 기본값으로 채우면 사용자가
    넣지 않은 값으로 계산된다. 하나라도 잘못이면 아무것도 저장하지 않는다(422)."""
    domestic = _sale_rate(payload.get("saleTaxRateDomestic"), "국내 매도 세율")
    rate = _sale_rate(payload.get("capitalGainsRateForeign"), "해외 양도소득세율")
    deduction = _deduction(payload.get("capitalGainsDeductionForeign"))
    await save_sale_tax(session, domestic=domestic, foreign_rate=rate, foreign_deduction=deduction)
    await session.commit()
    return await read_sale_tax(session)
