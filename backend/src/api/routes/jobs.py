"""`GET /api/fx/jobs` (T098, FR-037).

실패·부분 성공 이력은 영구 보관되므로 여기서 사후에 원인을 확인할 수 있다 (SC-011).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import FxCollectionJob, JobStatus
from src.db.session import get_session
from src.repository.job import list_jobs

router = APIRouter(prefix="/api/fx", tags=["fx"])

Json = dict[str, object]


def _serialize(job: FxCollectionJob) -> Json:
    return {
        "jobId": job.id,
        "currency": job.currency_code,
        "status": job.status.value,
        "rangeStart": job.range_start.isoformat(),
        "rangeEnd": job.range_end.isoformat(),
        "chunksTotal": job.chunks_total,
        "chunksDone": job.chunks_done,
        "startedAt": job.started_at.isoformat(),
        "finishedAt": job.finished_at.isoformat() if job.finished_at else None,
        "lastError": job.last_error,
    }


@router.get("/jobs")
async def list_jobs_endpoint(
    session: Annotated[AsyncSession, Depends(get_session)],
    currency: Annotated[str | None, Query()] = None,
    status: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> Json:
    parsed = JobStatus(status) if status else None
    rows = await list_jobs(
        session,
        currency_code=currency.upper() if currency else None,
        status=parsed,
        limit=limit)
    return {"jobs": [_serialize(j) for j in rows]}
