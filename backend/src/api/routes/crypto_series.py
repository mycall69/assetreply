"""가상자산 차트 시계열 (T041) — 007 FR-043, FR-044, contracts/rest-api `GET
/api/crypto/simulation/series`.

**표와 같은 판정·같은 계산을 거친다.** 수집 판정(202)·오류·원금 통화 조합이 표와 같고, 계산은 표가
쓰는 `prepare`다 — 경로가 갈리면 표의 행과 차트의 점이 어긋나는데 양쪽 다 그럴듯한 숫자라 알아챌
신호가 없다(005 SC-032와 같은 이유). 표 응답에 싣지 않고 따로 둔다 — 표를 이어 볼 때마다 같은
시계열이 다시 오지 않게 한다.
"""

from __future__ import annotations

import datetime as dt
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.errors import StartAfterEnd
from src.api.routes.crypto_simulation import calculation_end
from src.api.services.crypto_collect import collecting_body
from src.api.services.crypto_series import CryptoSeries, build_series
from src.api.services.crypto_simulation import (
    check_principal_currency,
    prepare,
    require_coin,
    require_start_available,
)
from src.api.services.series_query import DEFAULT_MAX_POINTS
from src.api.services.stock_simulation import parse_principal
from src.config.settings import load_settings
from src.db.session import get_session
from src.repository import crypto_daily

router = APIRouter(prefix="/api/crypto", tags=["crypto"])

Json = dict[str, object]


def series_json(series: CryptoSeries, *, principal_currency: str, price_currency: str) -> Json:
    """시계열 본문 — 비교 경로(013)도 이 함수로 같은 모양을 낸다."""
    return {
        "from": series.start.isoformat(),
        "to": series.end.isoformat(),
        # 원금 통화는 입력 그대로, 기준은 KRW다(FR-044, 006 FR-068).
        "principalCurrency": principal_currency,
        "basisCurrency": "KRW",
        # 010 — 가격은 그 일봉의 시가, 통화는 코인의 **시세 통화**다(원금이 KRW여도 환산하지
        # 않는다).
        "priceKind": "crypto_open",
        "priceCurrency": price_currency,
        "downsampled": series.downsampled,
        "algorithm": "lttb",
        "sourcePointCount": series.source_point_count,
        # 금액·비율은 문자열이다(헌법 원칙 VI). 표의 `balanceKrw`·`returnRate`·`openPrice`와 같은
        # 서식이다.
        "points": [{"date": p.date.isoformat(), "balance": format(p.balance, "f"),
                    "returnRate": format(p.return_rate, "f"), "price": format(p.price, "f")}
                   for p in series.points],
        # `source_missing` — 받은 구간 안의 출처 결측. 끊어 그린다(FR-023)
        "gaps": [{"from": g.start.isoformat(), "to": g.end.isoformat(), "reason": g.reason}
                 for g in series.gaps],
    }


@router.get("/simulation/series", response_model=None)
async def get_simulation_series(
    session: Annotated[AsyncSession, Depends(get_session)],
    coin_id: Annotated[int, Query(alias="coinId")],
    start: Annotated[dt.date, Query()],
    principal: Annotated[str, Query(description="투자 원금. 문자열")],
    principal_currency: Annotated[str, Query(alias="principalCurrency")],
    end: Annotated[dt.date | None, Query()] = None,
    max_points: Annotated[int, Query(alias="maxPoints", ge=2)] = DEFAULT_MAX_POINTS,
) -> Json | JSONResponse:
    """표와 같은 조건으로 일봉마다의 시계열을 돌려준다."""
    amount = parse_principal(principal)
    finish = calculation_end(end)
    if start > finish:
        raise StartAfterEnd(finish)
    coin = await require_coin(session, coin_id)
    check_principal_currency(principal_currency, coin.quote_currency)
    require_start_available(coin, start)
    collecting = await collecting_body(
        session, coin, start=start, end=finish, settings=load_settings())
    if collecting is not None:
        return JSONResponse(status_code=202, content=collecting)

    prepared = await prepare(session, coin, start=start, end=finish, principal=amount,
                             principal_currency=principal_currency, daily=True)
    series = build_series(prepared.result, start=start, end=finish,
                          covered=await crypto_daily.get_coverage(session, int(coin.id)),
                          max_points=max_points)
    return series_json(series, principal_currency=principal_currency,
                       price_currency=coin.quote_currency)
