"""수집 스트림 (T041, T042, T057) — contracts/rest-api 3절, research R3-7.

선택한 통화의 상태를 SSE로 내보낸다. **001의 작업별 스트림으로 대체할 수 없다.**

| 001 스트림의 한계 | 이유 |
|-------------------|------|
| 구독에 `jobId`가 필수다 | 수집이 없으면 구독할 대상이 없어 대기 상태를 표현할 수 없다 |
| 작업이 끝나면 닫힌다 | 서버가 `return`하고 클라이언트도 `close()`한다 |
| 작업 범위만 안다 | 오늘 호출 수·멈춤 판정·커버리지는 작업 바깥의 정보다 |

FR-010은 재진입 시 상태를 즉시 제시하라고 요구하는데, 이는 **진행 중인 작업이 없을
때도** 성립해야 한다. 화면이 열려 있는 동안 유지되는 연결이 필요한 이유다.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator, Callable

from sqlalchemy.ext.asyncio import AsyncSession

from src.api.services.timeline import build_timeline
from src.config.settings import Settings
from src.db.models import FxCollectionEvent
from src.repository.collection_event import list_by_currency

#: 상태 변화가 없어도 이 간격으로 `snapshot`을 보낸다. SC-004(10초 이내 갱신)의 근거다.
HEARTBEAT_SECONDS = 5

#: 모든 SSE 응답의 머리글 (006 FR-045a, research R6-19). **`no-transform`이 없으면 중간 프록시가
#: 압축하면서 이벤트를 모아 둔다** — 2026-10-03 실측으로 Next.js 개발 서버가 브라우저 요청에 gzip을
#: 걸어, 스트림이 끝날 때까지 `EventSource`에 이벤트가 하나도 도착하지 않았다.
SSE_HEADERS: dict[str, str] = {
    "Cache-Control": "no-cache, no-transform",
    "X-Accel-Buffering": "no",
}

Json = dict[str, object]


def format_sse(event: str, data: Json) -> str:
    """SSE 프레임으로 직렬화한다.

    `data`를 개행 없는 한 줄 JSON으로 만든다 — 값에 개행이 섞이면 프레임이 쪼개져
    클라이언트가 이벤트를 받지 못한다 (001 progress.py와 같은 규약).
    """
    payload = json.dumps(data, ensure_ascii=False).replace("\n", " ")
    return f"event: {event}\ndata: {payload}\n\n"


def event_payload(row: FxCollectionEvent) -> Json:
    """이벤트 행을 화면용 JSON으로 만든다."""
    return {
        "jobId": row.job_id,
        "currency": row.currency_code,
        "kind": row.kind,
        "chunkFrom": row.chunk_from.isoformat() if row.chunk_from else None,
        "chunkTo": row.chunk_to.isoformat() if row.chunk_to else None,
        "rowsStored": row.rows_stored,
        "detail": row.detail,
        "occurredAt": row.occurred_at.isoformat() if row.occurred_at else None,
    }


async def stream_body(
    session: AsyncSession,
    currency_code: str,
    settings: Settings,
    *,
    busy_with: str | None = None,
    busy_with_fn: Callable[[], str | None] | None = None,
    max_frames: int = 0,
) -> AsyncIterator[str]:
    """`StreamingResponse`에 넘길 본문 생성기.

    연결 직후 `snapshot`을 1회 보내 화면이 즉시 따라잡게 한다 (FR-010). 이후 5초마다
    갱신하며, 새 사건이 생기면 `event`로 덧붙인다 (FR-022).

    **작업이 끝나도 닫지 않는다.** 화면이 열려 있는 동안 유지되어 사용자가 새 수집을
    시작하면 같은 연결로 이어진다.

    `max_frames`가 0보다 크면 그만큼만 내보내고 끝낸다 (테스트용).

    `busy_with_fn`을 주면 **프레임마다** 다른 통화의 진행 여부를 다시 읽는다 (006). 연결할
    때 한 번만 읽으면 다른 통화가 끝나도 끝까지 같은 값을 보내, 기다리던 화면(`waiting`)이
    그 사실을 알 길이 없다.
    """
    seen_event_id = 0
    frames = 0

    while True:
        # 앞 프레임의 읽기 트랜잭션을 끝낸다(006 T113 보강). 끝내지 않으면 MySQL(REPEATABLE
        # READ)이 첫 조회의 스냅샷을 계속 보여, 워커가 수집을 끝내도 `snapshot`만 보내고 `idle`이
        # 오지 않는다. 쓰는 것이 없으므로 되돌려도 잃는 것이 없다.
        await session.rollback()
        current = busy_with_fn() if busy_with_fn is not None else busy_with
        snapshot = await build_timeline(session, currency_code, settings,
                                        busy_with=current)
        if "activeJob" in snapshot:
            yield format_sse("snapshot", snapshot)
        else:
            # 진행 중인 수집이 없다. 연결은 유지하고 대기 상태를 알린다.
            yield format_sse("idle", {
                "currency": currency_code,
                "callsToday": snapshot["callsToday"],
                "busyWith": snapshot["busyWith"],
            })
        frames += 1

        # 새로 생긴 사건만 덧붙인다. 전체를 다시 보내면 화면이 읽던 위치를 잃는다.
        rows = await list_by_currency(session, currency_code, limit=20)
        fresh = [r for r in reversed(rows) if r.id > seen_event_id]
        for row in fresh:
            seen_event_id = max(seen_event_id, row.id)
            yield format_sse("event", event_payload(row))
            frames += 1

        if max_frames and frames >= max_frames:
            return
        await asyncio.sleep(HEARTBEAT_SECONDS)
