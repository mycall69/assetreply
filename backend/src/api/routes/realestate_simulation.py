"""부동산 시뮬레이션 (009 T038, FR-005~FR-007, FR-011, FR-025~FR-030, contracts/rest-api
`GET /api/realestate/simulation`).

받아 둔 시·군·구가 아니면 202 — 화면은 진행을 보이고 끝나면 다시 요청한다. 계산은 순수 함수가 하고
결과는 저장하지 않는다.
"""

from __future__ import annotations

import datetime as dt
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.services.realestate_lists import get_realestate_now, get_realestate_settings
from src.api.services.realestate_simulation import parse_query, simulation_response
from src.config.settings import Settings
from src.db.session import get_session
from src.worker.apt_trade_runner import kst_date

router = APIRouter(prefix="/api/realestate", tags=["realestate"])


@router.get("/simulation")
async def get_simulation(
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_realestate_settings)],
    now: Annotated[dt.datetime, Depends(get_realestate_now)],
    complex_id: Annotated[str, Query(alias="complexId")],
    area: Annotated[str, Query()],
    buy_date: Annotated[str, Query(alias="buyDate")],
    buy_price: Annotated[str | None, Query(alias="buyPrice")] = None,
    principal_currency: Annotated[str | None, Query(alias="principalCurrency")] = None,
) -> JSONResponse:
    query = parse_query(complex_id, area, buy_date, buy_price, principal_currency,
                        today=kst_date(now))
    status, body = await simulation_response(session, query, settings=settings, now=now)
    return JSONResponse(status_code=status, content=body)
