"""`POST /api/fx/collect` · `GET /api/fx/progress` (T097).

contracts/rest-api.md — `joinedExisting`은 이미 진행 중인 작업이 있어 새 작업을 만들지
않고 합류했음을 뜻한다 (FR-015b).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Body, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.errors import CollectionInProgress, UnknownCurrency
from src.api.progress import sse_body
from src.config.settings import SUPPORTED_CURRENCIES as SUPPORTED
from src.db.session import get_session
from src.worker.queue import get_queue

router = APIRouter(prefix="/api/fx", tags=["fx"])

Json = dict[str, object]


@router.post("/collect", status_code=202)
async def start_collection(
    session: Annotated[AsyncSession, Depends(get_session)],
    payload: Annotated[dict[str, str] | None, Body()] = None,
) -> Json:
    """수집을 시작한다. 이미 진행 중인 통화는 그 작업에 합류한다."""
    requested = (payload or {}).get("currency")
    if requested is not None and requested.upper() not in SUPPORTED:
        raise UnknownCurrency(f"지원하지 않는 통화입니다: {requested}")
    codes = [requested.upper()] if requested else list(SUPPORTED)

    queue = get_queue()
    jobs: list[Json] = []

    for code in codes:
        # 큐가 받아들이면 워커가 꺼내 실제로 수집을 돈다 (FR-001, T025).
        # 001에서는 이 호출이 없어 작업이 진행 중으로 박힌 채 멈췄다.
        accepted = await queue.request(code)
        if not accepted:
            busy = queue.in_progress
            if busy == code:
                # 같은 통화의 중복 요청은 진행 중인 작업에 합류한다 (FR-003).
                jobs.append({"currency": code, "joinedExisting": True})
                continue
            # 다른 통화가 돌고 있다. 조용히 무시하지 않고 이름을 대어 거절한다
            # (FR-029) — 버튼만 반응이 없으면 사용자는 고장으로 여긴다.
            raise CollectionInProgress(
                f"{busy} 수집이 진행 중입니다. 끝나면 {code}를 시작할 수 있습니다.")
        jobs.append({"currency": code, "joinedExisting": False})

    return {"jobs": jobs}


@router.get("/progress")
async def progress_endpoint(
    session: Annotated[AsyncSession, Depends(get_session)],
    job_id: Annotated[int, Query(alias="jobId")],
) -> StreamingResponse:
    """진행률 SSE 스트림 (contracts/sse-progress.md)."""
    return StreamingResponse(
        sse_body(session, job_id=job_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
