"""`GET·PUT /api/fx/spreads` · `POST /api/fx/spreads/restore` (T068, T050).

contracts/rest-api.md — 비율은 **문자열**로 주고받는다. JSON `number`로 왕복하면
정밀도가 손실되어 헌법 원칙 VI가 API 경계에서 무력화된다.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Annotated

from fastapi import APIRouter, Body, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.errors import InvalidSpread, UnknownCurrency
from src.config.settings import SUPPORTED_CURRENCIES
from src.db.session import get_session
from src.db.spread_defaults import DEFAULT_SPREADS, FIELDS, default_for, is_default
from src.repository.spread import list_spreads, update_spread

router = APIRouter(prefix="/api/fx", tags=["fx"])

# 통화 순서는 항상 USD → JPY → EUR다 (FR-027). 정렬 옵션을 두지 않는다.
SUPPORTED = frozenset(SUPPORTED_CURRENCIES)

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


def _values(row: object) -> dict[str, Decimal]:
    return {f: getattr(row, f) for f in FIELDS}


def _serialize(row: object) -> Json:
    code: str = row.currency_code  # type: ignore[attr-defined]
    values = _values(row)
    return {
        "currency": code,
        "cashBuy": str(values["cash_buy"]),
        "cashSell": str(values["cash_sell"]),
        "remitSend": str(values["remit_send"]),
        "remitReceive": str(values["remit_receive"]),
        # 화면이 별도 조회 없이 "기본값과 다름"을 표시할 수 있게 한다 (FR-033).
        "isDefault": is_default(values, code),
    }


def _default_json(code: str) -> Json:
    values = DEFAULT_SPREADS[code]
    return {
        "currency": code,
        "cashBuy": str(values["cash_buy"]),
        "cashSell": str(values["cash_sell"]),
        "remitSend": str(values["remit_send"]),
        "remitReceive": str(values["remit_receive"]),
    }


def _ordered(rows: list[object]) -> list[object]:
    """USD → JPY → EUR 순서를 강제한다 (FR-027)."""
    order = {c: i for i, c in enumerate(SUPPORTED_CURRENCIES)}
    return sorted(rows, key=lambda r: order.get(r.currency_code, 99))  # type: ignore[attr-defined]


@router.get("/spreads")
async def list_spreads_endpoint(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Json:
    rows = _ordered(list(await list_spreads(session)))
    return {
        "spreads": [_serialize(r) for r in rows],
        "defaults": [_default_json(c) for c in SUPPORTED_CURRENCIES],
    }


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


@router.post("/spreads/restore")
async def restore_spreads_endpoint(
    session: Annotated[AsyncSession, Depends(get_session)],
    payload: Annotated[dict[str, str] | None, Body()] = None,
) -> Json:
    """스프레드를 기본값으로 되돌린다 (FR-031, FR-031a).

    `currency`를 생략하면 전 통화가 대상이다. 일부가 실패해도 **성공한 복원을 되돌리지
    않는다** — 부분 성공을 오류로 처리하면 화면이 성공한 복원까지 실패로 표시하게 된다.
    호출자는 `failed`의 길이로 판정한다.
    """
    requested = (payload or {}).get("currency")
    if requested is not None and requested.upper() not in SUPPORTED:
        raise UnknownCurrency(f"지원하지 않는 통화입니다: {requested}")

    targets = [requested.upper()] if requested else list(SUPPORTED_CURRENCIES)

    restored: list[str] = []
    failed: list[Json] = []
    for code in targets:
        try:
            await update_spread(session, code, default_for(code))
            restored.append(code)
        except Exception as exc:  # noqa: BLE001 — 통화별로 격리해 부분 성공을 보존한다
            failed.append({"currency": code, "reason": str(exc) or "복원에 실패했습니다."})
    await session.commit()

    rows = _ordered(list(await list_spreads(session)))
    return {
        "restored": restored,
        "failed": failed,
        # 복원 시도 후의 실제 값. 화면이 이 값으로 그대로 갱신하면 된다.
        "spreads": [_serialize(r) for r in rows],
    }
