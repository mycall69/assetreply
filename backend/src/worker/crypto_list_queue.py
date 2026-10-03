"""코인 목록 갱신 요청 큐 (T018) — 007 FR-005, R7-11.

검색은 여기에 요청을 넣고 **곧바로 답한다** — 갱신을 기다리면 처음 받는 목록은 약 2분 걸린다. 실제
갱신은 목록 갱신 줄이 꺼내 돌린다. 범위로 중복을 거른다 — 비용 절약이고 정합성의 근거는 DB
점유다(006 `ListingQueue`와 같은 모양, 섞지 않는다).
"""

from __future__ import annotations

import asyncio


class CryptoListQueue:
    """갱신 요청을 목록 갱신 줄로 넘기는 통로."""

    __slots__ = ("_queue", "_active")

    def __init__(self) -> None:
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        # 대기 중이거나 처리 중인 범위. `done()`으로만 빠진다 — 진행 스트림이 "곧 받는다"를 이것으로
        # 안다.
        self._active: set[str] = set()

    def request(self, scope: str) -> bool:
        """갱신을 요청한다. 받아들였으면 `True`. **동기 메서드다** — 검색 응답을 만들다가 부른다."""
        if scope in self._active:
            return False
        self._active.add(scope)
        self._queue.put_nowait(scope)
        return True

    async def pop(self) -> str:
        return await self._queue.get()

    def done(self, scope: str) -> None:
        self._active.discard(scope)

    def is_active(self, scope: str) -> bool:
        return scope in self._active


_queue: CryptoListQueue | None = None


def get_crypto_list_queue() -> CryptoListQueue:
    global _queue
    if _queue is None:
        _queue = CryptoListQueue()
    return _queue


def reset_crypto_list_queue() -> None:
    """테스트용. 앞 테스트의 요청이 남으면 뒤 테스트의 요청이 조용히 무시된다."""
    global _queue
    _queue = None
