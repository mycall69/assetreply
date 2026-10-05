"""공공데이터포털 관문 — 네 자료가 함께 지나는 하나의 문 (009 T012, FR-012, SC-012, research R9-5).

실거래·법정동코드·단지 목록·기본 정보가 같은 포털·같은 인증키다. 줄(실거래 수집·목록 갱신·요청
경로)마다 따로 세면 **합친 호출을 아무도 보지 않아** 한도를 넘긴다 — 포털은 하루 한도를 넘긴 키를
막는다.

- **동시 요청 수**: 프로세스에서 동시에 나가는 요청을 `DATA_API_MAX_CONCURRENT`로 묶는다
- **자료별 하루 호출 수**: 요청을 보내기 **전에** 계수기(`UsageCounter` — DB 구현은
  `repository/apt_usage.py`)에 1을 더하고,
  설정 한도에 닿으면 보내지 않고 `DataGoKrRateLimited`다. 날짜는 한국 시간이다
- **포털의 한도 신호(사유 22)**: 클라이언트가 `block`을 부르면 그날 그 자료는 더 보내지 않는다(다른
  자료는 계속)

관문은 앱에 하나다(`api/main.py`가 만든다). asyncio의 동기화 객체는 처음 쓴 루프에 묶이므로 테스트는
루프마다 새로 만든다.
"""

from __future__ import annotations

import asyncio
import datetime as dt
from collections.abc import AsyncIterator, Callable, Mapping
from contextlib import asynccontextmanager
from typing import Protocol
from zoneinfo import ZoneInfo

from src.ingestion.datagokr.errors import DataGoKrRateLimited

_KST = ZoneInfo("Asia/Seoul")


def kst_today() -> dt.date:
    return dt.datetime.now(_KST).date()


class UsageCounter(Protocol):
    """자료별 하루 호출 수. 한도 안이면 1을 더하고 True, 닿았으면 그대로 두고 False."""

    async def take(self, api: str, day: dt.date, limit: int) -> bool: ...


class DataGoKrGate:
    def __init__(self, limit: int, counter: UsageCounter, limits: Mapping[str, int], *,
                 today: Callable[[], dt.date] = kst_today) -> None:
        self._slots = asyncio.Semaphore(limit)
        self._counter = counter
        self._limits = dict(limits)
        self._today = today
        self._blocked: set[tuple[str, dt.date]] = set()

    def block(self, api: str) -> None:
        """포털이 한도 초과(사유 22)를 알렸다 — 그날 그 자료는 더 보내지 않는다."""
        self._blocked.add((api, self._today()))

    @asynccontextmanager
    async def slot(self, api: str) -> AsyncIterator[None]:
        """요청 하나의 자리. 보내기 전에 하루 호출 수를 센다 — 실패한 요청도 센다."""
        day = self._today()
        if (api, day) in self._blocked:
            raise DataGoKrRateLimited(f"오늘 출처가 {api} 자료의 호출 한도 초과를 알렸습니다")
        limit = self._limits[api]
        if not await self._counter.take(api, day, limit):
            raise DataGoKrRateLimited(f"{api} 자료의 하루 호출 한도({limit:,}회)에 닿았습니다")
        async with self._slots:
            yield
