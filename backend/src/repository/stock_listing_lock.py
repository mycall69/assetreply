"""검색용 목록 갱신 점유 (T034) — 006 FR-014, data-model 3절.

**기본 키 INSERT 충돌이 곧 "이미 갱신 중"이다**(헌법 DB 운영 규약). 점유는 끝나면 지워야 하는 것이라
종목·원본 리포지토리(`stock_listing.py`)와 나눈다 — 그 파일에는 삭제 질의가 없어야 한다(tasks T083).
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import StockListingLock


async def try_lock(session: AsyncSession, unit: str, now: dt.datetime) -> bool:
    """점유를 잡는다. **기본 키 충돌이 곧 "이미 갱신 중"이다.** 잡으면 곧바로 커밋한다 — 커밋하지
    않으면 다른 세션이 점유를 보지 못해 같은 단위를 함께 받는다."""
    session.add(StockListingLock(unit=unit, started_at=now, heartbeat_at=now))
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        return False
    return True


async def heartbeat(session: AsyncSession, unit: str, now: dt.datetime) -> None:
    await session.execute(update(StockListingLock).where(
        StockListingLock.unit == unit).values(heartbeat_at=now))


async def release_lock(session: AsyncSession, unit: str) -> None:
    await session.execute(delete(StockListingLock).where(StockListingLock.unit == unit))


async def release_all_locks(session: AsyncSession) -> None:
    """기동 시 남은 점유를 푼다. 프로세스가 하나라 그 점유는 죽은 프로세스의 것이다."""
    await session.execute(delete(StockListingLock))


async def reclaim_stale_locks(
    session: AsyncSession, now: dt.datetime, *, stale_after: dt.timedelta
) -> list[str]:
    """심장박동이 멈춘 점유를 회수한다. 회수하지 않으면 그 단위는 다시 갱신할 수 없다."""
    cutoff = now - stale_after
    stale = list((await session.execute(select(StockListingLock.unit).where(
        StockListingLock.heartbeat_at < cutoff).order_by(StockListingLock.unit))).scalars())
    if stale:
        await session.execute(delete(StockListingLock).where(StockListingLock.unit.in_(stale)))
    return stale


async def locked_units(session: AsyncSession) -> set[str]:
    return set((await session.execute(select(StockListingLock.unit))).scalars())
