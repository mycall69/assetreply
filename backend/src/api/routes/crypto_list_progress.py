"""코인 목록 갱신 진행 (T018) — 007 FR-005b, contracts/rest-api `GET /api/crypto/list/progress`,
analyze C2.

처음 받는 목록은 약 2분 걸린다. 진행이 보이지 않으면 사용자는 멈춘 것으로 읽는다(헌법 원칙 VII).
갱신 줄이 쪽마다 점유 행에 적은 진행을 **프레임마다 DB에서 새로 읽어** 보낸다(006 R6-19 — 프레임마다
rollback).

- `snapshot` — 판·받은 쪽 수·어림한 전체 쪽 수·받은 코인 수. 판이 바뀌면 0부터 센다
- `completed`·`failed` — 끝. `failed`의 `reason`은 검색 응답의 `list.reason`과 같다
- 갱신 중이 아니면 마지막 상태를 한 번 보내고 닫는다(받은 적이 없으면 `idle`)

**`error`에서 닫지 않는다**는 클라이언트 쪽 규약은 003·005와 같다.
"""

from __future__ import annotations

import asyncio
import datetime as dt
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.collection_stream import SSE_HEADERS, format_sse
from src.api.services.crypto_list_refresh import (
    EN,
    KO,
    CoinRefreshRecord,
    edition_state,
    expected_pages,
)
from src.db.models import CryptoCoinRefresh
from src.db.session import get_session
from src.repository import crypto_coin as repo
from src.repository import crypto_list_lock as locks
from src.worker import crypto_list_queue
from src.worker.crypto_list_queue import CryptoListQueue

router = APIRouter(prefix="/api/crypto", tags=["crypto"])

#: 스냅샷 간격. 한 쪽은 간격 제한(1.5초) 뒤에 오므로 그보다 짧게 둔다.
POLL_SECONDS = 1.0

Json = dict[str, object]


def get_crypto_list_queue() -> CryptoListQueue:
    return crypto_list_queue.get_crypto_list_queue()


def _iso(value: dt.datetime | None) -> str | None:
    return None if value is None else f"{value.isoformat()}Z"


def _expected(edition: str | None, records: dict[str, CryptoCoinRefresh]) -> int | None:
    row = records.get(edition or EN)
    return expected_pages(row.row_count if row is not None else None)


def _final(records: dict[str, CryptoCoinRefresh]) -> tuple[str, Json]:
    """갱신 중이 아닐 때의 마지막 상태."""
    english = edition_state(CoinRefreshRecord.from_row(records.get(EN)), refreshing=False)
    if english.state == "failed":
        row = records[EN]
        return "failed", {"reason": english.reason, "message": row.last_error or ""}
    if english.state == "never":
        return "idle", {}
    korean = edition_state(CoinRefreshRecord.from_row(records.get(KO)), refreshing=False)
    return "completed", {"asOf": _iso(english.as_of), "coins": records[EN].row_count,
                         "koreanNames": korean.state}


async def stream_body(
    session: AsyncSession, *, queue: CryptoListQueue, max_frames: int = 0
) -> AsyncIterator[str]:
    """갱신이 끝날 때까지 진행을 내보낸다. `max_frames`가 0보다 크면 그만큼만 내보낸다(테스트용).

    **점유가 풀리면 끝이다.** 갱신 줄은 갱신이 끝난 뒤에야 큐에서 요청을 뺀다 — 그 사이를 "곧
    받는다"로 읽으면 끝난 갱신이 0쪽으로 되돌아간다. 점유를 본 적이 있거나, 스트림을 연 뒤 새 시도가
    기록되었으면 끝난 것이다.
    """
    frames = 0
    saw_lock = False
    first_attempt: dt.datetime | None = None
    opened = False
    while True:
        # 앞 프레임의 읽기 트랜잭션을 끝낸다 — MySQL(REPEATABLE READ)이 첫 스냅샷을 계속 보여 진행이
        # 멈춘 것처럼 보인다.
        await session.rollback()
        lock = await locks.get_lock(session)
        records = await repo.all_refresh(session)
        english = records.get(EN)
        attempt = english.last_attempt_at if english is not None else None
        if not opened:
            first_attempt, opened = attempt, True

        if lock is not None:
            saw_lock = True
            yield format_sse("snapshot", {
                "edition": lock.edition, "pagesDone": lock.pages_done,
                "pagesExpected": _expected(lock.edition, records), "coinsSeen": lock.coins_seen})
        elif not saw_lock and attempt == first_attempt and queue.is_active(locks.SCOPE):
            # 요청은 들어갔고 갱신 줄이 아직 꺼내지 않았다
            yield format_sse("snapshot", {
                "edition": None, "pagesDone": 0, "pagesExpected": _expected(EN, records),
                "coinsSeen": 0})
        else:
            name, payload = _final(records)
            yield format_sse(name, payload)
            return

        frames += 1
        if max_frames and frames >= max_frames:
            return
        await asyncio.sleep(POLL_SECONDS)


@router.get("/list/progress")
async def get_list_progress(
    session: Annotated[AsyncSession, Depends(get_session)],
    queue: Annotated[CryptoListQueue, Depends(get_crypto_list_queue)],
) -> StreamingResponse:
    """코인 목록 갱신 진행 스트림 (FR-005b)."""
    return StreamingResponse(
        stream_body(session, queue=queue), media_type="text/event-stream", headers=SSE_HEADERS)
