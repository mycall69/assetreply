"""부동산 차트 시계열 (009 T047, FR-031, contracts/rest-api `GET
/api/realestate/simulation/series`).

시뮬레이션과 같은 질의·같은 202·같은 오류다. 표와 같은 계산을 차트 모양으로 바꾼다.
"""

from __future__ import annotations

import datetime as dt
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.services.realestate_lists import get_realestate_now, get_realestate_settings
from src.api.services.realestate_series import RealEstateSeries, SeriesPoint, build_series
from src.api.services.realestate_simulation import Prepared, parse_query, prepare
from src.api.services.series_query import DEFAULT_MAX_POINTS
from src.config.settings import Settings
from src.db.session import get_session
from src.worker.apt_trade_runner import kst_date

router = APIRouter(prefix="/api/realestate", tags=["realestate"])

Json = dict[str, object]


def point_json(p: SeriesPoint) -> Json:
    """금액·비율은 문자열이다(헌법 원칙 VI). 표의 `value`·`returnRate`·`monthAverage`와 같은
    서식이다. 실거래가 평균이 없는 달은 `null`과 사유(010 FR-011) — 값이 있으면 사유 키를 두지
    않는다."""
    body: Json = {"date": p.date.isoformat(), "balance": str(p.balance),
                  "returnRate": format(p.return_rate, ".6f"), "estimated": p.estimated,
                  "provisional": p.provisional, "profit": str(p.profit),
                  "price": None if p.price is None else str(p.price)}
    if p.price_missing is not None:
        body["priceMissing"] = p.price_missing
    return body


def series_json(series: RealEstateSeries, *, provisional_from: dt.date) -> Json:
    """시계열 본문 — 비교 경로(013)도 이 함수로 같은 모양을 낸다."""
    return {
        "from": series.start.isoformat(), "to": series.end.isoformat(),
        "principalCurrency": "KRW", "basisCurrency": "KRW",
        # 010 — 가격은 그 달 실거래가 평균(원).
        "priceKind": "apt_average", "priceCurrency": "KRW",
        "downsampled": series.downsampled, "algorithm": "lttb",
        "sourcePointCount": series.source_point_count,
        "points": [point_json(p) for p in series.points],
        "gaps": [{"from": g.start.isoformat(), "to": g.end.isoformat(), "reason": g.reason}
                 for g in series.gaps],
        "provisionalFrom": provisional_from.isoformat(),
    }


@router.get("/simulation/series", response_model=None)
async def get_simulation_series(
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_realestate_settings)],
    now: Annotated[dt.datetime, Depends(get_realestate_now)],
    complex_id: Annotated[str, Query(alias="complexId")],
    area: Annotated[str, Query()],
    buy_date: Annotated[str, Query(alias="buyDate")],
    buy_price: Annotated[str | None, Query(alias="buyPrice")] = None,
    principal_currency: Annotated[str | None, Query(alias="principalCurrency")] = None,
    max_points: Annotated[int, Query(alias="maxPoints", ge=2)] = DEFAULT_MAX_POINTS,
) -> Json | JSONResponse:
    query = parse_query(complex_id, area, buy_date, buy_price, principal_currency,
                        today=kst_date(now))
    prepared = await prepare(session, query, settings=settings, now=now)
    if not isinstance(prepared, Prepared):
        return JSONResponse(status_code=202, content=prepared)
    series = build_series(prepared.result, max_points=max_points)
    return series_json(series, provisional_from=prepared.provisional_from)
