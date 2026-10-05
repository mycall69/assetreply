"""자료별 하루 호출 수 (T006·T012) — 009 FR-012, SC-012, data-model 7절, research R9-5.

관문이 요청을 보내기 **전에** 1을 더하고, 설정 한도에 닿으면 보내지 않는다. DB에 세므로 프로세스를
다시 띄워도 이어 센다. 날짜는 한국 시간이다. 한도를 넘는 동시 요청이 와도 정확히 한도만큼만
통과한다(행 잠금).
"""
from __future__ import annotations

import asyncio
import datetime as dt

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.db.models import AptApiUsage
from src.repository.apt_usage import ApiUsageCounter

DAY = dt.date(2026, 10, 5)


async def calls(factory: async_sessionmaker[AsyncSession], api: str, day: dt.date) -> int | None:
    async with factory() as session:
        return (await session.execute(select(AptApiUsage.calls).where(
            AptApiUsage.api == api, AptApiUsage.kst_date == day))).scalar_one_or_none()


async def test_한도까지_세고_멈춘다(session_factory: async_sessionmaker[AsyncSession]) -> None:
    counter = ApiUsageCounter(session_factory)
    taken = [await counter.take("trade", DAY, 3) for _ in range(5)]
    assert taken == [True, True, True, False, False]
    assert await calls(session_factory, "trade", DAY) == 3


async def test_자료와_날짜마다_따로(session_factory: async_sessionmaker[AsyncSession]) -> None:
    counter = ApiUsageCounter(session_factory)
    assert await counter.take("trade", DAY, 1) is True
    assert await counter.take("trade", DAY, 1) is False
    assert await counter.take("kapt", DAY, 1) is True
    assert await counter.take("trade", DAY + dt.timedelta(days=1), 1) is True


async def test_다시_만든_계수기도_이어_센다(
        session_factory: async_sessionmaker[AsyncSession]) -> None:
    """프로세스를 다시 띄운 것과 같다 — 메모리가 아니라 DB에 센다."""
    await ApiUsageCounter(session_factory).take("region", DAY, 2)
    second = ApiUsageCounter(session_factory)
    assert await second.take("region", DAY, 2) is True
    assert await second.take("region", DAY, 2) is False


async def test_동시에_와도_한도만큼만(session_factory: async_sessionmaker[AsyncSession]) -> None:
    counter = ApiUsageCounter(session_factory)
    results = await asyncio.gather(*(counter.take("trade", DAY, 5) for _ in range(12)))
    assert results.count(True) == 5
    assert await calls(session_factory, "trade", DAY) == 5
