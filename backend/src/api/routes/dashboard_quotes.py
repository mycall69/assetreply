"""`GET /api/dashboard/quotes` (014 T035) — FR-003~FR-009, contracts A1.

지표 15개의 현재 시세. 출처가 실패해도 **200**이다 — 실패는 지표마다 싣는다(FR-009). 같은 순간의
요청은 서버 캐시를 함께 쓴다
(`api/services/market_quotes` — 단일 비행).
"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from src.api.services import market_quotes

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

Json = dict[str, object]


@router.get("/quotes", response_model=None)
async def get_quotes() -> Json | JSONResponse:
    service = market_quotes.get_shared_service()
    if service is None:
        return JSONResponse(
            status_code=503,
            content={
                "status": "not_ready",
                "message": "대시보드 시세 서비스가 준비되지 않았습니다.",
            },
        )
    return await service.quotes_body()
