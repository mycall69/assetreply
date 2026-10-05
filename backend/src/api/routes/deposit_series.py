"""예금 차트 시계열 (T029) — 008 FR-036, contracts/rest-api `GET /api/deposit/simulation/series`.

**표와 같은 판정·같은 계산을 거친다**(`simulate_or_collect`) — 수집 판정(202)·오류가 표와 같고, 점의
값은 표의 행·보드와 같다. 주식·가상자산의 시계열 형식에 `provisionalFrom` 하나를 더했다 —
`PerformanceChart`·`ComparisonChart`를 그대로 쓰기 위해서다(research R8-10).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.services import deposit_simulation as service
from src.api.services.deposit_series import SeriesPoint, build_series
from src.api.services.series_query import DEFAULT_MAX_POINTS
from src.db.session import get_session
from src.repository.deposit_rate import rate_text

router = APIRouter(prefix="/api/deposit", tags=["deposit"])


Json = dict[str, object]


def point_json(p: SeriesPoint) -> Json:
    """금액·비율은 문자열이다(헌법 원칙 VI). 표의 `balance`·`returnRate`·`rate`와 같은 서식이다.
    금리가 없는 점은 `null`과 사유(010 FR-011) — 값이 있으면 사유 키를 두지 않는다."""
    body: Json = {"date": p.date.isoformat(), "balance": format(p.balance, "f"),
                  "returnRate": format(p.return_rate, "f"),
                  "price": None if p.price is None else rate_text(p.price)}
    if p.price_missing is not None:
        body["priceMissing"] = p.price_missing
    return body


@router.get("/simulation/series", response_model=None)
async def get_simulation_series(
    session: Annotated[AsyncSession, Depends(get_session)],
    institution: Annotated[str, Query()],
    start: Annotated[str, Query(description="YYYY-MM-DD")],
    principal: Annotated[str, Query(description="원 단위 정수 문자열")],
    principal_currency: Annotated[str | None, Query(alias="principalCurrency")] = None,
    end: Annotated[str | None, Query(description="기본 오늘(한국 시간)")] = None,
    max_points: Annotated[int, Query(alias="maxPoints", ge=2)] = DEFAULT_MAX_POINTS,
) -> Json | JSONResponse:
    """표와 같은 조건으로 행 날짜와 계산 끝의 시계열을 돌려준다."""
    request = service.read_request(institution, start, principal, principal_currency, end)
    result = await service.simulate_or_collect(session, request)
    if not isinstance(result, service.Prepared):
        return JSONResponse(status_code=202, content=result)
    series = build_series(result.outcome, start=request.start, rates=result.rates,
                          latest_month=result.latest_month, max_points=max_points)
    return {
        "from": series.start.isoformat(),
        "to": series.end.isoformat(),
        "principalCurrency": "KRW",
        "basisCurrency": "KRW",
        # 010 — 가격은 그 달 발표 금리(연 %). 통화가 아니라 단위라 `priceCurrency`는 비운다.
        "priceKind": "deposit_rate",
        "priceCurrency": None,
        "downsampled": series.downsampled,
        "algorithm": "lttb",
        "sourcePointCount": series.source_point_count,
        # 금액·비율은 문자열이다(헌법 원칙 VI). 표의 `balance`·`returnRate`와 같은 서식이다.
        "points": [point_json(p) for p in series.points],
        "gaps": [],
        "provisionalFrom": (None if series.provisional_from is None
                            else series.provisional_from.isoformat()),
    }
