"""`GET /api/dashboard/news/{source}` (014 T077) — FR-020, FR-023, FR-024, contracts A5.

칸 셋(`kr`·`us`·`jp`)의 뉴스 목록. 출처가 실패해도 **200**이다 — 칸마다 따로 실패한다(FR-024). 틀린
칸은 404다.
화면은 셋을 동시에 부르고 온 것부터 그린다 — 가장 느린 출처가 다른 칸·카드를 막지 않는다. 강제로
다시 받는 질의는
없다(성공 캐시 안의 재요청은 늘 캐시다 — US3 시나리오 6).
"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from src.api.services import news_cache
from src.ingestion.news.types import SOURCES, SourceKey

router = APIRouter(prefix="/api/dashboard/news", tags=["dashboard"])

Json = dict[str, object]


@router.get("/{source}", response_model=None)
async def get_news(source: str) -> Json | JSONResponse:
    key: SourceKey | None = next((s for s in SOURCES if s == source), None)
    if key is None:
        return JSONResponse(
            status_code=404,
            content={"status": "unknown_source", "message": f"없는 뉴스 칸입니다: {source}"},
        )
    cache = news_cache.get_shared_service()
    if cache is None:
        return JSONResponse(
            status_code=503,
            content={
                "status": "not_ready",
                "message": "대시보드 뉴스 서비스가 준비되지 않았습니다.",
            },
        )
    return await cache.body(key)
