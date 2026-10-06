"""단지·평형 (009 T025, FR-003~FR-005, FR-011, FR-015, contracts/rest-api).

- `GET /api/realestate/complexes?umd=` — 단지 목록(곧바로), 기본 정보·실거래 진행
- `GET /api/realestate/complexes/{complexId}/areas` — 평형 일곱 구분. 실거래를 다 받기 전에는 202
- `GET /api/realestate/complexes/{complexId}/naver` — Npay 부동산 단지 화면 주소(010 반복 3,
  FR-029). 단지 하나에
  한 번 찾아 저장한다 — 공개되지 않은 단지 자동완성(헌법 원칙 II 이탈)
"""

from __future__ import annotations

import datetime as dt
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.services.apt_naver_link import ComplexSearch, get_naver_land_client, naver_link
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


@router.get("/complexes/{complex_id}/naver")
async def get_naver_link(
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_realestate_settings)],
    now: Annotated[dt.datetime, Depends(get_realestate_now)],
    client: Annotated[ComplexSearch, Depends(get_naver_land_client)],
    complex_id: int,
) -> JSONResponse:
    body = await naver_link(session, complex_id, client=client, settings=settings, now=now)
    return JSONResponse(status_code=200, content=body)

