"""잠금 범위 분리 (T056) — FR-036a, research R2-8.

대량 수집이 도는 동안 오늘 새로고침이 막히면, 오늘 환율을 보려는 사용자가 몇 분을
기다려야 해서 이 기능을 만든 이유가 사라진다. 두 작업의 대상 구간이 겹치지 않으므로
(수집은 어제까지, 새로고침은 오늘만) 서로를 막을 이유가 없다.
"""
from __future__ import annotations

import datetime as dt

from sqlalchemy import func, select

from src.db.models import FxCollectionLock
from src.repository.collection_lock import (
    SCOPE_COLLECTION,
    SCOPE_TODAY_REFRESH,
    acquire_lock,
    release_lock,
)
from src.repository.job import create_job


async def _job(session, currency: str = "USD") -> int:
    """작업 생성은 리포지토리에 맡긴다 — 필수 필드가 늘어도 테스트가 따라간다."""
    job = await create_job(
        session, currency, dt.date(2026, 8, 1), dt.date(2026, 8, 29), chunks_total=1)
    return job.id


async def test_수집과_새로고침_잠금이_공존한다(session_factory) -> None:
    async with session_factory() as s:
        job = await _job(s)
        assert await acquire_lock(s, "USD", job, scope=SCOPE_COLLECTION) is None
        # 같은 통화인데도 새로고침 잠금이 잡혀야 한다 (FR-036a)
        assert await acquire_lock(s, "USD", job, scope=SCOPE_TODAY_REFRESH) is None
        await s.commit()
        count = (await s.execute(
            select(func.count()).select_from(FxCollectionLock))).scalar_one()
    assert count == 2


async def test_같은_범위에서는_하나만_실행된다(session_factory) -> None:
    """FR-036b — 새로고침끼리는 여전히 하나만."""
    async with session_factory() as s:
        job = await _job(s)
        assert await acquire_lock(s, "USD", job, scope=SCOPE_TODAY_REFRESH) is None
        await s.commit()
    async with session_factory() as s:
        job2 = await _job(s)
        existing = await acquire_lock(s, "USD", job2, scope=SCOPE_TODAY_REFRESH)
    assert existing == job


async def test_한_범위의_해제가_다른_범위를_건드리지_않는다(session_factory) -> None:
    async with session_factory() as s:
        job = await _job(s)
        await acquire_lock(s, "USD", job, scope=SCOPE_COLLECTION)
        await acquire_lock(s, "USD", job, scope=SCOPE_TODAY_REFRESH)
        await s.commit()

        await release_lock(s, "USD", scope=SCOPE_TODAY_REFRESH)
        await s.commit()
        remaining = list((await s.execute(select(FxCollectionLock))).scalars())

    assert [r.scope for r in remaining] == [SCOPE_COLLECTION]


async def test_다른_통화는_서로를_막지_않는다(session_factory) -> None:
    """001의 FR-015c가 그대로 유지되는지."""
    async with session_factory() as s:
        usd = await _job(s, "USD")
        jpy = await _job(s, "JPY")
        assert await acquire_lock(s, "USD", usd, scope=SCOPE_TODAY_REFRESH) is None
        assert await acquire_lock(s, "JPY", jpy, scope=SCOPE_TODAY_REFRESH) is None
