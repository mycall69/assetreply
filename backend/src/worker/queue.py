"""시작 요청 큐 (T021) — research R3-1, FR-003, FR-004.

HTTP 요청은 여기에 통화를 넣고 곧바로 202를 돌려준다. 실제 수집은 워커 태스크가 큐에서
꺼내 돌린다. **그래서 요청 연결이 끊겨도 수집이 이어진다** (FR-001).

중복 요청을 큐 단계에서 거른다. DB 점유가 실행 자체는 막지만, 그 확인에도 비용이 들고
큐가 무의미하게 길어진다.
"""

from __future__ import annotations

import asyncio


class StartQueue:
    """수집 시작 요청을 워커로 넘기는 통로.

    `single_currency=True`면 한 번에 한 통화만 받는다 (FR-004, 2026-09-24 반복).
    다른 통화가 대기·진행 중이면 요청을 거절하고, 호출자는 `in_progress`로 어느 통화가
    돌고 있는지 알아내 사용자에게 알린다 (FR-029).
    """

    __slots__ = ("_queue", "_active", "_single")

    def __init__(self, *, single_currency: bool = True) -> None:
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        # 대기 중이거나 처리 중인 통화. `done()`으로만 빠진다.
        self._active: list[str] = []
        self._single = single_currency

    async def request(self, currency: str) -> bool:
        """시작을 요청한다. 받아들였으면 `True`, 거절했으면 `False`.

        거절 사유는 두 가지다 — 같은 통화가 이미 진행 중이거나(FR-003), 단일 통화
        모드에서 다른 통화가 돌고 있거나(FR-004). 둘 다 큐에 쌓지 않는다.
        """
        if currency in self._active:
            return False
        if self._single and self._active:
            return False
        self._active.append(currency)
        await self._queue.put(currency)
        return True

    async def pop(self) -> str:
        """다음 요청을 꺼낸다. 없으면 도착할 때까지 기다린다.

        꺼내도 `_active`에서 빠지지 않는다 — 처리가 끝날 때까지 중복 요청을 막아야
        하기 때문이다. 해제는 `done()`이 한다.
        """
        return await self._queue.get()

    def done(self, currency: str) -> None:
        """처리 완료를 알린다. 이후 같은 통화를 다시 요청할 수 있다."""
        if currency in self._active:
            self._active.remove(currency)

    @property
    def size(self) -> int:
        """대기 중인 요청 수."""
        return self._queue.qsize()

    @property
    def in_progress(self) -> str | None:
        """진행 중이거나 곧 진행될 통화. 없으면 `None` (FR-029)."""
        return self._active[0] if self._active else None


#: 애플리케이션 전역 큐. `lifespan`이 워커를 띄우고 라우트가 여기에 요청을 넣는다.
_queue: StartQueue | None = None


def get_queue() -> StartQueue:
    """전역 큐를 얻는다. 없으면 만든다."""
    global _queue
    if _queue is None:
        _queue = StartQueue()
    return _queue


def reset_queue() -> None:
    """테스트용. 전역 상태가 테스트 사이에 새지 않게 한다."""
    global _queue
    _queue = None
