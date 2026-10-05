"""단지·평형 (009 T025, FR-003~FR-005, FR-011, FR-015, contracts/rest-api).

- `GET /api/realestate/complexes?umd=` — 단지 목록(곧바로), 기본 정보·실거래 진행
- `GET /api/realestate/complexes/{complexId}/areas` — 평형 일곱 구분. 실거래를 다 받기 전에는 202
"""

from __future__ import annotations

import datetime as dt
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.services.realestate_lists import (
    areas_response,
    complexes_response,
    get_realestate_now,
    get_realestate_settings,
    get_realestate_source,
)
from src.config.settings import Settings
from src.db.session import get_session
from src.worker.apt_list_runner import ComplexListSource

router = APIRouter(prefix="/api/realestate", tags=["realestate"])


@router.get("/complexes")
async def get_complexes(
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_realestate_settings)],
    now: Annotated[dt.datetime, Depends(get_realestate_now)],
    source: Annotated[ComplexListSource, Depends(get_realestate_source)],
    umd: Annotated[str, Query()],
) -> JSONResponse:
    body = await complexes_response(session, source, umd, settings=settings, now=now)
    return JSONResponse(status_code=200, content=body)


@router.get("/complexes/{complex_id}/areas")
async def get_areas(
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_realestate_settings)],
    now: Annotated[dt.datetime, Depends(get_realestate_now)],
    complex_id: int,
) -> JSONResponse:
    status, body = await areas_response(session, complex_id, settings=settings, now=now)
    return JSONResponse(status_code=status, content=body)
