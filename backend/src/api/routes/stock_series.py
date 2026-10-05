"""차트용 시계열 (T083) — 005 contracts/rest-api, FR-033, FR-034, SC-032.

**표와 같은 순수 함수를 같은 입력으로 부른다.** `stock_simulation` 서비스의
`prepare`를 거치므로 다른 계산 경로가 생길 수 없다 — 경로가 갈리면 표의 마지막 행과
차트의 끝점이 어긋나는데 양쪽 다 그럴듯한 숫자라 알아챌 신호가 없다 (SC-032).

**표 응답에 싣지 않고 따로 둔다.** 표에 실으면 페이지를 넘길 때마다 같은 시계열이
재전송된다. 60년치면 표 행이 960개다.
"""

from __future__ import annotations

import datetime as dt
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.services.series_query import DEFAULT_MAX_POINTS
from src.api.services.stock_collect import collecting_body
from src.api.services.stock_series import build_series
from src.api.services.stock_simulation import (
    check_principal_currency,
    parse_principal,
    prepare,
    require_start_available,
    require_stock,
)
from src.db.session import get_session
from src.repository.stock import get_coverage

router = APIRouter(prefix="/api/stocks", tags=["stocks"])

Json = dict[str, object]


@router.get("/simulation/series", response_model=None)
async def get_simulation_series(
    session: Annotated[AsyncSession, Depends(get_session)],
    market: Annotated[str, Query()],
    symbol: Annotated[str, Query()],
    start: Annotated[dt.date, Query()],
    principal: Annotated[str, Query(description="투자 원금. 문자열")],
    principal_currency: Annotated[str, Query(alias="principalCurrency")],
    reinvest: Annotated[bool, Query()] = True,
    end: Annotated[dt.date | None, Query()] = None,
    max_points: Annotated[int, Query(alias="maxPoints", ge=2)] = DEFAULT_MAX_POINTS,
) -> Json | JSONResponse:
    """표와 같은 조건으로 전 구간 시계열을 돌려준다."""
    check_principal_currency(principal_currency)
    amount = parse_principal(principal)

    # 끝은 기본적으로 어제다. 표와 같은 기준이어야 끝점이 맞는다.
    finish = end or (dt.date.today() - dt.timedelta(days=1))

    # 표와 **같은 판정**을 쓴다. 한쪽만 막으면 한쪽은 비어 있고 한쪽은 받은 만큼만
    # 계산한 틀린 값을 보여준다 (FR-049).
    stock = await require_stock(session, market, symbol)
    # 006 FR-050 — 막힌 조합이면 수집도 계산도 하지 않는다. 수집보다 먼저 본다.
    check_principal_currency(principal_currency, stock.currency)
    # 상장 이전 판정이 **수집보다 먼저다.** 뒤로 미루면 상장 수십 년 전부터의
    # 구간이 미수집으로 보여 수집이 시작되고, 받을 수 없는 데이터를 기다리게 된다.
    await require_start_available(session, stock, start)
    # 006 — 주식 시세와 환율을 **함께** 본다. 둘 중 하나라도 비면 202다 (FR-045).
    collecting = await collecting_body(session, stock, start=start, end=finish)
    if collecting is not None:
        return JSONResponse(status_code=202, content=collecting)

    prepared = await prepare(
        session, market=market, symbol=symbol, start=start, end=finish,
        principal=amount, principal_currency=principal_currency,
        reinvest=reinvest)

    covered = await get_coverage(session, int(stock.id))
    series = build_series(
        prepared.result, start=start, end=finish, covered=covered,
        max_points=max_points)

    return {
        "from": series.start.isoformat(),
        "to": series.end.isoformat(),
        # FR-041 — 기준 통화를 밝히지 않으면 사용자가 어느 쪽을 보는지 모른다. 006 FR-068 — 기준은
        # 원금 통화와 관계없이 KRW다. 원금 통화는 입력 그대로 따로 싣는다 — 범례·비교가 원금 통화로
        # 기준을 말하면 달러 원금 실행의 KRW 값을 달러로 읽는다.
        "principalCurrency": principal_currency,
        "basisCurrency": "KRW",
        # 010 — 가격은 원주가 시가, 통화는 **종목 통화**다(원금이 KRW여도 환산하지 않는다 — 표의
        # 시작가와 같은 값).
        "priceKind": "stock_open",
        "priceCurrency": stock.currency,
        "downsampled": series.downsampled,
        "algorithm": "lttb",
        "sourcePointCount": series.source_point_count,
        # 금액·비율은 **문자열**이다. JSON number는 IEEE 754라 경계에서 정밀도가
        # 무너지고, 그것은 헌법 원칙 VI를 API 경계에서 무력화하는 일이다.
        "points": [
            {"date": p.date.isoformat(), "balance": str(p.balance),
             "returnRate": str(p.return_rate), "price": str(p.price)}
            for p in series.points],
        "gaps": [
            {"from": g.start.isoformat(), "to": g.end.isoformat(),
             "reason": g.reason}
            for g in series.gaps],
        # 010 FR-008 — 원주가 선이 꺾이는 까닭. 표식 자리(효력일 뒤 첫 점)는 그린 점을 아는 화면이
        # 정한다.
        "splits": [
            {"date": s.date.isoformat(), "numerator": s.numerator,
             "denominator": s.denominator}
            for s in series.splits],
    }
