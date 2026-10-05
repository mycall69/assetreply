"""부동산 수집 요청 큐 둘 — 실거래·목록 (009 T024, FR-011, FR-012).

HTTP 요청은 여기에 일감을 넣고 곧바로 202·200을 돌려준다. 실제 수집은 부동산 수집 태스크의 두 줄이
꺼내 돌린다 — 요청 연결이 끊겨도 수집이 이어진다. **실거래 줄과 목록 줄의 큐를 나눈다** — 시·군·구
전체 이력(약 280회)이 행정구역 갱신·기본 정보 채우기를 막지 않는다(006 목록 갱신 워커가
국내·미국으로 나뉜 것과 같다). 같은 (종류, 대상)은 한 번만 들어간다 — 중복 수집은 DB 점유가 막고,
큐는 같은 일감이 두 번 줄 서는 것을 막는다.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AptWork:
    """수집 일감 하나. `kind`는 `trade`·`region`·`complex_details`, `target`은 시·군·구
    5자리·`regions`· 법정동 10자리다(data-model 6절)."""

    job_id: int
    kind: str
    target: str


class AptQueue:
    __slots__ = ("_queue", "_active")

    def __init__(self) -> None:
        self._queue: asyncio.Queue[AptWork] = asyncio.Queue()
        self._active: set[tuple[str, str]] = set()

    def request(self, work: AptWork) -> bool:
        """시작을 요청한다. 받아들였으면 `True`. **동기 메서드다** — 라우트가 응답을 만들다가
        부른다."""
        key = (work.kind, work.target)
        if key in self._active:
            return False
        self._active.add(key)
        self._queue.put_nowait(work)
        return True

    async def pop(self) -> AptWork:
        return await self._queue.get()

    def done(self, kind: str, target: str) -> None:
        self._active.discard((kind, target))

    def is_active(self, kind: str, target: str) -> bool:
        return (kind, target) in self._active


_trade: AptQueue | None = None
_list: AptQueue | None = None


def get_apt_trade_queue() -> AptQueue:
    global _trade
    if _trade is None:
        _trade = AptQueue()
    return _trade


def get_apt_list_queue() -> AptQueue:
    global _list
    if _list is None:
        _list = AptQueue()
    return _list


def queue_for(kind: str) -> AptQueue:
    """일감 종류의 큐 — 실거래는 실거래 줄, 행정구역·기본 정보는 목록 줄."""
    return get_apt_trade_queue() if kind == "trade" else get_apt_list_queue()


def reset_apt_queues() -> None:
    """테스트용. 앞 테스트의 요청이 남으면 뒤 테스트의 요청이 조용히 무시된다."""
    global _trade, _list
    _trade = None
    _list = None
