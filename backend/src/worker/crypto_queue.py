"""가상자산 수집 요청 큐 (T031) — 007 FR-013~FR-015, research R7-11.

HTTP 요청은 여기에 일감을 넣고 곧바로 202를 돌려준다. 실제 수집은 가상자산 수집 줄이 꺼내 돌린다 —
요청 연결이 끊겨도 수집이 이어진다. **주식 큐와 섞지 않는다**(SC-012) — 출처가 달라 한쪽이 막혀도
다른 쪽이 기다리지 않아야 한다. 코인 단위로 중복을 거른다(005 `StockQueue`와 같은 모양).
"""

from __future__ import annotations

import asyncio
import datetime as dt
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CryptoWork:
    """수집 일감 하나. 작업 ID까지 들고 다녀야 줄이 진행을 기록할 수 있다."""

    job_id: int
    coin_id: int
    #: 출처의 코인 식별자. 심볼이 아니다 — 심볼은 유일하지 않다(FR-004).
    source_id: str
    start: dt.date
    end: dt.date


class CryptoQueue:
    __slots__ = ("_queue", "_active")

    def __init__(self) -> None:
        self._queue: asyncio.Queue[CryptoWork] = asyncio.Queue()
        self._active: set[int] = set()

    def request(self, work: CryptoWork) -> bool:
        """시작을 요청한다. 받아들였으면 `True`. **동기 메서드다** — 라우트가 응답을 만들다가
        부른다."""
        if work.coin_id in self._active:
            return False
        self._active.add(work.coin_id)
        self._queue.put_nowait(work)
        return True

    async def pop(self) -> CryptoWork:
        return await self._queue.get()

    def done(self, coin_id: int) -> None:
        self._active.discard(coin_id)

    def is_active(self, coin_id: int) -> bool:
        return coin_id in self._active


_queue: CryptoQueue | None = None


def get_crypto_queue() -> CryptoQueue:
    global _queue
    if _queue is None:
        _queue = CryptoQueue()
    return _queue


def reset_crypto_queue() -> None:
    """테스트용. 앞 테스트의 요청이 남으면 뒤 테스트의 요청이 조용히 무시된다."""
    global _queue
    _queue = None
