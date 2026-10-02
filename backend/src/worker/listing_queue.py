"""목록 갱신 요청 큐 (T036) — 006 FR-014, FR-017, research R6-3.

검색은 여기에 단위를 넣고 **곧바로 답한다** — 갱신을 기다리면 그날 첫 검색이 수 분 걸린다(FR-017).
실제 갱신은 목록 갱신 워커가 꺼내 돌린다.

**단위로 중복을 거른다.** 이것은 비용 절약이고 정합성의 근거는 DB 점유다(FR-014). 주식 수집 큐와
같은 모양이며 섞지 않는다 — 출처가 달라 호출 한도도 따로다.
"""

from __future__ import annotations

import asyncio


class ListingQueue:
    """갱신 요청을 워커로 넘기는 통로."""

    __slots__ = ("_queue", "_active")

    def __init__(self) -> None:
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        # 대기 중이거나 처리 중인 단위. `done()`으로만 빠진다.
        self._active: set[str] = set()

    def request(self, unit: str) -> bool:
        """갱신을 요청한다. 받아들였으면 `True`, 이미 대기·처리 중이면 `False`.

        **동기 메서드다.** 검색 응답을 만들다가 부르므로 기다릴 일이 없어야 한다.
        """
        if unit in self._active:
            return False
        self._active.add(unit)
        self._queue.put_nowait(unit)
        return True

    async def pop(self) -> str:
        return await self._queue.get()

    def done(self, unit: str) -> None:
        self._active.discard(unit)

    @property
    def size(self) -> int:
        return self._queue.qsize()

    def is_active(self, unit: str) -> bool:
        return unit in self._active


_queue: ListingQueue | None = None


def get_listing_queue() -> ListingQueue:
    global _queue
    if _queue is None:
        _queue = ListingQueue()
    return _queue


def reset_listing_queue() -> None:
    """테스트용. 앞 테스트의 요청이 남으면 뒤 테스트의 요청이 조용히 무시된다."""
    global _queue
    _queue = None
