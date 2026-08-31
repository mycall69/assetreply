"""`POST /api/fx/today/refresh` (T068).

FR-036a: 대량 수집과 독립적으로 동작한다. 수집 중이라는 이유로 거부하지 않는다.
FR-039: 오늘 고시가 없으면 값을 만들어내지 않는다.
FR-040: 실패해도 저장된 과거 데이터는 유효하다 — 오류 매핑은 001의 규약을 따른다.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Body, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.errors import UnknownCurrency
from src.api.services.today_refresh import refresh_today
from src.config.settings import SUPPORTED_CURRENCIES as SUPPORTED
from src.config.settings import load_settings
from src.db.session import get_session
from src.ingestion.ecos.client import EcosClient

router = APIRouter(prefix="/api/fx", tags=["fx"])

Json = dict[str, object]


@router.post("/today/refresh")
async def refresh_today_endpoint(
    session: Annotated[AsyncSession, Depends(get_session)],
    payload: Annotated[dict[str, str] | None, Body()] = None,
) -> Json:
    requested = (payload or {}).get("currency")
    if requested is None or requested.upper() not in SUPPORTED:
        raise UnknownCurrency(f"지원하지 않는 통화입니다: {requested}")
    code = requested.upper()

    settings = load_settings()
    async with EcosClient(settings) as client:
        result = await refresh_today(session, client, code)

    body: Json = {
        "currency": result.currency,
        "status": result.status,
        "date": result.date.isoformat(),
        "fetchedAt": result.fetched_at.isoformat(),
        "joinedExisting": result.joined_existing,
    }
    if result.base_rate is not None:
        body["baseRate"] = str(result.base_rate)
        body["isProvisional"] = True
    else:
        body["message"] = "오늘은 아직 고시가 없습니다."
    return body
