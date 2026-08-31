"""`GET /api/fx/latest` — 요약 영역 (T027).

FR-011: 오늘 잠정값이 있으면 그것을, 없으면 마지막 확정값을 제시한다.
FR-013: 변화량을 절대값·백분율과 함께 **방향을 값으로** 내려준다. 색에만 의존하면
색각 이상 사용자가 상승·하락을 구분할 수 없다.
FR-048: 미수집 구간이 있으면 001의 자동 수집 규칙을 그대로 적용한다.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
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
from src.api.services.series_query import missing_days
from src.config.settings import SUPPORTED_CURRENCIES as SUPPORTED
from src.config.settings import load_settings
from src.db.models import FxRate
from src.db.session import get_session
from src.repository.fx_rate import latest as latest_rate
from src.repository.fx_rate import previous_business_day

router = APIRouter(prefix="/api/fx", tags=["fx"])

Json = dict[str, object]

_QUANTUM = Decimal("0.01")


def _change(current: FxRate, previous: FxRate | None) -> Json | None:
    """직전 고시일 대비 변화 (FR-013).

    요약이 잠정값일 때 비교 대상은 직전 **확정값**이다 — 잠정끼리 비교하면 의미가 없다.
    백분율은 표시용이라 소수 둘째 자리까지 반올림하지만, 절대값은 저장 정밀도를 유지한다.
    """
    if previous is None:
        return None
    delta = current.base_rate - previous.base_rate
    percent = (
        (delta / previous.base_rate * Decimal(100)).quantize(_QUANTUM)
        if previous.base_rate
        else Decimal("0")
    )
    direction = "up" if delta > 0 else "down" if delta < 0 else "flat"
    return {
        "comparedTo": previous.quote_date.isoformat(),
        "absolute": str(delta),
        "percent": str(percent),
        "direction": direction,
    }


@router.get("/latest", response_model=None)
async def get_latest(
    session: Annotated[AsyncSession, Depends(get_session)],
    currency: Annotated[str, Query(description="통화 코드")],
) -> Json | JSONResponse:
    code = currency.upper()
    if code not in SUPPORTED:
        raise UnknownCurrency(f"지원하지 않는 통화입니다: {currency}")

    settings = load_settings()
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

    row = await latest_rate(session, code)
    if row is None:
        return {
            "currency": code,
            "status": "no_data",
            "message": "아직 수집된 데이터가 없습니다.",
        }

    # 잠정값의 비교 대상은 직전 확정값이다. 확정값의 비교 대상은 그냥 직전 고시일이다.
    previous = await previous_business_day(
        session, code, row.quote_date, not_before=dt.date.min)

    return {
        "currency": code,
        "quotePair": f"{code}/KRW",
        "date": row.quote_date.isoformat(),
        "baseRate": str(row.base_rate),
        "quoteUnit": row.quote_unit,
        "isProvisional": row.is_provisional,
        # 잠정값일 때만 의미가 있다. 마지막으로 받아온 시각이다 (FR-038).
        "fetchedAt": row.updated_at.isoformat() if row.is_provisional else None,
        "change": _change(row, previous),
    }
