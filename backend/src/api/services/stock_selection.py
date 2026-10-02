"""고른 종목의 등록 (T039) — 006 FR-030, FR-030b, FR-033, research R6-6, R6-17.

**고르는 순간 등록한다.** 005는 고른 종목을 저장하는 경로가 없어(`ensure_stock` 호출처 0) 고른
종목마다 실행에서 "알 수 없는 종목"으로 끝났다. 고르는 순간에 등록하면 실패가 그 자리에서 드러난다.

- 국내: 검색용 목록의 행으로 등록한다. 식별은 research R6-6의 규칙이다
- 일본: 외부 검색 결과로 등록한다. 시장은 TSE, 통화는 JPY로 고정해 검증한다
- 이력 재실행(브라우저의 이력은 DB와 따로 산다): 시세 식별자에서 **역변환**으로 목록을 찾아
  등록한다. 정방향으로 다시 옮긴 식별자가 요청과 같을 때만 등록한다 — 다르면 다른 종목을 등록하게
  된다

**목록의 상장일을 `stock.first_available_date`에 복사하지 않는다**(research R6-8). 상장일은 하한일
뿐이다.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Final

from sqlalchemy.ext.asyncio import AsyncSession

from src.api.errors import InvalidQuery, UnknownListing
from src.db.models import Stock, StockListing
from src.repository import stock_listing as listing_repo
from src.repository.stock import ensure_stock
from src.search.price_symbol import listing_candidates, to_price_symbol

#: 외부 검색이 맡는 시장과 그 통화 (FR-026).
_EXTERNAL_MARKET: Final = "TSE"
_EXTERNAL_CURRENCY: Final = "JPY"


@dataclass(frozen=True, slots=True)
class Selected:
    stock: Stock
    listed_on: dt.date | None


async def _register_listing(session: AsyncSession, listing: StockListing) -> Stock:
    ps = to_price_symbol(listing.unit, listing.code)
    return await ensure_stock(
        session, market=ps.market, symbol=ps.symbol,
        name=listing.name_ko or listing.name_en or listing.code, currency=ps.currency)


async def select_listing(session: AsyncSession, listing_id: int) -> Selected:
    """검색용 목록의 행으로 등록한다. 이미 있으면 그 종목이다(FR-030, SC-007)."""
    listing = await listing_repo.get_listing(session, listing_id)
    if listing is None:
        raise UnknownListing(f"목록에서 찾을 수 없는 종목입니다: {listing_id}")
    stock = await _register_listing(session, listing)
    await session.commit()
    return Selected(stock, listing.listed_on)


async def select_external(
    session: AsyncSession, *, market: str, symbol: str, name: str, currency: str
) -> Selected:
    """일본 외부 검색 결과로 등록한다. 일본 밖은 로컬 목록이 맡으므로 거절한다(FR-026)."""
    if market != _EXTERNAL_MARKET or currency != _EXTERNAL_CURRENCY:
        raise InvalidQuery(
            f"외부 검색 결과는 {_EXTERNAL_MARKET}·{_EXTERNAL_CURRENCY} 종목만 등록할 수 있습니다: "
            f"{market}·{currency}")
    if not symbol.strip() or not name.strip():
        raise InvalidQuery("종목 심볼과 이름이 비어 있습니다.")
    stock = await ensure_stock(session, market=market, symbol=symbol.strip(),
                               name=name.strip(), currency=currency)
    await session.commit()
    return Selected(stock, None)


async def listing_for(
    session: AsyncSession, market: str, symbol: str
) -> StockListing | None:
    """시세 식별자에 해당하는 검색용 목록 종목 (research R6-6 역변환). 없으면 `None`.

    정방향으로 다시 옮긴 식별자가 요청과 같을 때만 그 종목이다 — 코스닥 종목을 `.KS`로
    부르면 왕복이 깨지므로 다른 종목으로 보지 않는다.
    """
    key = listing_candidates(market, symbol)
    if key is None:
        return None
    for code in key.codes:
        listing = await listing_repo.find_listing(session, key.country, code)
        if listing is None:
            continue
        ps = to_price_symbol(listing.unit, listing.code)
        return listing if (ps.market, ps.symbol) == (market, symbol) else None
    return None


async def register_from_price_symbol(
    session: AsyncSession, market: str, symbol: str
) -> Stock | None:
    """시세 식별자에서 목록을 거꾸로 찾아 등록한다. 찾지 못하면 `None`.

    **커밋하지 않는다.** 시뮬레이션이 이어서 수집 작업을 만들며 함께 커밋한다.
    """
    listing = await listing_for(session, market, symbol)
    if listing is None:
        return None
    return await _register_listing(session, listing)
