"""목록 갱신 워커 (T036) — 006 FR-013, FR-014, data-model 3절, research R6-3.

**앱 수명과 함께 산다.** `lifespan`에 등록하지 않으면 갱신 요청이 큐에 쌓이기만 하고 실행되지 않는다
— 003·005가 겪은 일이다. 화면에는 "받는 중"이 영원히 남는다.

**기동 시 점유를 푼다.** 프로세스가 하나다(CLAUDE.md "단일 워커"). 기동 시점에 남은 점유는 죽은
프로세스의 것이고, 풀지 않으면 그 단위는 다시 갱신할 수 없다.

**클라이언트 하나를 수명 내내 쓴다.** 토큰을 메모리에 두고 만료 10분 전에 갱신하므로, 단위마다 새로
만들면 토큰을 매번 다시 받는다.
"""

from __future__ import annotations

import asyncio
import logging

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.api.services.listing_refresh import ListingSource, refresh_unit
from src.config.settings import Settings
from src.repository import stock_listing as repo
from src.worker.listing_queue import ListingQueue

_log = logging.getLogger(__name__)


async def startup(session_factory: async_sessionmaker[AsyncSession]) -> None:
    """기동 시 남은 점유를 모두 푼다."""
    async with session_factory() as session:
        await repo.release_all_locks(session)
        await session.commit()


async def listing_worker_loop(
    session_factory: async_sessionmaker[AsyncSession],
    source: ListingSource,
    queue: ListingQueue,
    *,
    settings: Settings,
) -> None:
    """큐에서 단위를 꺼내 갱신한다. **한 건이 실패해도 루프를 끝내지 않는다.**"""
    while True:
        unit = await queue.pop()
        try:
            await refresh_unit(session_factory, source, unit, settings=settings)
        except asyncio.CancelledError:
            raise
        except Exception:  # pragma: no cover — refresh_unit이 실패를 기록하고 삼킨다
            _log.exception("목록 갱신 루프 오류 unit=%s", unit)
        finally:
            queue.done(unit)
