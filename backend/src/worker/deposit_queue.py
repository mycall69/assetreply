"""예금 금리 수집 요청 큐 (T019) — 008 FR-011, FR-012, SC-012.

HTTP 요청은 여기에 일감을 넣고 곧바로 202를 돌려준다. 실제 수집은 예금 수집 줄이 꺼내 돌린다 — 요청
연결이 끊겨도 수집이 이어진다. **환율 큐와 섞지 않는다**(SC-012) — 같은 ECOS 출처라도 한쪽 작업이
다른 쪽을 기다리지 않아야 한다. 호출 한도는 관문(`EcosGate`)이 함께 지킨다. 투자처 단위로 중복을
거른다(007 `CryptoQueue`와 같은 모양).
"""

from __future__ import annotations

import asyncio
import datetime as dt
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DepositWork:
    """수집 일감 하나. 구간은 그 실행에 필요한 구간(시작 달 ~ 이번 달, 각 달 1일)이다."""

    job_id: int
    institution: str
    start_month: dt.date
    end_month: dt.date


class DepositQueue:
    __slots__ = ("_queue", "_active")

    def __init__(self) -> None:
        self._queue: asyncio.Queue[DepositWork] = asyncio.Queue()
        self._active: set[str] = set()

    def request(self, work: DepositWork) -> bool:
        """시작을 요청한다. 받아들였으면 `True`. **동기 메서드다** — 라우트가 응답을 만들다가
        부른다."""
        if work.institution in self._active:
            return False
        self._active.add(work.institution)
        self._queue.put_nowait(work)
        return True

    async def pop(self) -> DepositWork:
        return await self._queue.get()

    def done(self, institution: str) -> None:
        self._active.discard(institution)

    def is_active(self, institution: str) -> bool:
        return institution in self._active


_queue: DepositQueue | None = None


def get_deposit_queue() -> DepositQueue:
    global _queue
    if _queue is None:
        _queue = DepositQueue()
    return _queue


def reset_deposit_queue() -> None:
    """테스트용. 앞 테스트의 요청이 남으면 뒤 테스트의 요청이 조용히 무시된다."""
    global _queue
    _queue = None
