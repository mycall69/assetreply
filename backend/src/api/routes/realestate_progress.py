"""부동산 수집 진행 (009 T025, FR-011, FR-014, contracts/rest-api `GET /api/realestate/progress`).

006~008 진행 스트림과 같은 사건·머리글이다. 스냅샷은 종류마다 분모가 달라도 한
모양(`done`·`total`)이다 — 실거래는 받은 달/받을 달, 기본 정보는 받은 단지/단지 수, 행정구역은 받은
쪽/쪽 수. 실패는 종류를 싣는다.

**프레임마다 읽기 트랜잭션을 끝낸다**(006 R6-19) — 끝내지 않으면 MySQL이 첫 스냅샷을 계속 보여
진행이 멈춘 것처럼 보이고 `completed`가 오지 않는다.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.collection_stream import SSE_HEADERS, format_sse
from src.db.models import JobStatus
from src.db.session import get_session
from src.repository import apt_job

router = APIRouter(prefix="/api/realestate", tags=["realestate"])

#: 스냅샷 간격. 짧으면 DB를 자주 때리고, 길면 멈춘 것처럼 보인다.
POLL_SECONDS = 2.0


async def stream_body(session: AsyncSession, job_id: int, *,
                      max_frames: int = 0) -> AsyncIterator[str]:
    """작업이 끝날 때까지 진행을 내보낸다. `max_frames`가 0보다 크면 그만큼만 내보낸다(테스트용)."""
    frames = 0
    while True:
        await session.rollback()
        job = await apt_job.get_job(session, job_id)
        if job is None:
            yield format_sse("failed", {"jobId": job_id, "kind": None,
                                        "reason": "알 수 없는 작업입니다."})
            return
        yield format_sse("snapshot", {"jobId": job_id, "kind": job.kind, "target": job.target,
                                      "status": str(job.status), "done": job.done,
                                      "total": job.total})
        if job.status is JobStatus.SUCCEEDED:
            yield format_sse("completed", {"jobId": job_id})
            return
        if job.status in (JobStatus.FAILED, JobStatus.PARTIAL):
            kind, reason = apt_job.split_error(job.last_error)
            yield format_sse("failed", {"jobId": job_id, "kind": kind,
                                        "reason": reason or "수집에 실패했습니다."})
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
    """부동산 수집 진행 스트림 (FR-011)."""
    return StreamingResponse(stream_body(session, job_id), media_type="text/event-stream",
                             headers=SSE_HEADERS)
