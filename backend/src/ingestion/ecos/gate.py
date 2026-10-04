"""ECOS 관문 — 환율(001)과 예금 금리(008)가 함께 지나는 하나의 문 (008 T010, FR-013, research R8-6).

같은 출처·같은 인증키다. 클라이언트마다 세마포어를 따로 가지면 **합친 호출을 아무도 보지 않아**,
한쪽이 한도에 걸려도 다른 쪽이 계속 불러 둘 다 막힌다(약관 제6조 ① 4 — 과다 호출이면 서비스를 중단할
수 있다).

- **동시 요청 수**: 프로세스에서 동시에 나가는 ECOS 요청을 `ECOS_MAX_CONCURRENT_REQUESTS`로 묶는다
- **한도 신호 공유**: 누가 `INFO-300`을 받으면 그 백오프 동안 **모두의 다음 요청**이 기다린다

한도 신호가 없으면 서로 기다리지 않는다 — 줄(워커)은 따로다. 대기는 `asyncio.sleep`을 **호출
시점에** 찾아 부른다 — 계약 테스트가 대기를 가로채 백오프 간격을 검사한다(001과 같다).
"""

from __future__ import annotations

import asyncio
import weakref
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from src.config.settings import Settings


class EcosGate:
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
        """한도 초과를 받은 쪽이 부른다 — 그 백오프 동안 관문 전체가 닫힌다."""
        self._pauses += 1
        self._open.clear()
        try:
            await asyncio.sleep(seconds)
        finally:
            self._pauses -= 1
            if self._pauses == 0:
                self._open.set()


# 이벤트 루프마다 하나다 — asyncio의 동기화 객체는 처음 쓴 루프에 묶인다. 앱은 루프가 하나라 사실상
# 프로세스에 하나이고, 테스트는 루프마다 새 관문을 받는다.
_GATES: weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, EcosGate] = (
    weakref.WeakKeyDictionary())


def get_gate(settings: Settings) -> EcosGate:
    """지금 루프의 관문. 처음 부른 쪽의 설정으로 만든다."""
    loop = asyncio.get_running_loop()
    gate = _GATES.get(loop)
    if gate is None:
        gate = EcosGate(settings.ecos_max_concurrent_requests)
        _GATES[loop] = gate
    return gate
