"""자료별 하루 호출 수 (009 T012, FR-012, SC-012, data-model 7절).

관문(`ingestion/datagokr/gate.py`)의 `UsageCounter`를 DB로 구현한다 — 프로세스를 다시 띄워도 이어
센다. 한도 안이면 1을 더하고 True, 닿았으면 그대로 두고 False. **동시 요청이 와도 한도만큼만
통과한다** — `calls < limit` 조건의 UPDATE가 행 잠금으로 하나씩 처리된다.

그날 첫 요청은 행이 없다. 단계마다 **트랜잭션을 나눈다** — 없는 행에 UPDATE한 같은 트랜잭션에서
INSERT하면, 동시에 들어온 요청들이 서로의 간격 잠금을 기다리며 교착한다(InnoDB 1213 — 구현 중 실측).
그래도 교착이 나면 짧게 다시 시도한다.
"""

from __future__ import annotations

import asyncio
import datetime as dt
from typing import Final, cast

from sqlalchemy import CursorResult, update
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.db.models import AptApiUsage

#: 교착(1213)·잠금 대기 초과(1205) — 다시 시도하면 풀린다.
_RETRYABLE_CODES: Final = frozenset({1205, 1213})
_ATTEMPTS: Final = 5


def _retryable(exc: OperationalError) -> bool:
    args: tuple[object, ...] = tuple(getattr(exc.orig, "args", ()))
    return len(args) > 0 and args[0] in _RETRYABLE_CODES


class ApiUsageCounter:
    def __init__(self, factory: async_sessionmaker[AsyncSession]) -> None:
        self._factory = factory

    async def _increment(self, api: str, day: dt.date, limit: int) -> bool:
        async with self._factory() as session:
            result = cast(CursorResult[tuple[()]], await session.execute(
                update(AptApiUsage)
                .where(AptApiUsage.api == api, AptApiUsage.kst_date == day,
                       AptApiUsage.calls < limit)
                .values(calls=AptApiUsage.calls + 1)))
            await session.commit()
            return result.rowcount == 1

    async def _exists(self, api: str, day: dt.date) -> bool:
        async with self._factory() as session:
            return await session.get(AptApiUsage, (api, day)) is not None

    async def _insert_first(self, api: str, day: dt.date) -> bool:
        """그날 첫 호출. 다른 요청이 먼저 넣었으면(기본 키 충돌) False."""
        async with self._factory() as session:
            session.add(AptApiUsage(api=api, kst_date=day, calls=1))
            try:
                await session.commit()
                return True
            except IntegrityError:
                await session.rollback()
                return False

    async def _take_once(self, api: str, day: dt.date, limit: int) -> bool:
        if await self._increment(api, day, limit):
            return True
        if limit < 1 or await self._exists(api, day):
            return False  # 행이 있는데 늘지 않았다 — 한도에 닿았다
        if await self._insert_first(api, day):
            return True
        return await self._increment(api, day, limit)  # 다른 요청이 먼저 넣은 행에 더한다

    async def take(self, api: str, day: dt.date, limit: int) -> bool:
        for attempt in range(_ATTEMPTS):
            try:
                return await self._take_once(api, day, limit)
            except OperationalError as exc:
                if not _retryable(exc) or attempt + 1 == _ATTEMPTS:
                    raise
                await asyncio.sleep(0.01 * (attempt + 1))
        raise AssertionError("다시 시도 횟수 안에서 끝난다")
