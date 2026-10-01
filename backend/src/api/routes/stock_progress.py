"""주식 수집 진행 상태 (T022) — 005 FR-047, contracts/rest-api.

003이 FX에서 만든 스트림과 같은 모양이다. **`error`에서 `close()`하지 않는다** —
`EventSource`의 자동 재연결에 의존하는 것이 SSE를 택한 근거이며, 닫으면 그 동작을
없애게 된다 (003이 001에서 얻은 교훈).

**작업이 끝나면 `completed`를 보내고 끝낸다.** 화면은 그 신호를 받아 시뮬레이션을 다시
요청한다 — 부분 결과를 먼저 보여주지 않는 대신(FR-049) 완료 시점을 알려야 한다.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

# 003이 만든 직렬화를 그대로 쓴다. **값의 개행을 지우는 가드가 거기 있다** —
# `last_error`에 예외 메시지가 그대로 들어가므로 개행이 섞일 수 있고, 섞이면 SSE
# 프레임이 쪼개져 클라이언트가 이벤트를 받지 못한다.
from src.api.collection_stream import format_sse
from src.db.models import JobStatus
from src.db.session import get_session
from src.repository.stock_job import get_job

router = APIRouter(prefix="/api/stocks", tags=["stocks"])

#: 스냅샷 간격. 짧게 잡으면 DB를 자주 때리고, 길게 잡으면 진행이 멈춘 것처럼 보인다.
POLL_SECONDS = 2.0

Json = dict[str, object]


async def stream_body(
    session: AsyncSession, job_id: int, *, max_frames: int = 0
) -> AsyncIterator[str]:
    """작업이 끝날 때까지 진행 상태를 내보낸다.

    `max_frames`가 0보다 크면 그만큼만 내보내고 끝낸다 (테스트용).
    """
    frames = 0
    while True:
        job = await get_job(session, job_id)
        if job is None:
            yield format_sse("failed", {"jobId": job_id, "reason": "알 수 없는 작업"})
            return

        payload: Json = {
            "jobId": job_id,
            "chunksDone": job.chunks_done,
            "chunksTotal": job.chunks_total,
            "rangeStart": job.range_start.isoformat(),
            "rangeEnd": job.range_end.isoformat(),
        }
        yield format_sse("snapshot", payload)

        if job.status is JobStatus.SUCCEEDED:
            yield format_sse("completed", {"jobId": job_id})
            return
        if job.status in (JobStatus.FAILED, JobStatus.PARTIAL):
            yield format_sse("failed", {
                "jobId": job_id, "reason": job.last_error or "수집에 실패했습니다."})
            return

        frames += 1
        if max_frames and frames >= max_frames:
            return
        await asyncio.sleep(POLL_SECONDS)


@router.get("/progress")
async def get_progress(
    session: Annotated[AsyncSession, Depends(get_session)],
    job_id: Annotated[int, Query(alias="jobId")],
) -> StreamingResponse:
    """수집 진행 스트림 (FR-047)."""
    return StreamingResponse(
        stream_body(session, job_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
