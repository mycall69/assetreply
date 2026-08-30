"""`GET·PUT /api/fx/spreads` (T068).

contracts/rest-api.md — 비율은 **문자열**로 주고받는다. JSON `number`로 왕복하면
정밀도가 손실되어 헌법 원칙 VI가 API 경계에서 무력화된다.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Annotated

from fastapi import APIRouter, Body, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.errors import InvalidSpread, UnknownCurrency
from src.db.session import get_session
from src.repository.spread import list_spreads, update_spread

router = APIRouter(prefix="/api/fx", tags=["fx"])

SUPPORTED = frozenset({"USD", "JPY", "EUR"})

Json = dict[str, object]


# 요청 본문의 카멜케이스 키 → 도메인 필드명
_PAYLOAD_KEYS = (
    ("cashBuy", "cash_buy"),
    ("cashSell", "cash_sell"),
    ("remitSend", "remit_send"),
    ("remitReceive", "remit_receive"),
)


def _to_decimals(payload: dict[str, str]) -> dict[str, Decimal]:
    """비율을 문자열로 받아 `Decimal`로 변환한다.

    JSON `number`로 받으면 배정밀도를 거치며 정밀도가 손실되므로 문자열만 허용한다
    (헌법 원칙 VI).
    """
    out: dict[str, Decimal] = {}
    for wire_key, field in _PAYLOAD_KEYS:
        raw = payload.get(wire_key)
        if not isinstance(raw, str):
            raise InvalidSpread(f"{wire_key}는 문자열이어야 합니다: {raw!r}")
        try:
            out[field] = Decimal(raw)
        except (InvalidOperation, ValueError) as exc:
            raise InvalidSpread(f"{wire_key}는 숫자여야 합니다: {raw!r}") from exc
    return out


def _serialize(row: object) -> Json:
    return {
        "currency": row.currency_code,  # type: ignore[attr-defined]
        "cashBuy": str(row.cash_buy),  # type: ignore[attr-defined]
        "cashSell": str(row.cash_sell),  # type: ignore[attr-defined]
        "remitSend": str(row.remit_send),  # type: ignore[attr-defined]
        "remitReceive": str(row.remit_receive),  # type: ignore[attr-defined]
    }


@router.get("/spreads")
async def list_spreads_endpoint(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Json:
    return {"spreads": [_serialize(r) for r in await list_spreads(session)]}


@router.put("/spreads/{currency}")
async def update_spread_endpoint(
    currency: str,
    payload: Annotated[dict[str, str], Body()],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Json:
    code = currency.upper()
    if code not in SUPPORTED:
        raise UnknownCurrency(f"지원하지 않는 통화입니다: {currency}")
    row = await update_spread(session, code, _to_decimals(payload))
    await session.commit()
    return _serialize(row)
