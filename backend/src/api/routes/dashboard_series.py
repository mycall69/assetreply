"""지표 화면 경로 (014 T057) — FR-010, FR-016, FR-019, contracts A2~A4.

- `GET /api/dashboard/indicators/{id}/series?unit=` — 그래프(200) 또는 받는 중·실패(202). 없는
  지표는 404
- `POST /api/dashboard/indicators/{id}/collect` — 다시 시도. 워커를 곧바로 깨운다(202). 환율은 외환
  수집 경로에 넘긴다
- `GET /api/dashboard/indicators/{id}/progress` — SSE. 2초마다 커버리지 행을 읽는다(007
  `crypto_progress`와 같다 — 브로드캐스터 없음).
  **프레임마다 읽기 트랜잭션을 끝낸다** — 끝내지 않으면 MySQL이 첫 스냅샷을 계속 보여 `completed`가
  오지 않는다(006 R6-19)
- 환율도 같은 진행 경로다(반복 2026-10-10 — FR-018). 외환 커버리지·외환 수집 작업을 읽어 같은 세
  사건을 낸다(`indicator_series.fx_state`). 외환 시작 큐가 처리 중인 통화는 실패보다 받는 중이다
"""

from __future__ import annotations

import asyncio
import datetime as dt
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.collection_stream import SSE_HEADERS, format_sse
from src.api.services import market_quotes
from src.api.services.collection_gate import ensure_background_job
from src.api.services.indicator_series import (
    complete,
    failure_after_success,
    fx_state,
    progress_json,
    series_response,
    unit_of,
)
from src.config.settings import load_settings
from src.db.session import get_session
from src.repository import market_daily
from src.simulation.market_indicators import Indicator, get
from src.worker import market_worker
from src.worker.queue import get_queue

router = APIRouter(prefix="/api/dashboard/indicators", tags=["dashboard"])

#: 스냅샷 간격. 짧으면 DB를 자주 때리고, 길면 멈춘 것처럼 보인다.
POLL_SECONDS = 2.0

Json = dict[str, object]


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def _unknown(indicator_id: str) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content={"status": "unknown_indicator", "message": f"없는 지표입니다: {indicator_id}"},
    )


def _indicator(indicator_id: str) -> Indicator | None:
    return get(indicator_id)


@router.get("/{indicator_id}/series", response_model=None)
async def get_series(
    session: Annotated[AsyncSession, Depends(get_session)],
    indicator_id: str,
    unit: Annotated[str | None, Query()] = None,
) -> Json | JSONResponse:
    indicator = _indicator(indicator_id)
    if indicator is None:
        return _unknown(indicator_id)
    status, body = await series_response(
        session,
        indicator,
        unit_of(unit),
        quotes=market_quotes.get_shared_service(),
        settings=load_settings(),
        now=utc_now(),
        ensure_job=ensure_background_job,
        fx_busy=get_queue().in_progress,
    )
    return body if status == 200 else JSONResponse(status_code=status, content=body)


@router.post("/{indicator_id}/collect", response_model=None)
async def post_collect(
    session: Annotated[AsyncSession, Depends(get_session)], indicator_id: str
) -> JSONResponse:
    indicator = _indicator(indicator_id)
    if indicator is None:
        return _unknown(indicator_id)
    if indicator.history == "fx":
        ticket = await ensure_background_job(session, indicator.fx_currency or "")
        return JSONResponse(status_code=202, content={"status": "queued", **ticket.as_json()})
    market_worker.wake()
    return JSONResponse(status_code=202, content={"status": "queued"})


async def stream_body(
    session: AsyncSession, indicator_id: str, *, max_frames: int = 0
) -> AsyncIterator[str]:
    """과거 구간이 다 받아지거나 실패할 때까지 진행을 내보낸다. `max_frames`가 0보다 크면
    그만큼만(테스트용)."""
    indicator = _indicator(indicator_id)
    if indicator is not None and indicator.history == "fx":
        async for frame in _fx_stream(session, indicator, max_frames=max_frames):
            yield frame
        return
    frames = 0
    while True:
        await session.rollback()
        row = await market_daily.get_coverage(session, indicator_id)
        yield format_sse("snapshot", progress_json(row))
        if complete(row):
            yield format_sse("completed", {"id": indicator_id})
            return
        failure = failure_after_success(row)
        if failure is not None:
            yield format_sse(
                "failed",
                {"id": indicator_id, "kind": failure["kind"], "message": failure["message"]},
            )
            return
        frames += 1
        if max_frames and frames >= max_frames:
            return
        await asyncio.sleep(POLL_SECONDS)


async def _fx_stream(
    session: AsyncSession, indicator: Indicator, *, max_frames: int
) -> AsyncIterator[str]:
    """환율 — 외환 이력이 충분해지면 `completed`, 외환 수집이 실패했으면 `failed{fx_collection}`."""
    frames = 0
    while True:
        await session.rollback()
        state = await fx_state(
            session,
            indicator,
            settings=load_settings(),
            now=utc_now(),
            fx_busy=get_queue().in_progress,
        )
        if state.complete:
            yield format_sse("completed", {"id": indicator.id})
            return
        if state.failure is not None:
            yield format_sse(
                "failed",
                {
                    "id": indicator.id,
                    "kind": state.failure["kind"],
                    "message": state.failure["message"],
                },
            )
            return
        yield format_sse("snapshot", state.progress)
        frames += 1
        if max_frames and frames >= max_frames:
            return
        await asyncio.sleep(POLL_SECONDS)


@router.get("/{indicator_id}/progress", response_model=None)
async def get_progress(
    session: Annotated[AsyncSession, Depends(get_session)], indicator_id: str
) -> StreamingResponse | JSONResponse:
    if _indicator(indicator_id) is None:
        return _unknown(indicator_id)
    return StreamingResponse(
        stream_body(session, indicator_id), media_type="text/event-stream", headers=SSE_HEADERS
    )
