"""수집 현황 조회 (T040, T041, T056) — contracts/rest-api 2·3·4절.

001의 `/api/fx/progress`(작업별 스트림)는 그대로 둔다. 002의 기존 화면이 쓰고 있어
깨뜨릴 이유가 없다.
"""

from __future__ import annotations

import datetime as dt
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.collection_stream import event_payload, stream_body
from src.api.errors import InvalidQuery, UnknownCurrency
from src.api.services.timeline import build_timeline
from src.config.settings import SUPPORTED_CURRENCIES as SUPPORTED
from src.config.settings import load_settings
from src.db.session import get_session
from src.repository.collection_event import (
    dropped_for_currency,
    list_by_currency,
    list_by_job,
)
from src.worker.queue import get_queue

router = APIRouter(prefix="/api/fx/collection", tags=["fx"])

Json = dict[str, object]


def _validated(currency: str | None) -> str:
    if currency is None:
        raise InvalidQuery("currency 매개변수가 필요합니다.")
    code = currency.upper()
    if code not in SUPPORTED:
        raise UnknownCurrency(f"지원하지 않는 통화입니다: {currency}")
    return code


@router.get("/timeline")
async def get_timeline(
    session: Annotated[AsyncSession, Depends(get_session)],
    currency: Annotated[str | None, Query()] = None,
) -> Json:
    """선택한 통화의 시간축 자료 (FR-012, FR-027)."""
    code = _validated(currency)
    return await build_timeline(session, code, load_settings(),
                                busy_with=get_queue().in_progress)


@router.get("/stream")
async def get_stream(
    session: Annotated[AsyncSession, Depends(get_session)],
    currency: Annotated[str | None, Query()] = None,
) -> StreamingResponse:
    """선택한 통화의 수집 스트림 (FR-010, FR-015, FR-022)."""
    code = _validated(currency)
    return StreamingResponse(
        stream_body(session, code, load_settings(),
                    busy_with=get_queue().in_progress),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/events")
async def get_events(
    session: Annotated[AsyncSession, Depends(get_session)],
    job_id: Annotated[int | None, Query(alias="jobId")] = None,
    currency: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> Json:
    """종료된 작업의 사건을 사후 조회한다 (FR-022).

    `retention.jobsKept`를 함께 내려주는 이유는 화면이 **"왜 오래된 게 없는지"**를
    설명할 수 있어야 하기 때문이다. 없으면 사용자가 기록 유실로 오해한다 (FR-023).
    """
    settings = load_settings()
    if job_id is None and currency is None:
        raise InvalidQuery("jobId 또는 currency 중 하나가 필요합니다.")

    if job_id is not None:
        rows = await list_by_job(session, job_id, limit=limit)
        dropped = await _dropped_for_job(session, job_id)
    else:
        code = _validated(currency)
        rows = await list_by_currency(session, code, limit=limit)
        dropped = await dropped_for_currency(
            session, code, keep_jobs=settings.event_retention_jobs)

    return {
        "events": [event_payload(r) for r in rows],
        "retention": {"jobsKept": settings.event_retention_jobs},
        # 0보다 크면 이 기록은 불완전하다. 화면이 그 사실을 알려야 사용자가 기록을
        # 근거로 "수집이 정상이었다"는 잘못된 결론을 내리지 않는다 (FR-018b).
        "eventsDropped": dropped,
    }


async def _dropped_for_job(session: AsyncSession, job_id: int) -> int:
    from src.repository.job import get_job

    job = await get_job(session, job_id)
    return job.events_dropped if job is not None else 0


@router.get("/calls-today")
async def get_calls_today(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Json:
    """오늘 데이터 출처를 호출한 수 (FR-024).

    **참고 지표다.** 출처의 한도 리셋 시각이 비공개라 서버 날짜 기준 집계가 실제
    리셋과 어긋날 수 있다. 한도 판정은 출처가 돌려주는 신호로만 한다 (research R3-5).
    """
    from src.repository.raw_response import count_calls_on

    return {
        "callsToday": await count_calls_on(session, dt.date.today()),
        "isAdvisory": True,
    }
