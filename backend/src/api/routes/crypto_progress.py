"""가상자산 수집 진행 (T032) — 007 FR-013, FR-020, contracts/rest-api `GET /api/crypto/progress`.

006 주식 진행 스트림과 같은 사건·머리글이다. 진행은 **받은 날 / 받을 날**(달력 일수, 006
FR-045a)이고, 실패는 종류(`kind`)를 싣는다 — 화면이 종류마다 다른 말을 한다(FR-020). **프레임마다
읽기 트랜잭션을 끝낸다**(006 R6-19) — 끝내지 않으면 MySQL이 첫 스냅샷을 계속 보여 진행이 멈춘 것처럼
보이고 `completed`가 오지 않는다.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.collection_stream import SSE_HEADERS, format_sse
from src.api.routes.stock_progress import covered_days
from src.db.models import JobStatus
from src.db.session import get_session
from src.repository import crypto_daily, crypto_job

router = APIRouter(prefix="/api/crypto", tags=["crypto"])

#: 스냅샷 간격. 짧으면 DB를 자주 때리고, 길면 멈춘 것처럼 보인다.
POLL_SECONDS = 2.0

Json = dict[str, object]


async def stream_body(
    session: AsyncSession, job_id: int, *, max_frames: int = 0
) -> AsyncIterator[str]:
    """작업이 끝날 때까지 진행을 내보낸다. `max_frames`가 0보다 크면 그만큼만 내보낸다(테스트용)."""
    frames = 0
    while True:
        await session.rollback()
        job = await crypto_job.get_job(session, job_id)
        if job is None:
            yield format_sse("failed", {"jobId": job_id, "reason": "알 수 없는 작업입니다.",
                                        "kind": None})
            return
        yield format_sse("snapshot", {
            "jobId": job_id,
            "status": str(job.status),
            "chunksDone": job.chunks_done,
            "chunksTotal": job.chunks_total,
            "daysDone": covered_days(await crypto_daily.get_coverage(session, job.coin_id),
                                     job.range_start, job.range_end),
            "daysTotal": (job.range_end - job.range_start).days + 1,
            "missingFrom": job.range_start.isoformat(),
            "missingThrough": job.range_end.isoformat(),
        })
        if job.status is JobStatus.SUCCEEDED:
            yield format_sse("completed", {"jobId": job_id})
            return
        if job.status in (JobStatus.FAILED, JobStatus.PARTIAL):
            kind, reason = crypto_job.split_error(job.last_error)
            yield format_sse("failed", {"jobId": job_id, "reason": reason or "수집에 실패했습니다.",
                                        "kind": kind})
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
    """가상자산 수집 진행 스트림 (FR-013)."""
    return StreamingResponse(stream_body(session, job_id), media_type="text/event-stream",
                             headers=SSE_HEADERS)
