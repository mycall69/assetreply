"""지표 모달의 변화 까닭 경로 (014 반복 2026-10-10b T118) — FR-027, contracts A8.

`GET /api/dashboard/indicators/{id}/commentary` — 출처가 실패해도 200(`status: "failed"`). 없는
지표는 404, 서비스가 없으면(앱 수명 밖) 503이다.
"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from src.api.services import indicator_commentary
from src.simulation.market_indicators import get

router = APIRouter(prefix="/api/dashboard/indicators", tags=["dashboard"])

Json = dict[str, object]


@router.get("/{indicator_id}/commentary", response_model=None)
async def get_commentary(indicator_id: str) -> Json | JSONResponse:
    indicator = get(indicator_id)
    if indicator is None:
        return JSONResponse(
            status_code=404,
            content={"status": "unknown_indicator", "message": f"없는 지표입니다: {indicator_id}"},
        )
    service = indicator_commentary.get_shared_service()
    if service is None:
        return JSONResponse(
            status_code=503,
            content={"status": "unavailable", "message": "변화 까닭 서비스가 없습니다."},
        )
    return await service.body(indicator)
