"""`GET /api/fx/rates/{currency}` (T053).

contracts/rest-api.md의 응답 규약을 따른다. 금액은 **문자열**로 직렬화한다 — JSON
`number`는 IEEE 754 배정밀도라 `Decimal` 정밀도가 클라이언트에서 손실되며, 이는 헌법
원칙 VI를 API 경계에서 무력화한다.

`progressUrl`은 User Story 4에서 SSE 엔드포인트가 생긴 뒤에 포함한다
(contracts/rest-api.md 단계 조건).
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
from src.api.services.rate_query import RateResult, query_rate
from src.api.services.series_query import missing_days
from src.config.settings import load_settings
from src.db.session import get_session

router = APIRouter(prefix="/api/fx", tags=["fx"])

SUPPORTED = frozenset({"USD", "JPY", "EUR"})

# JSON 직렬화 형태 — 값 타입이 섞여 object로 받는다
Json = dict[str, object]


def _serialize(result: RateResult) -> Json:
    if result.status == "quoted":
        assert result.base_rate is not None
        assert result.derived is not None
        assert result.applied_spread is not None
        d, sp = result.derived, result.applied_spread
        return {
            "status": "quoted",
            "currency": result.currency,
            "date": result.date.isoformat(),
            "quoteUnit": result.quote_unit,
            "baseRate": str(result.base_rate),
            "derived": {
                "cashBuy": str(d.cash_buy),
                "cashSell": str(d.cash_sell),
                "remitSend": str(d.remit_send),
                "remitReceive": str(d.remit_receive),
            },
            "appliedSpread": {
                "cashBuy": str(sp.cash_buy),
                "cashSell": str(sp.cash_sell),
                "remitSend": str(sp.remit_send),
                "remitReceive": str(sp.remit_receive),
            },
            "spreadBasis": result.spread_basis,
            "source": result.source,
        }

    reference: Json | None = None
    if result.reference is not None:
        reference = {
            "kind": result.reference.kind,
            "date": result.reference.quote_date.isoformat(),
            "quoteUnit": result.reference.quote_unit,
            "baseRate": str(result.reference.base_rate),
            "note": result.reference.note,
        }
    return {
        "status": "no_quote",
        "currency": result.currency,
        "date": result.date.isoformat(),
        "message": result.message,
        "reference": reference,
    }


# 상황에 따라 200(dict) 또는 202(JSONResponse)를 반환하므로 응답 모델 추론을 끈다
@router.get("/rates/{currency}", response_model=None)
async def get_rate_endpoint(
    currency: str,
    date: Annotated[dt.date, Query(description="조회 날짜 (YYYY-MM-DD)")],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Json | JSONResponse:
    code = currency.upper()
    if code not in SUPPORTED:
        raise UnknownCurrency(f"지원하지 않는 통화입니다: {currency}")

    settings = load_settings()
    missing = await missing_days(session, code, date, date)
    if decide_collection(
        missing_days=missing,
        threshold_days=settings.collection_sync_threshold_days,
    ) is CollectionDecision.BACKGROUND:
        job_id = await ensure_background_job(
            session, code, dt.date.today() - dt.timedelta(days=1),
            chunk_days=settings.ecos_chunk_days)
        return JSONResponse(status_code=202, content={
            "status": "collecting",
            "currency": code,
            "date": date.isoformat(),
            "jobId": job_id,
            "missingDays": missing,
            "progressUrl": f"/api/fx/progress?jobId={job_id}",
        })

    return _serialize(await query_rate(session, code, date))
