"""`GET /api/fx/series` (T079, T080).

FR-032a: 차트 요청도 날짜 조회와 동일한 자동 수집 규칙을 적용한다 —
`collection_gate` 모듈을 재사용한다.
"""

from __future__ import annotations

import datetime as dt
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.errors import UnknownCurrency
from src.api.services.collection_gate import (
    CollectionDecision,
    decide_collection,
    ensure_background_job,
)
from src.api.services.series_query import DEFAULT_MAX_POINTS, missing_days, query_series
from src.config.settings import load_settings
from src.db.session import get_session

router = APIRouter(prefix="/api/fx", tags=["fx"])

SUPPORTED = frozenset({"USD", "JPY", "EUR"})

Json = dict[str, object]


# 상황에 따라 200(dict) 또는 202(JSONResponse)를 반환하므로 응답 모델 추론을 끈다
@router.get("/series", response_model=None)
async def get_series_endpoint(
    session: Annotated[AsyncSession, Depends(get_session)],
    currency: Annotated[str, Query()],
    date_from: Annotated[dt.date, Query(alias="from")],
    date_to: Annotated[dt.date, Query(alias="to")],
    max_points: Annotated[int, Query(alias="maxPoints", ge=2)] = DEFAULT_MAX_POINTS,
) -> Json | JSONResponse:
    code = currency.upper()
    if code not in SUPPORTED:
        raise UnknownCurrency(f"지원하지 않는 통화입니다: {currency}")

    settings = load_settings()
    missing = await missing_days(session, code, date_from, date_to)
    decision = decide_collection(
        missing_days=missing,
        threshold_days=settings.collection_sync_threshold_days)

    if decision is CollectionDecision.BACKGROUND:
        job_id = await ensure_background_job(
            session, code, dt.date.today() - dt.timedelta(days=1),
            chunk_days=settings.ecos_chunk_days)
        return JSONResponse(status_code=202, content={
            "status": "collecting",
            "currency": code,
            "from": date_from.isoformat(),
            "to": date_to.isoformat(),
            "missingDays": missing,
            "progressUrl": f"/api/fx/progress?jobId={job_id}",
        })

    result = await query_series(session, code, date_from, date_to, max_points=max_points)
    return {
        "currency": result.currency,
        "quoteUnit": result.quote_unit,
        "from": result.start.isoformat(),
        "to": result.end.isoformat(),
        "downsampled": result.downsampled,
        "algorithm": "lttb",
        "sourcePointCount": result.source_point_count,
        "points": [{"date": p.date.isoformat(), "baseRate": str(p.value)}
                   for p in result.points],
        "gaps": [{"from": g.start.isoformat(), "to": g.end.isoformat(), "reason": g.reason}
                 for g in result.gaps],
    }
