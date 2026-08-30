"""수집 진행률 SSE 스트림 (T096).

contracts/sse-progress.md — 서버→클라이언트 단방향이라 WebSocket 대신 SSE를 쓴다.
브라우저 `EventSource`의 자동 재연결을 그대로 활용한다 (research R4).

재연결 시 현재 상태를 즉시 1회 보내 클라이언트가 공백 없이 따라잡게 한다.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import JobStatus
from src.repository.coverage import get_coverage
from src.repository.job import get_job

# SC-009: 진행 상황이 갱신되지 않는 구간을 10초 이상 경험하지 않는다
HEARTBEAT_SECONDS = 5

Json = dict[str, object]


@dataclass(frozen=True, slots=True)
class ProgressEvent:
    name: str
    data: Json


def format_sse(event: str, data: Json) -> str:
    """SSE 프레임으로 직렬화한다.

    `data`를 개행 없는 한 줄 JSON으로 만든다 — 값에 개행이 섞이면 프레임이 쪼개져
    클라이언트가 이벤트를 받지 못한다.
    """
    payload = json.dumps(data, ensure_ascii=False).replace("\n", " ")
    return f"event: {event}\ndata: {payload}\n\n"


async def progress_stream(
    session: AsyncSession, *, job_id: int, max_events: int = 0
) -> AsyncIterator[ProgressEvent]:
    """작업의 진행 상황을 이벤트로 흘린다.

    `max_events`가 0보다 크면 그만큼만 내보내고 끝낸다 (테스트용).
    """
    emitted = 0
    while True:
        job = await get_job(session, job_id)
        if job is None:
            yield ProgressEvent("error", {"message": f"작업을 찾을 수 없습니다: {job_id}"})
            return

        await session.refresh(job)
        coverage = await get_coverage(session, job.currency_code)
        covered_through = (coverage.covered_through.isoformat()
                           if coverage is not None else None)

        if job.status is JobStatus.RUNNING:
            yield ProgressEvent("progress", {
                "jobId": job.id,
                "currency": job.currency_code,
                "status": job.status.value,
                "chunksTotal": job.chunks_total,
                "chunksDone": job.chunks_done,
                "coveredThrough": covered_through,
                "lastError": job.last_error,
            })
        else:
            yield ProgressEvent("completed", {
                "jobId": job.id,
                "currency": job.currency_code,
                "status": job.status.value,
                "chunksDone": job.chunks_done,
                "coveredThrough": covered_through,
                "lastError": job.last_error,
                "finishedAt": job.finished_at.isoformat() if job.finished_at else None,
            })
            return

        emitted += 1
        if max_events and emitted >= max_events:
            return
        await asyncio.sleep(HEARTBEAT_SECONDS)


async def sse_body(session: AsyncSession, *, job_id: int) -> AsyncIterator[str]:
    """`StreamingResponse`에 넘길 본문 생성기."""
    async for event in progress_stream(session, job_id=job_id):
        yield format_sse(event.name, event.data)
