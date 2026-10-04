"""예금 금리 수집 진행 (T020) — 008 FR-011, FR-016, contracts/rest-api `GET /api/deposit/progress`.

006·007 진행 스트림과 같은 사건·머리글이다. 진행은 **받은 달 / 받을 달**이다 — 받을 달은 그 실행에
필요한 구간 (시작 달 ~ 이번 달)의 달 수라 처음 받을 때도 알고, 받은 달은 그중 받은 구간 안의
달이다(analyze I1). 미발표 달은 받을 수 없어 완료 때 받은 달이 받을 달보다 적을 수 있다. 실패는
종류(`kind`)를 싣는다(FR-016).

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
from src.api.services.deposit_collect import month_text
from src.db.models import JobStatus
from src.db.session import get_session
from src.repository import deposit_job, deposit_rate
from src.worker.deposit_runner import months_between, shift_months

router = APIRouter(prefix="/api/deposit", tags=["deposit"])

#: 스냅샷 간격. 짧으면 DB를 자주 때리고, 길면 멈춘 것처럼 보인다.
POLL_SECONDS = 2.0


async def stream_body(
    session: AsyncSession, job_id: int, *, max_frames: int = 0
) -> AsyncIterator[str]:
    """작업이 끝날 때까지 진행을 내보낸다. `max_frames`가 0보다 크면 그만큼만 내보낸다(테스트용)."""
    frames = 0
    while True:
        await session.rollback()
        job = await deposit_job.get_job(session, job_id)
        if job is None:
            yield format_sse("failed", {"jobId": job_id, "reason": "알 수 없는 작업입니다.",
                                        "kind": None})
            return
        coverage = await deposit_rate.get_coverage(session, job.institution)
        done, missing_from = 0, job.range_start
        if coverage is not None:
            done = months_between(max(job.range_start, coverage.first_month),
                                  min(job.range_end, coverage.latest_month))
            missing_from = min(job.range_end, max(job.range_start,
                                                  shift_months(coverage.latest_month, 1)))
        yield format_sse("snapshot", {
            "jobId": job_id, "status": str(job.status), "institution": job.institution,
            "monthsDone": done, "monthsTotal": job.months_total,
            "missingFrom": month_text(missing_from), "missingThrough": month_text(job.range_end),
        })
        if job.status is JobStatus.SUCCEEDED:
            yield format_sse("completed", {
                "jobId": job_id,
                "latestMonth": None if coverage is None else month_text(coverage.latest_month)})
            return
        if job.status in (JobStatus.FAILED, JobStatus.PARTIAL):
            kind, reason = deposit_job.split_error(job.last_error)
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
    """예금 금리 수집 진행 스트림 (FR-011)."""
    return StreamingResponse(stream_body(session, job_id), media_type="text/event-stream",
                             headers=SSE_HEADERS)
