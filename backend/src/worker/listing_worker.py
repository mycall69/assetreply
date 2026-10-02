"""목록 갱신 워커 (T036) — 006 FR-013, FR-014, data-model 3절, research R6-3.

**앱 수명과 함께 산다.** `lifespan`에 등록하지 않으면 갱신 요청이 큐에 쌓이기만 하고 실행되지 않는다
— 003·005가 겪은 일이다. 화면에는 "받는 중"이 영원히 남는다.

**기동 시 점유를 푼다.** 프로세스가 하나다(CLAUDE.md "단일 워커"). 기동 시점에 남은 점유는 죽은
프로세스의 것이고, 풀지 않으면 그 단위는 다시 갱신할 수 없다.

**클라이언트 하나를 수명 내내 쓴다.** 토큰을 메모리에 두고 만료 10분 전에 갱신하므로, 단위마다 새로
만들면 토큰을 매번 다시 받는다.

**국내와 미국을 두 줄로 나눈다**(T068). 미국 목록은 분당 5회 제한 때문에 쪽 사이에 12초씩 쉰다. 한
줄로 처리하면 미국이 한도에 걸려 오래 걸리는 동안 국내 갱신이 그 뒤에 줄 서고, 국내 종목까지 그날 첫
검색이 늦어진다. 줄 안에서는 차례대로 한다 — 같은 출처 API를 동시에 두드리지 않는다.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.api.services.listing_refresh import ListingSource, refresh_unit
from src.config.settings import Settings
from src.ingestion.kiwoom.client import US_UNITS
from src.repository import stock_listing_lock as locks
from src.worker.listing_queue import ListingQueue

_log = logging.getLogger(__name__)


async def startup(session_factory: async_sessionmaker[AsyncSession]) -> None:
    """기동 시 남은 점유를 모두 푼다."""
    async with session_factory() as session:
        await locks.release_all_locks(session)
        await session.commit()


async def _lane(
    session_factory: async_sessionmaker[AsyncSession],
    source: ListingSource,
    queue: ListingQueue,
    lane: asyncio.Queue[str],
    settings: Settings,
) -> None:
    """한 줄의 단위를 차례로 갱신한다. **한 건이 실패해도 줄을 끝내지 않는다.**"""
    while True:
        unit = await lane.get()
        try:
            await refresh_unit(session_factory, source, unit, settings=settings)
        except asyncio.CancelledError:
            raise
        except Exception:  # pragma: no cover — refresh_unit이 실패를 기록하고 삼킨다
            _log.exception("목록 갱신 루프 오류 unit=%s", unit)
        finally:
            queue.done(unit)


async def listing_worker_loop(
    session_factory: async_sessionmaker[AsyncSession],
    source: ListingSource,
    queue: ListingQueue,
    *,
    settings: Settings,
) -> None:
    """큐에서 단위를 꺼내 국내·미국 줄로 나눠 넘긴다. 앱 수명과 함께 산다."""
    domestic: asyncio.Queue[str] = asyncio.Queue()
    us: asyncio.Queue[str] = asyncio.Queue()
    lanes = [asyncio.create_task(_lane(session_factory, source, queue, lane, settings))
             for lane in (domestic, us)]
    try:
        while True:
            unit = await queue.pop()
            (us if unit in US_UNITS else domestic).put_nowait(unit)
    finally:
        for task in lanes:
            task.cancel()
        for task in lanes:
            with contextlib.suppress(asyncio.CancelledError):
                await task
