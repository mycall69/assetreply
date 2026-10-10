"""지표 모달의 일자별 표 경로 (014 반복 2026-10-10b T117) — FR-029, contracts A7.

`GET /api/dashboard/indicators/{id}/table?period=daily|weekly|monthly&before=&limit=` — 표(200) 또는
받는 중·실패(202, 그래프와 같은 본문). 틀린 `period`는 400 `invalid_query`(012 `parse_period` — 일
단위로 떨어뜨리지 않는다), 없는 지표는 404다.
"""

from __future__ import annotations

import datetime as dt
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.services import market_quotes
from src.api.services.collection_gate import ensure_background_job
from src.api.services.indicator_table import table_response
from src.api.services.table_rows import parse_period
from src.config.settings import load_settings
from src.db.session import get_session
from src.simulation.market_indicators import get
from src.worker.queue import get_queue

router = APIRouter(prefix="/api/dashboard/indicators", tags=["dashboard"])

Json = dict[str, object]


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


@router.get("/{indicator_id}/table", response_model=None)
async def get_table(
    session: Annotated[AsyncSession, Depends(get_session)],
    indicator_id: str,
    period: Annotated[str | None, Query()] = None,
    before: Annotated[dt.date | None, Query(description="이 날짜 미만만 반환")] = None,
    limit: Annotated[int | None, Query(ge=1, le=200)] = None,
) -> Json | JSONResponse:
    indicator = get(indicator_id)
    if indicator is None:
        return JSONResponse(
            status_code=404,
            content={"status": "unknown_indicator", "message": f"없는 지표입니다: {indicator_id}"},
        )
    unit = parse_period(period)
    settings = load_settings()
    status, body = await table_response(
        session,
        indicator,
        unit,
        before=before,
        limit=limit if limit is not None else settings.dashboard_table_page_limit,
        quotes=market_quotes.get_shared_service(),
        settings=settings,
        now=utc_now(),
        ensure_job=ensure_background_job,
        fx_busy=get_queue().in_progress,
    )
    return body if status == 200 else JSONResponse(status_code=status, content=body)
