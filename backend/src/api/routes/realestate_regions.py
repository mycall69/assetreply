"""행정구역 (009 T025, FR-002, FR-015, contracts/rest-api `GET /api/realestate/regions`).

받은 적 없으면 202 — 목록 줄이 받고 화면은 진행을 보인 뒤 다시 요청한다. 현존 코드만, 이름순이다.
"""

from __future__ import annotations

import datetime as dt
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.services.realestate_lists import (
    get_realestate_now,
    get_realestate_settings,
    regions_response,
)
from src.config.settings import Settings
from src.db.session import get_session

router = APIRouter(prefix="/api/realestate", tags=["realestate"])


@router.get("/regions")
async def get_regions(
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_realestate_settings)],
    now: Annotated[dt.datetime, Depends(get_realestate_now)],
    parent: Annotated[str | None, Query()] = None,
) -> JSONResponse:
    """시·도(상위 없음) → 시·군·구(시·도 코드) → 법정동(시·군·구 코드)."""
    status, body = await regions_response(session, parent, settings=settings, now=now)
    return JSONResponse(status_code=status, content=body)
