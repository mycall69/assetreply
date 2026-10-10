"""고른 종목 등록 (T039) — 006 FR-030, FR-030b, contracts/rest-api
`POST /api/stocks/selection`, research R6-17. 고른 종목의 상장일(`GET /api/stocks/listing-date` —
014 반복 2026-10-10g, FR-034, contracts A11)도 여기다.

검색 결과 하나를 받아 종목을 등록하고, 이후 요청이 쓸 식별(시장·심볼·이름·
통화)을 돌려준다. 화면은 이 응답의 식별로 시뮬레이션하고 이력에 남긴다.

본문을 직접 검증한다(005 `stock_settings`와 같은 방식). 형식 오류(422)가
아니라 **"이 경로로는 등록할 수 없다"(400)**는 사유를 말해야 하는 경우가
있다 — 일본 밖 시장의 외부 결과가 그렇다.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Body, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.errors import InvalidQuery, UnknownStock
from src.api.services.comparison_metrics import listing_json
from src.api.services.stock_selection import (
    FirstTradeLookup,
    Selected,
    fill_first_trade_date,
    get_first_trade,
    select_external,
    select_listing,
    stock_listing,
)
from src.db.session import get_session
from src.repository.stock import find_stock, find_us_stock
from src.search.price_symbol import US_MARKETS

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


@router.get("/listing-date")
async def get_listing_date(
    session: Annotated[AsyncSession, Depends(get_session)],
    first_trade: Annotated[FirstTradeLookup | None, Depends(get_first_trade)],
    market: Annotated[str, Query()],
    symbol: Annotated[str, Query()],
) -> Json:
    """고른 종목의 상장일 (014 반복 2026-10-10g — FR-034, contracts A11).

    메뉴의 고른 줄(검색 칸 아래)이 읽는다 — 고른 줄은 등록 뒤에도, 등록이 없는 이력 다시 실행(010)
    뒤에도 생긴다. 비교 블록과 같은 함수(`stock_listing`)라 같은 대상이면 같은 글자다. **등록하지
    않는다** — 없는 종목은 404다(실행이 등록한 뒤 다시 물으면 보인다).
    """
    stock = await find_stock(session, market, symbol)
    if stock is None and market in US_MARKETS:
        # 006 FR-030a — 다른 거래소로 등록된 같은 티커가 같은 종목이다.
        stock = await find_us_stock(session, symbol)
    if stock is None:
        raise UnknownStock(
            f"목록에서 찾을 수 없는 종목입니다: {market}:{symbol}. 검색에서 다시 고르세요.")
    listing = await stock_listing(session, stock, first_trade)
    return {"market": stock.market, "symbol": stock.symbol, "listing": listing_json(listing)}
