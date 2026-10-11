"""기준금리 수집 워커 (014 반복 2026-10-11d T207) — FR-043, research R14-32.

`lifespan`의 열째 태스크다. **다른 수집 워커와 따로다** — 출처(네이버 증권)가 대시보드
지표(Yahoo)와 달라 한쪽이 막혀도 다른 쪽이
기다리지 않는다(CLAUDE.md의 자산군별 워커 원칙).

- `POLICY_RATE_COLLECT_INTERVAL_SECONDS`(기본 30분)마다 깨어 한 바퀴를 돈다 — 목록 한 번, 할 일이
  있는 은행만 결정 이력
- [다시 시도](`POST /api/dashboard/rates/collect`)가 깨우기 이벤트로 곧바로 한 바퀴를 돌린다
- **한 바퀴의 오류가 루프를 끝내지 않는다**
- 출처 클라이언트는 `lifespan`이 열고 닫는다
"""

from __future__ import annotations

import asyncio
import contextlib
import datetime as dt
import logging
import weakref
from collections.abc import Callable

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.config.settings import Settings
from src.worker.policy_rate_runner import PolicyRateSource, run_round, utc_now

_log = logging.getLogger(__name__)

# 이벤트 루프마다 하나다 — asyncio의 동기화 객체는 처음 쓴 루프에 묶인다(지표 워커와 같다).
_EVENTS: weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, asyncio.Event] = (
    weakref.WeakKeyDictionary()
)


def wake_event() -> asyncio.Event:
    """지금 루프의 깨우기 이벤트."""
    loop = asyncio.get_running_loop()
    event = _EVENTS.get(loop)
    if event is None:
        event = asyncio.Event()
        _EVENTS[loop] = event
    return event


def wake() -> None:
    """워커를 곧바로 깨운다(다시 시도 — spec FR-040)."""
    wake_event().set()


async def policy_rate_worker_loop(
    factory: async_sessionmaker[AsyncSession],
    source: PolicyRateSource,
    *,
    settings: Settings,
    clock: Callable[[], dt.datetime] = utc_now,
) -> None:
    """앱 수명과 함께 산다. 취소되면 끝난다."""
    event = wake_event()
    while True:
        try:
            await run_round(factory, source, settings=settings, now=clock())
        except asyncio.CancelledError:
            raise
        except Exception:  # pragma: no cover — run_round가 은행마다 삼킨다. DB가 끊긴 경우 등
            _log.exception("기준금리 수집 바퀴 오류")
        # 바퀴 도중에 온 깨우기는 잃지 않는다 — 이미 켜져 있으면 기다리지 않고 곧바로 돈다.
        if not event.is_set():
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(
                    event.wait(), timeout=settings.policy_rate_collect_interval_seconds
                )
        event.clear()
