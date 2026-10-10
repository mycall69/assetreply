"""고른 종목 등록 (T039) — 006 FR-030, FR-030b, contracts/rest-api
`POST /api/stocks/selection`, research R6-17.

검색 결과 하나를 받아 종목을 등록하고, 이후 요청이 쓸 식별(시장·심볼·이름·
통화)을 돌려준다. 화면은 이 응답의 식별로 시뮬레이션하고 이력에 남긴다.

본문을 직접 검증한다(005 `stock_settings`와 같은 방식). 형식 오류(422)가
아니라 **"이 경로로는 등록할 수 없다"(400)**는 사유를 말해야 하는 경우가
있다 — 일본 밖 시장의 외부 결과가 그렇다.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Body, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.errors import InvalidQuery
from src.api.services.stock_selection import (
    FirstTradeLookup,
    Selected,
    fill_first_trade_date,
    get_first_trade,
    select_external,
    select_listing,
)
from src.db.session import get_session

router = APIRouter(prefix="/api/stocks", tags=["stocks"])

Json = dict[str, object]


def _text(payload: Json, key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str):
        raise InvalidQuery(f"{key}가 문자열이 아닙니다.")
    return value


def selected_json(selected: Selected) -> Json:
    stock = selected.stock
    return {
        "market": stock.market, "symbol": stock.symbol, "name": stock.name,
        "currency": stock.currency,
        "listedOn": selected.listed_on.isoformat() if selected.listed_on else None,
    }


@router.post("/selection")
async def post_selection(
    session: Annotated[AsyncSession, Depends(get_session)],
    payload: Annotated[Json, Body()],
    first_trade: Annotated[FirstTradeLookup | None, Depends(get_first_trade)],
) -> Json:
    source = payload.get("source")
    if source == "listing":
        listing_id = payload.get("listingId")
        if not isinstance(listing_id, int) or isinstance(listing_id, bool):
            raise InvalidQuery("listingId가 정수가 아닙니다.")
        selected = await select_listing(session, listing_id)
    elif source == "external":
        selected = await select_external(
            session, market=_text(payload, "market"), symbol=_text(payload, "symbol"),
            name=_text(payload, "name"), currency=_text(payload, "currency"))
    else:
        raise InvalidQuery("source는 listing 또는 external이어야 합니다.")
    # 014 FR-033 — 응답은 그대로다. 첫 거래일은 표시 전용 열에만 남는다.
    await fill_first_trade_date(session, selected.stock, first_trade)
    return selected_json(selected)
