"""주식 수집 진행 상태 (T022) — 005 FR-047, contracts/rest-api.

003이 FX에서 만든 스트림과 같은 모양이다. **`error`에서 `close()`하지 않는다** —
`EventSource`의 자동 재연결에 의존하는 것이 SSE를 택한 근거이며, 닫으면 그 동작을
없애게 된다 (003이 001에서 얻은 교훈).

**작업이 끝나면 `completed`를 보내고 끝낸다.** 화면은 그 신호를 받아 시뮬레이션을 다시
요청한다 — 부분 결과를 먼저 보여주지 않는 대신(FR-049) 완료 시점을 알려야 한다.
"""

from __future__ import annotations

import asyncio
import datetime as dt
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

# 003이 만든 직렬화를 그대로 쓴다. **값의 개행을 지우는 가드가 거기 있다** —
# `last_error`에 예외 메시지가 그대로 들어가므로 개행이 섞일 수 있고, 섞이면 SSE
# 프레임이 쪼개져 클라이언트가 이벤트를 받지 못한다.
from src.api.collection_stream import SSE_HEADERS, format_sse
from src.db.models import JobStatus
from src.db.session import get_session
from src.repository.stock import Range, get_coverage
from src.repository.stock_job import get_job, split_error

router = APIRouter(prefix="/api/stocks", tags=["stocks"])

#: 스냅샷 간격. 짧게 잡으면 DB를 자주 때리고, 길게 잡으면 진행이 멈춘 것처럼 보인다.
POLL_SECONDS = 2.0

Json = dict[str, object]


def covered_days(coverage: Range | None, start: dt.date, end: dt.date) -> int:
    """`start`~`end`(양끝 포함) 가운데 커버리지가 덮는 달력 일수 (006 FR-045a).

    커버리지는 청크마다 커밋되므로 따로 세지 않아도 받은 날을 안다. 작업 구간 앞뒤로 이미 받아
    둔 구간이 겹치면 처음부터 0보다 크다 — "그 구간 가운데 이미 확보한 날"이라는 뜻이라 맞다.
    """
    if coverage is None:
        return 0
    first, last = max(start, coverage[0]), min(end, coverage[1])
    return max(0, (last - first).days + 1)


async def stream_body(
    session: AsyncSession, job_id: int, *, max_frames: int = 0
) -> AsyncIterator[str]:
    """작업이 끝날 때까지 진행 상태를 내보낸다.

    `max_frames`가 0보다 크면 그만큼만 내보내고 끝낸다 (테스트용).
    """
    frames = 0
    while True:
        # 앞 프레임의 읽기 트랜잭션을 끝낸다(006 T113 보강). 끝내지 않으면 MySQL(REPEATABLE READ)이
        # 첫 조회의 스냅샷을 계속 보여, 워커가 작업을 끝내도 진행이 0에 머물고 `completed`가 오지
        # 않는다 — 화면은 결과를 다시 요청하지 못한다. 쓰는 것이 없으므로 되돌려도 잃는 것이 없다.
        await session.rollback()
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
            # 006 FR-045a — 받은 날 / 받을 날(달력 일수). 구간 수는 호환을 위해 남긴다.
            "daysDone": covered_days(
                await get_coverage(session, job.stock_id), job.range_start, job.range_end),
            "daysTotal": (job.range_end - job.range_start).days + 1,
        }
        yield format_sse("snapshot", payload)

        if job.status is JobStatus.SUCCEEDED:
            yield format_sse("completed", {"jobId": job_id})
            return
        if job.status in (JobStatus.FAILED, JobStatus.PARTIAL):
            # 006 FR-032 — 출처가 심볼을 모른 실패는 `status`로 구별해 알린다. 표지는 사유에서 뗀다.
            status, reason = split_error(job.last_error)
            failed: Json = {"jobId": job_id, "reason": reason or "수집에 실패했습니다."}
            if status is not None:
                failed["status"] = status
            yield format_sse("failed", failed)
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
        headers=SSE_HEADERS,
    )
