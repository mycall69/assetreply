"""주식 적립식 경로 (011 T026) — contracts/rest-api §1. FR-002, FR-004, FR-012~FR-016.

일시금 경로(`/api/stocks/simulation`)와 **따로 둔다**(research R11-10) — 일시금의 조회 문자열과 응답
모양은 기존 테스트가 정확히 고정하고, 같은 경로에 방식을 더하면 응답이 두 모양의 합집합이 된다.
검증·수집 판정 함수는 일시금과 같은 것을 같은 순서로 부른다 — 규칙이 갈라지지 않는다.

금액·비율은 모두 **문자열**이다(헌법 원칙 VI — JSON number는 IEEE 754).
"""

from __future__ import annotations

import datetime as dt
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.services.recurring_series import build_stock_series
from src.api.services.series_query import DEFAULT_MAX_POINTS
from src.api.services.stock_collect import collecting_body
from src.api.services.stock_recurring import (
    PreparedRecurring,
    dec,
    page,
    parse_amount,
    parse_frequency,
    prepare_recurring,
    row_json,
    summary_json,
)
from src.api.services.stock_simulation import (
    check_principal_currency,
    require_start_available,
    require_stock,
)
from src.db.session import get_session
from src.repository.stock import get_coverage

router = APIRouter(prefix="/api/stocks", tags=["stocks"])

Json = dict[str, object]


async def _prepare_or_collect(session: AsyncSession, *, market: str, symbol: str, start: dt.date,
                              amount_raw: str, principal_currency: str, frequency_raw: str,
                              reinvest: bool, end: dt.date | None,
                              ) -> PreparedRecurring | JSONResponse:
    """표와 차트가 **같은 판정·같은 계산**을 쓴다 — 한쪽만 막거나 한쪽만 설정을 빠뜨려도 오류 없이
    다른 숫자가 나온다(005 SC-032)."""
    check_principal_currency(principal_currency)
    amount = parse_amount(amount_raw)
    frequency = parse_frequency(frequency_raw)
    # 끝은 기본적으로 어제다(일시금과 같다). 오늘 시세는 장중에 바뀐다.
    finish = end or (dt.date.today() - dt.timedelta(days=1))
    stock = await require_stock(session, market, symbol)
    check_principal_currency(principal_currency, stock.currency)
    await require_start_available(session, stock, start)
    collecting = await collecting_body(session, stock, start=start, end=finish)
    if collecting is not None:
        return JSONResponse(status_code=202, content=collecting)
    return await prepare_recurring(
        session, market=market, symbol=symbol, start=start, end=finish, amount=amount,
        principal_currency=principal_currency, frequency=frequency, reinvest=reinvest)


@router.get("/recurring-simulation", response_model=None)
async def get_recurring_simulation(
    session: Annotated[AsyncSession, Depends(get_session)],
    market: Annotated[str, Query()],
    symbol: Annotated[str, Query()],
    start: Annotated[dt.date, Query()],
    amount: Annotated[str, Query(description="한 번 납입액(원금 통화). 문자열")],
    principal_currency: Annotated[str, Query(alias="principalCurrency")],
    frequency: Annotated[str, Query(description="daily · weekly · monthly · yearly")],
    reinvest: Annotated[bool, Query()] = True,
    end: Annotated[dt.date | None, Query()] = None,
    before: Annotated[dt.date | None, Query(description="이 날짜 미만만 반환")] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 30,
) -> Json | JSONResponse:
    """적립식을 실행하고 표 한 쪽을 돌려준다."""
    prepared = await _prepare_or_collect(
        session, market=market, symbol=symbol, start=start, amount_raw=amount,
        principal_currency=principal_currency, frequency_raw=frequency, reinvest=reinvest, end=end)
    if isinstance(prepared, JSONResponse):
        return prepared
    stock, result = prepared.stock, prepared.result
    rows, has_more = page(result.views, before, limit)
    return {
        "stock": {"market": stock.market, "symbol": stock.symbol, "name": stock.name,
                  "currency": stock.currency},
        "condition": {
            "mode": "recurring", "start": start.isoformat(), "amount": dec(parse_amount(amount)),
            "principalCurrency": principal_currency, "frequency": parse_frequency(frequency),
            "reinvest": reinvest, "tradeFeeRate": dec(prepared.settings.trade_fee_rate),
            "dividendTaxRate": dec(prepared.dividend_tax_rate),
        },
        "summary": summary_json(result, amount=parse_amount(amount), stock=stock),
        "rows": [row_json(v) for v in rows],
        "hasMore": has_more,
        "oldestReturned": rows[-1].row.date.isoformat() if rows else None,
    }


@router.get("/recurring-simulation/series", response_model=None)
async def get_recurring_series(
    session: Annotated[AsyncSession, Depends(get_session)],
    market: Annotated[str, Query()],
    symbol: Annotated[str, Query()],
    start: Annotated[dt.date, Query()],
    amount: Annotated[str, Query()],
    principal_currency: Annotated[str, Query(alias="principalCurrency")],
    frequency: Annotated[str, Query()],
    reinvest: Annotated[bool, Query()] = True,
    end: Annotated[dt.date | None, Query()] = None,
    max_points: Annotated[int, Query(alias="maxPoints", ge=2)] = DEFAULT_MAX_POINTS,
) -> Json | JSONResponse:
    """표와 같은 조건으로 전 구간 시계열을 돌려준다."""
    prepared = await _prepare_or_collect(
        session, market=market, symbol=symbol, start=start, amount_raw=amount,
        principal_currency=principal_currency, frequency_raw=frequency, reinvest=reinvest, end=end)
    if isinstance(prepared, JSONResponse):
        return prepared
    stock = prepared.stock
    finish = end or (dt.date.today() - dt.timedelta(days=1))
    covered = await get_coverage(session, int(stock.id))
    series = build_stock_series(prepared.result, start=start, end=finish, covered=covered,
                                max_points=max_points)
    return {
        "from": series.start.isoformat(),
        "to": series.end.isoformat(),
        "principalCurrency": principal_currency,
        "basisCurrency": "KRW",
        "priceKind": "stock_adjusted_close",
        "priceCurrency": stock.currency,
        "downsampled": series.downsampled,
        "algorithm": "lttb",
        "sourcePointCount": series.source_point_count,
        "points": [
            {"date": p.date.isoformat(), "balance": dec(p.balance),
             "returnRate": dec(p.return_rate), "principal": dec(p.principal),
             "price": dec(p.price)}
            for p in series.points],
        "gaps": [{"from": g.start.isoformat(), "to": g.end.isoformat(), "reason": g.reason}
                 for g in series.gaps],
    }
