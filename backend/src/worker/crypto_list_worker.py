"""코인 목록 갱신 줄 (T018) — 007 FR-005, research R7-11.

**앱 수명과 함께 산다.** `lifespan`에 등록하지 않으면 갱신 요청이 큐에 쌓이기만 하고 실행되지 않는다
— 003·005가 겪은 일이다. **시세 수집과 다른 줄이다** — 목록(약 74요청, 2분)이 끝날 때까지 시세
수집이 멈추지 않게 한다. 두 줄은 같은 출처 클라이언트(간격 제한기)를 함께 쓴다.

**기동 시 점유를 푼다.** 프로세스가 하나다(CLAUDE.md "단일 워커") — 기동 시점에 남은 점유는 죽은
프로세스의 것이다.
"""

from __future__ import annotations

import asyncio
import logging

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.api.services.crypto_list_refresh import CoinListSource, refresh_coins
from src.config.settings import Settings
from src.repository import crypto_list_lock as locks
from src.worker.crypto_list_queue import CryptoListQueue

_log = logging.getLogger(__name__)


async def startup(session_factory: async_sessionmaker[AsyncSession]) -> None:
    """기동 시 남은 점유를 푼다."""
    async with session_factory() as session:
        await locks.release_all_locks(session)
        await session.commit()


async def crypto_list_worker_loop(
    session_factory: async_sessionmaker[AsyncSession],
    source: CoinListSource,
    queue: CryptoListQueue,
    *,
    settings: Settings,
) -> None:
    """큐에서 요청을 꺼내 갱신한다. **한 번 실패해도 줄을 끝내지 않는다.**"""
    while True:
        scope = await queue.pop()
        try:
            await refresh_coins(session_factory, source, settings=settings)
        except asyncio.CancelledError:
            raise
        except Exception:  # pragma: no cover — refresh_coins가 실패를 기록하고 삼킨다
            _log.exception("코인 목록 갱신 줄 오류")
        finally:
            queue.done(scope)
