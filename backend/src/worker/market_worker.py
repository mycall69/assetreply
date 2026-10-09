"""대시보드 지표 수집 워커 (014 T055) — FR-019, research R14-11.

`lifespan`의 아홉째 태스크다. **다른 자산군 워커와 따로다** — 대시보드 수집이 주식·외환 수집을 막지
않는다(CLAUDE.md의 자산군별
워커 원칙). 같은 Yahoo 출처의 한도는 관문이 함께 지킨다(R14-10).

- `MARKET_COLLECT_INTERVAL_SECONDS`(기본 30분)마다 깨어 한 바퀴를 돈다. 받은 청크가 있으면 곧바로
  다음 바퀴를 돈다(처음 과거
  구간을 이어서 받는다) — 이 사이클에 실패한 지표는 건너뛴다(같은 실패를 되풀이해 출처를 두드리지
  않는다)
- "다시 시도"(`POST …/collect`)가 깨우기 이벤트로 곧바로 한 바퀴를 돌린다
- **한 지표의 실패가 루프를 끝내지 않는다**
- 출처 클라이언트는 `lifespan`이 열고 닫는다 — 현재 시세 서비스와 함께 쓴다
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
from src.worker.market_runner import MarketSource, run_round, utc_now

_log = logging.getLogger(__name__)

# 이벤트 루프마다 하나다 — asyncio의 동기화 객체는 처음 쓴 루프에 묶인다(관문과 같다).
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
    """워커를 곧바로 깨운다(다시 시도 — FR-016)."""
    wake_event().set()


async def market_worker_loop(
    factory: async_sessionmaker[AsyncSession],
    source: MarketSource,
    *,
    settings: Settings,
    clock: Callable[[], dt.datetime] = utc_now,
) -> None:
    """앱 수명과 함께 산다. 취소되면 끝난다."""
    event = wake_event()
    skip: set[str] = set()
    while True:
        try:
            result = await run_round(factory, source, settings=settings, now=clock(), skip=skip)
        except asyncio.CancelledError:
            raise
        except Exception:  # pragma: no cover — run_round가 지표마다 삼킨다. DB가 끊긴 경우 등
            _log.exception("대시보드 지표 수집 바퀴 오류")
            result = None
        if result is not None and result.succeeded > 0:
            skip |= result.failed
            continue
        skip.clear()
        # 바퀴 도중에 온 깨우기는 잃지 않는다 — 이미 켜져 있으면 기다리지 않고 곧바로 돈다.
        if not event.is_set():
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(
                    event.wait(), timeout=settings.market_collect_interval_seconds
                )
        event.clear()
