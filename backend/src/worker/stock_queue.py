"""주식 수집 요청 큐 (T093) — 005 FR-047, FR-048, research R5-7.

HTTP 요청은 여기에 일감을 넣고 곧바로 202를 돌려준다. 실제 수집은 워커 태스크가
꺼내 돌린다 — **그래서 요청 연결이 끊겨도 수집이 이어진다**.

**FX 큐와 분리한다.** 출처가 다르므로 호출 한도도 따로다. 한 큐에 섞으면 환율 수집이
주식 수집을 막고, 그 이유가 화면 어디에도 드러나지 않는다 (research R5-7).

**종목 단위로 중복을 거른다.** DB 점유가 실행 자체는 막지만, 그 확인에도 세션이 들고
큐만 무의미하게 길어진다.
"""

from __future__ import annotations

import asyncio
import datetime as dt
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class StockWork:
    """수집 일감 하나. 작업 ID까지 들고 다녀야 워커가 진행을 기록할 수 있다."""

    job_id: int
    stock_id: int
    symbol: str
    start: dt.date
    end: dt.date


class StockQueue:
    """수집 시작 요청을 워커로 넘기는 통로."""

    __slots__ = ("_queue", "_active")

    def __init__(self) -> None:
        self._queue: asyncio.Queue[StockWork] = asyncio.Queue()
        # 대기 중이거나 처리 중인 종목. `done()`으로만 빠진다.
        self._active: set[int] = set()

    def request(self, work: StockWork) -> bool:
        """시작을 요청한다. 받아들였으면 `True`, 이미 진행 중이면 `False`.

        **동기 메서드다.** 라우트가 응답을 만들다가 부르므로 기다릴 일이 없어야 한다.
        """
        if work.stock_id in self._active:
            return False
        self._active.add(work.stock_id)
        self._queue.put_nowait(work)
        return True

    async def pop(self) -> StockWork:
        """다음 일감을 꺼낸다. 없으면 도착할 때까지 기다린다.

        꺼내도 `_active`에서 빠지지 않는다 — 처리가 끝날 때까지 중복 요청을 막아야
        한다. 해제는 `done()`이 한다.
        """
        return await self._queue.get()

    def done(self, stock_id: int) -> None:
        """처리 완료를 알린다. 이후 같은 종목을 다시 요청할 수 있다."""
        self._active.discard(stock_id)

    @property
    def size(self) -> int:
        return self._queue.qsize()

    def is_active(self, stock_id: int) -> bool:
        return stock_id in self._active


#: 애플리케이션 전역 큐. `lifespan`이 워커를 띄우고 라우트가 여기에 일감을 넣는다.
_queue: StockQueue | None = None


def get_stock_queue() -> StockQueue:
    global _queue
    if _queue is None:
        _queue = StockQueue()
    return _queue


def reset_stock_queue() -> None:
    """테스트용. 전역 상태가 테스트 사이에 새지 않게 한다."""
    global _queue
    _queue = None
