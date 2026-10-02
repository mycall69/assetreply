"""동기 대기 / 백그라운드 위임 분기 (T051) — 001. 006 T092에서 백그라운드 요청을 고쳤다.

FR-035: 필요 구간이 임계값 이하이면 수집 완료까지 대기한 뒤 결과를 제시한다.
FR-035a: 임계값을 초과하면 즉시 진행 상태를 제시하고 완료 후 결과를 갱신한다.
FR-035b: 임계값은 설정값이며 기본 30일이다.

날짜 조회와 차트 요청이 이 모듈을 공유한다 (FR-032a). 006의 시뮬레이션 환율 판정도
`ensure_background_job`을 거친다 — 판정이 두 곳에 생기면 외환 화면과 시뮬레이션이 같은
상황을 다르게 말한다 (006 analyze A1).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import FxCollectionLock
from src.repository.collection_lock import SCOPE_COLLECTION
from src.worker.queue import StartQueue, get_queue


class CollectionDecision(StrEnum):
    """수집이 필요한지, 필요하다면 어느 경로로 갈지."""

    NONE = "none"
    WAIT = "wait"
    BACKGROUND = "background"


def decide_collection(*, missing_days: int, threshold_days: int) -> CollectionDecision:
    """부족한 일수와 임계값으로 경로를 정한다.

    30년치 백필은 수 분 이상 걸리므로 대기시키면 조회가 사실상 멈춘다. 반대로 며칠치
    증분까지 백그라운드로 넘기면 평소 조회가 두 단계가 된다.
    """
    if missing_days <= 0:
        return CollectionDecision.NONE
    return (CollectionDecision.WAIT if missing_days <= threshold_days
            else CollectionDecision.BACKGROUND)


CollectState = Literal["collecting", "queued", "waiting"]


@dataclass(frozen=True, slots=True)
class CollectionTicket:
    """수집 표 (006 research R6-10). **작업 번호는 점유가 있을 때만 있다**(analyze N1).

    작업 행은 워커의 `run_once`가 만들므로 큐에 넣는 시점에는 번호가 없다. 번호가 없으면
    화면은 통화별 스트림(003)으로 진행을 본다.
    """

    currency: str
    state: CollectState
    job_id: int | None
    busy_with: str | None
    progress_url: str

    def as_json(self) -> dict[str, object]:
        """외환 화면 202에 싣는 필드 (006 contracts 6a절)."""
        return {"state": self.state, "jobId": self.job_id, "busyWith": self.busy_with,
                "progressUrl": self.progress_url}


def _stream_url(currency_code: str) -> str:
    return f"/api/fx/collection/stream?currency={currency_code}"


async def ensure_background_job(
    session: AsyncSession, currency_code: str, *, queue: StartQueue | None = None
) -> CollectionTicket:
    """백그라운드 수집을 **요청하고** 수집 표를 돌려준다 (006 FR-046a, T092).

    **작업도 점유도 만들지 않는다.** 001의 이 함수는 작업과 점유를 만들고 워커의 큐에
    넣지 않았다. 워커의 `run_once`는 점유를 새로 잡으려다 이미 잡혀 있으면 조용히 끝나므로,
    그 작업은 아무도 실행하지 않는 채 점유만 쥐고 정리 루프가 회수할 때까지 그 통화의
    수집을 막았다. 작업과 점유는 `run_once`만 만든다.

    | 상황 | `state` | 작업 번호 |
    |------|---------|-----------|
    | 그 통화의 점유가 있다(실행 중) | `collecting` | 점유의 작업 |
    | 큐가 받았다 / 이미 큐에 있다 | `queued` | 없음 |
    | 다른 통화 처리 중이라 큐가 거절했다 | `waiting` | 없음 |

    **큐가 거절하면 아무것도 남기지 않는다** — 미리 만든 작업은 실행되지 않는다.
    """
    start_queue = queue if queue is not None else get_queue()
    running = (await session.execute(select(FxCollectionLock.job_id).where(
        FxCollectionLock.scope == SCOPE_COLLECTION,
        FxCollectionLock.currency_code == currency_code))).scalar_one_or_none()
    if running is not None:
        return CollectionTicket(currency_code, "collecting", int(running), None,
                                f"/api/fx/progress?jobId={running}")

    accepted = await start_queue.request(currency_code)
    busy = start_queue.in_progress
    if accepted or busy == currency_code:
        return CollectionTicket(currency_code, "queued", None, None, _stream_url(currency_code))
    return CollectionTicket(currency_code, "waiting", None, busy, _stream_url(currency_code))
