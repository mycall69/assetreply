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

from src.api.errors import InvalidQuery, UnknownCurrency
from src.api.services.collection_gate import (
    CollectionDecision,
    decide_collection,
    ensure_background_job,
)
from src.api.services.daily_query import PeriodRow, daily_page, derive_for_row
from src.api.services.period_rows import PERIOD_UNITS, PeriodUnit
from src.api.services.series_query import missing_days
from src.config.settings import SUPPORTED_CURRENCIES as SUPPORTED
from src.config.settings import load_settings
from src.db.session import get_session
from src.simulation.fx_change import RateChange
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
    period: Annotated[str, Query(description="daily · weekly · monthly")] = "daily",
    before: Annotated[dt.date | None, Query(description="이 날짜 미만만 반환")] = None,
    limit: Annotated[int | None, Query(ge=1, le=200)] = None,
) -> Json | JSONResponse:
    code = currency.upper()
    if code not in SUPPORTED:
        raise UnknownCurrency(f"지원하지 않는 통화입니다: {currency}")

    # 알 수 없는 값을 **조용히 `daily`로 떨어뜨리지 않는다.** 화면이 잘못된 값을 보냈는데
    # 정상 응답이 오면 그 버그가 드러나지 않는다 (contracts/rest-api).
    if period not in PERIOD_UNITS:
        raise InvalidQuery(
            f"period는 {' · '.join(PERIOD_UNITS)} 중 하나여야 합니다: {period}")
    unit: PeriodUnit = period  # type: ignore[assignment]

    settings = load_settings()
    page_size = limit if limit is not None else settings.daily_page_size

    yesterday = dt.date.today() - dt.timedelta(days=1)
    missing = await missing_days(session, code, yesterday, yesterday)
    if decide_collection(
        missing_days=missing,
        threshold_days=settings.collection_sync_threshold_days,
    ) is CollectionDecision.BACKGROUND:
        # 006 FR-046a — 수집 표를 싣는다. `jobId`는 실행 중일 때만 있다.
        ticket = await ensure_background_job(session, code)
        return JSONResponse(status_code=202, content={
            "status": "collecting",
            "currency": code,
            "missingDays": missing,
            **ticket.as_json(),
        })

    page = await daily_page(
        session, code, before=before, limit=page_size, unit=unit)

    return {
        "currency": code,
        "period": page.unit,
        "quoteUnit": page.rows[0].rate.quote_unit if page.rows else 1,
        "appliedSpread": _spread_json(page.spread),
        # 파생값은 "현재 스프레드를 과거에 적용한 가정"이다. 화면이 이를 밝혀야 한다(FR-024).
        "spreadBasis": "current",
        "rows": [_row_json(r, page.spread) for r in page.rows],
        "hasMore": page.has_more,
        "oldestReturned": (
            page.oldest_returned.isoformat() if page.oldest_returned else None),
    }


def _row_json(row: PeriodRow, spread: SpreadSet) -> Json:
    """표 한 행. **세 사실을 각각 따로 싣는다** (FR-015b).

    `shiftedFrom`은 **옮겨졌을 때만 키를 넣는다**(FR-014). 정상 상태에 값을 두면 화면이
    존재 여부가 아니라 내용을 검사해야 한다 — 002·003이 세운 규약이다.

    `isOngoing`은 반대로 항상 명시한다. "확인했고 아니다"와 "확인하지 않았다"가
    구별되어야 하는 값이다.
    """
    body: Json = {
        "date": row.rate.quote_date.isoformat(),
        "baseRate": str(row.rate.base_rate),
        "isProvisional": row.rate.is_provisional,
        "derived": _derived_json(row.rate.base_rate, spread),
        "periodFrom": row.period_from.isoformat(),
        "periodTo": row.period_to.isoformat(),
        "isOngoing": row.is_ongoing,
        # 014 반복 2026-10-10d(FR-031, contracts A9) — 늘 싣는다. 비교할 행이 없으면 `null`
        "change": _change_json(row.change),
    }
    if row.shifted_from is not None:
        body["shiftedFrom"] = row.shifted_from.isoformat()
    return body


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


def _change_json(change: RateChange | None) -> dict[str, str | None] | None:
    """행의 등락 — `/api/fx/latest`의 `change`와 같은 꼴이다(014 반복 2026-10-10d).

    요약 칸과 달리 비율이 없으면 `null`이다(화면 "—") — 0을 지어내지 않는다(헌법 원칙 V).
    """
    if change is None:
        return None
    return {
        "comparedTo": change.compared_to.isoformat(),
        "absolute": str(change.absolute),
        "percent": None if change.percent is None else str(change.percent),
        "direction": change.direction,
    }
