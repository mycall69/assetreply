"""`GET /api/fx/daily` — 일자별 상세 표 (T028).

금액·비율은 모두 **문자열**로 직렬화한다. JSON `number`는 IEEE 754라 `Decimal` 정밀도가
손실되며, 이는 헌법 원칙 VI를 API 경계에서 무력화한다.

FR-021: 고시가 없는 날은 행을 만들지 않는다. 응답의 날짜가 연속하지 않는 것이 정상이다.
FR-048: 미수집 구간이 있으면 001의 자동 수집 규칙을 그대로 적용한다.
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
from src.api.services.daily_query import daily_page, derive_for_row
from src.api.services.series_query import missing_days
from src.config.settings import SUPPORTED_CURRENCIES as SUPPORTED
from src.config.settings import load_settings
from src.db.session import get_session
from src.simulation.spread_calc import SpreadSet

router = APIRouter(prefix="/api/fx", tags=["fx"])

Json = dict[str, object]


def _spread_json(spread: SpreadSet) -> dict[str, str]:
    return {
        "cashBuy": str(spread.cash_buy),
        "cashSell": str(spread.cash_sell),
        "remitSend": str(spread.remit_send),
        "remitReceive": str(spread.remit_receive),
    }


@router.get("/daily", response_model=None)
async def get_daily(
    session: Annotated[AsyncSession, Depends(get_session)],
    currency: Annotated[str, Query(description="통화 코드")],
    before: Annotated[dt.date | None, Query(description="이 날짜 미만만 반환")] = None,
    limit: Annotated[int | None, Query(ge=1, le=200)] = None,
) -> Json | JSONResponse:
    code = currency.upper()
    if code not in SUPPORTED:
        raise UnknownCurrency(f"지원하지 않는 통화입니다: {currency}")

    settings = load_settings()
    page_size = limit if limit is not None else settings.daily_page_size

    yesterday = dt.date.today() - dt.timedelta(days=1)
    missing = await missing_days(session, code, yesterday, yesterday)
    if decide_collection(
        missing_days=missing,
        threshold_days=settings.collection_sync_threshold_days,
    ) is CollectionDecision.BACKGROUND:
        job_id = await ensure_background_job(
            session, code, yesterday, chunk_days=settings.ecos_chunk_days)
        return JSONResponse(status_code=202, content={
            "status": "collecting",
            "currency": code,
            "jobId": job_id,
            "missingDays": missing,
            "progressUrl": f"/api/fx/progress?jobId={job_id}",
        })

    page = await daily_page(session, code, before=before, limit=page_size)

    return {
        "currency": code,
        "quoteUnit": page.rows[0].quote_unit if page.rows else 1,
        "appliedSpread": _spread_json(page.spread),
        # 파생값은 "현재 스프레드를 과거에 적용한 가정"이다. 화면이 이를 밝혀야 한다(FR-024).
        "spreadBasis": "current",
        "rows": [{
            "date": r.quote_date.isoformat(),
            "baseRate": str(r.base_rate),
            "isProvisional": r.is_provisional,
            "derived": _derived_json(r.base_rate, page.spread),
        } for r in page.rows],
        "hasMore": page.has_more,
        "oldestReturned": (
            page.oldest_returned.isoformat() if page.oldest_returned else None),
    }


def _derived_json(base_rate: object, spread: SpreadSet) -> dict[str, str]:
    from decimal import Decimal

    assert isinstance(base_rate, Decimal)
    d = derive_for_row(base_rate, spread)
    return {
        "cashBuy": str(d.cash_buy),
        "cashSell": str(d.cash_sell),
        "remitSend": str(d.remit_send),
        "remitReceive": str(d.remit_receive),
    }
