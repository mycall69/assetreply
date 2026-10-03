"""코인 목록 갱신 점유와 진행 (T017) — 007 FR-005b, data-model 3절.

**기본 키 INSERT 충돌이 곧 "이미 갱신 중"이다**(006 `stock_listing_lock`과 같은 수단). 점유 행은
진행도 담는다 — 갱신 줄이 쪽마다 판·받은 쪽 수·받은 코인 수를 적고, 진행 스트림이 프레임마다 읽는다.
끝나면 지운다 — 행이 없으면 갱신 중이 아니다. 지울 수 있는 것은 점유뿐이라 코인·원본
리포지토리(`crypto_coin.py`)와 나눈다.
"""

from __future__ import annotations

import datetime as dt
from typing import Final

from sqlalchemy import delete, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import CryptoListLock

#: 점유 범위. 두 판(`en`·`ko`)을 한 갱신이 함께 받으므로 하나다.
SCOPE: Final = "coins"


async def try_lock(session: AsyncSession, now: dt.datetime) -> bool:
    """점유를 잡는다. 잡으면 곧바로 커밋한다 — 커밋하지 않으면 다른 세션이 점유를 보지 못해 함께
    받는다."""
    session.add(CryptoListLock(scope=SCOPE, started_at=now, heartbeat_at=now,
                               pages_done=0, coins_seen=0))
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        return False
    return True


async def set_progress(
    session: AsyncSession, *, edition: str, pages_done: int, coins_seen: int, now: dt.datetime
) -> None:
    """진행을 적는다. 심장박동도 함께 고친다 — 쪽을 받는 동안은 정체가 아니다."""
    await session.execute(update(CryptoListLock).where(CryptoListLock.scope == SCOPE).values(
        edition=edition, pages_done=pages_done, coins_seen=coins_seen, heartbeat_at=now))


async def get_lock(session: AsyncSession) -> CryptoListLock | None:
    return await session.get(CryptoListLock, SCOPE, populate_existing=True)


async def release_lock(session: AsyncSession) -> None:
    await session.execute(delete(CryptoListLock).where(CryptoListLock.scope == SCOPE))


async def release_all_locks(session: AsyncSession) -> None:
    """기동 시 남은 점유를 푼다. 프로세스가 하나라 그 점유는 죽은 프로세스의 것이다."""
    await session.execute(delete(CryptoListLock))


async def reclaim_stale_lock(
    session: AsyncSession, now: dt.datetime, *, stale_after: dt.timedelta
) -> bool:
    """심장박동이 멈춘 점유를 회수한다. 회수하지 않으면 다시 갱신할 수 없고 화면은 영원히 "갱신
    중"이다."""
    result = await session.execute(delete(CryptoListLock).where(
        CryptoListLock.heartbeat_at < now - stale_after))
    return bool(getattr(result, "rowcount", 0))
