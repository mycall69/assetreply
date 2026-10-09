"""Yahoo 관문 — 주식(005)과 대시보드(014)가 함께 지나는 하나의 문 (014 T014, FR-019, research
R14-10).

같은 출처(비공식 엔드포인트)다. 클라이언트마다 세마포어를 따로 가지면 **합친 호출을 아무도 보지
않아**, 대시보드 수집이
주식 수집과 합쳐 출처 한도를 넘기고 둘 다 막힌다(008 `EcosGate`와 같은 까닭).

- **동시 요청 수**: 프로세스에서 동시에 나가는 Yahoo 요청을 `YAHOO_MAX_CONCURRENT_REQUESTS`로 묶는다
- **한도 신호 공유**: 누가 429를 받아 `pause`하면 그 백오프 동안 **모두의 다음 요청**이 기다린다

대기는 `asyncio.sleep`을 **호출 시점에** 찾아 부른다 — 계약 테스트가 대기를 가로챈다(`EcosGate`와
같다).
"""

from __future__ import annotations

import asyncio
import weakref
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from src.config.settings import Settings


class YahooGate:
    """동시 수 제한 + 한도 신호 공유 백오프."""

    def __init__(self, limit: int) -> None:
        self._slots = asyncio.Semaphore(limit)
        self._open = asyncio.Event()
        self._open.set()
        self._pauses = 0

    @asynccontextmanager
    async def slot(self) -> AsyncIterator[None]:
        """요청 하나의 자리. 한도 백오프 중이면 끝날 때까지 기다린다."""
        while not self._open.is_set():
            await self._open.wait()
        async with self._slots:
            yield

    async def pause(self, seconds: float) -> None:
        """429를 받은 쪽이 부른다 — 그 백오프 동안 관문 전체가 닫힌다."""
        self._pauses += 1
        self._open.clear()
        try:
            await asyncio.sleep(seconds)
        finally:
            self._pauses -= 1
            if self._pauses == 0:
                self._open.set()


# 이벤트 루프마다 하나다 — asyncio의 동기화 객체는 처음 쓴 루프에 묶인다. 앱은 루프가 하나라 사실상
# 프로세스에 하나이고,
# 테스트는 루프마다 새 관문을 받는다.
_GATES: weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, YahooGate] = (
    weakref.WeakKeyDictionary()
)


def get_yahoo_gate(settings: Settings) -> YahooGate:
    """지금 루프의 관문. 처음 부른 쪽의 설정으로 만든다."""
    loop = asyncio.get_running_loop()
    gate = _GATES.get(loop)
    if gate is None:
        gate = YahooGate(settings.yahoo_max_concurrent_requests)
        _GATES[loop] = gate
    return gate
