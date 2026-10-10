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

014 반복 2026-10-10f(FR-033) — 고른 종목의 시세 출처 첫 거래일(`stock.first_trade_date` — 표시
전용)을 모르면 등록 때 한 번 받는다(`fill_first_trade_date`). **실패해도 등록은 성공한다** — 출처가
막혀도 종목을 고를 수 있어야 한다. 앱 수명주기의 공유 시세 클라이언트가 있을 때만 받는다 —
없으면(lifespan 없이 도는 테스트) 부르지 않아 006 등록 테스트가 실제 출처를 부르지 않는다(헌법 원칙
III).
"""

from __future__ import annotations

import asyncio
import datetime as dt
from dataclasses import dataclass
from typing import Final, Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from src.api.errors import InvalidQuery, UnknownListing
from src.db.models import Stock, StockListing
from src.ingestion.yahoo.errors import StockSourceError
from src.observability.logging_config import collection_logger
from src.repository import stock_listing as listing_repo
from src.repository.stock import ensure_stock, find_us_stock, record_first_trade_date
from src.search.price_symbol import US_MARKETS, listing_candidates, to_price_symbol

#: 외부 검색이 맡는 시장과 그 통화 (FR-026).
_EXTERNAL_MARKET: Final = "TSE"
_EXTERNAL_CURRENCY: Final = "JPY"


@dataclass(frozen=True, slots=True)
class Selected:
    stock: Stock
    listed_on: dt.date | None


async def _register_listing(session: AsyncSession, listing: StockListing) -> Stock:
    ps = to_price_symbol(listing.unit, listing.code)
    if ps.market in US_MARKETS:
        # FR-030a — 미국은 티커로 기존 행을 먼저 찾는다. 없을 때만 목록의 거래소로 만든다.
        existing = await find_us_stock(session, ps.symbol)
        if existing is not None:
            return existing
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
    부르면 왕복이 깨지므로 다른 종목으로 보지 않는다. 미국은 티커만 맞으면 된다(FR-030a).
    """
    key = listing_candidates(market, symbol)
    if key is None:
        return None
    for code in key.codes:
        listing = await listing_repo.find_listing(session, key.country, code)
        if listing is None:
            continue
        ps = to_price_symbol(listing.unit, listing.code)
        if market in US_MARKETS:
            return listing if ps.symbol == symbol else None
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


class FirstTradeSource(Protocol):
    """시세 출처의 첫 거래일 (014 FR-033) — `YahooStockClient.fetch_first_trade_date`."""

    async def fetch_first_trade_date(self, symbol: str) -> dt.date | None: ...


@dataclass(frozen=True, slots=True)
class FirstTradeLookup:
    """등록 때 첫 거래일을 받는 수단 — 출처와 시간 한도(초)."""

    source: FirstTradeSource
    timeout_seconds: float


_shared_source: FirstTradeSource | None = None


def set_shared_first_trade_source(source: FirstTradeSource | None) -> None:
    """앱 수명주기가 연 시세 클라이언트를 등록 경로에 넘긴다(닫을 때 `None`)."""
    global _shared_source
    _shared_source = source


def get_shared_first_trade_source() -> FirstTradeSource | None:
    return _shared_source


async def fill_first_trade_date(
    session: AsyncSession, stock: Stock, lookup: FirstTradeLookup | None
) -> None:
    """고른 종목의 첫 거래일을 모르면 한 번 받아 둔다 (014 FR-033, research R14-26).

    알면 부르지 않는다. 출처 실패·시간 초과·출처가 주지 않음이면 비운 채 돌아간다 — 등록 응답은
    그대로다. 다음 주식 수집 청크가 채운다(`collect_range`).
    """
    if lookup is None or stock.first_trade_date is not None:
        return
    try:
        day = await asyncio.wait_for(
            lookup.source.fetch_first_trade_date(stock.symbol), lookup.timeout_seconds)
    except (StockSourceError, TimeoutError) as exc:
        _event("stock_first_trade", symbol=stock.symbol, status="failed",
               reason=type(exc).__name__)
        return
    _event("stock_first_trade", symbol=stock.symbol, status="ok" if day else "none")
    if day is None:
        return
    await record_first_trade_date(session, stock.id, day)
    await session.commit()
    stock.first_trade_date = day


def _event(event: str, **fields: object) -> None:
    """출처를 부를 때마다 수집 로그에 한 줄(014 — 대시보드 출처 사건과 같은 곳)."""
    collection_logger().info(event, extra={"event": event, **fields})
