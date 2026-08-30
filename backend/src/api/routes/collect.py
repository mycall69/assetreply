"""`POST /api/fx/collect` · `GET /api/fx/progress` (T097).

contracts/rest-api.md — `joinedExisting`은 이미 진행 중인 작업이 있어 새 작업을 만들지
않고 합류했음을 뜻한다 (FR-015b).
"""

from __future__ import annotations

import datetime as dt
from typing import Annotated

from fastapi import APIRouter, Body, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.errors import UnknownCurrency
from src.api.progress import sse_body
from src.config.settings import SUPPORTED_CURRENCIES as SUPPORTED
from src.config.settings import load_settings
from src.db.session import get_session
from src.ingestion.collector import next_start_date, split_into_chunks
from src.repository.collection_lock import acquire_lock
from src.repository.job import create_job

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

    settings = load_settings()
    end = dt.date.today() - dt.timedelta(days=1)
    jobs: list[Json] = []

    for code in codes:
        start = await next_start_date(session, code, default=settings.probe_start(code))
        chunks = split_into_chunks(start, end, chunk_days=settings.ecos_chunk_days)
        job = await create_job(session, code, start, end, chunks_total=len(chunks))
        existing = await acquire_lock(session, code, job.id)
        if existing is not None:
            await session.rollback()
            jobs.append({"currency": code, "jobId": existing, "joinedExisting": True})
            continue
        await session.commit()
        jobs.append({"currency": code, "jobId": job.id, "joinedExisting": False})

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
