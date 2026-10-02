"""목록 갱신 점유 (T020) — 006 FR-014, SC-005, data-model 3절.

**중복 차단은 DB 점유로 한다.** 기본 키 충돌이 곧 "이미 갱신 중"이다(헌법 DB 운영 규약). 두 번
받으면 오류 없이 호출 한도를 두 배로 쓰고, 미국 목록은 분당 제한에 걸려 둘 다 실패할 수 있다.
"""
from __future__ import annotations

import asyncio
import datetime as dt

import pytest
from sqlalchemy import select
from src.api.services.listing_refresh import AuthBlocker, refresh_unit
from src.worker.listing_worker import startup

from src.db.models import StockListingLock
from src.repository import stock_listing as repo
from tests.integration.listing_support import (
    KOSPI_ROWS,
    NOW,
    StubListingSource,
    kr_body,
    listing_settings,
    page,
    reset_listing_state,
)


@pytest.fixture(autouse=True)
def _listing_state():
    reset_listing_state()
    yield
    reset_listing_state()


async def locks(session_factory) -> list[str]:  # type: ignore[no-untyped-def]
    async with session_factory() as s:
        return list((await s.execute(select(StockListingLock.unit))).scalars())


class Test기본_키_점유:
    async def test_같은_단위는_하나만_잡는다(self, session_factory) -> None:
        async with session_factory() as s:
            assert await repo.try_lock(s, "KOSPI", NOW) is True
        async with session_factory() as s:
            assert await repo.try_lock(s, "KOSPI", NOW) is False
        async with session_factory() as s:
            # 다른 단위는 막지 않는다 — 한 시장의 갱신이 다른 시장을 기다릴 이유가 없다.
            assert await repo.try_lock(s, "KOSDAQ", NOW) is True
        assert sorted(await locks(session_factory)) == ["KOSDAQ", "KOSPI"]

    async def test_풀면_다시_잡을_수_있다(self, session_factory) -> None:
        async with session_factory() as s:
            assert await repo.try_lock(s, "KOSPI", NOW)
        async with session_factory() as s:
            await repo.release_lock(s, "KOSPI")
            await s.commit()
        async with session_factory() as s:
            assert await repo.try_lock(s, "KOSPI", NOW)


class Test동시_갱신:
    async def test_동시에_둘을_요청해도_한_번만_받는다(self, session_factory) -> None:
        """FR-014, SC-005."""
        source = StubListingSource({"KOSPI": [[page(kr_body(KOSPI_ROWS))]] * 2})
        source.gate = asyncio.Event()
        settings, blocker = listing_settings(), AuthBlocker()

        first = asyncio.create_task(refresh_unit(
            session_factory, source, "KOSPI", settings=settings, now=lambda: NOW,
            blocker=blocker))
        await asyncio.wait_for(source.entered.wait(), timeout=5)
        second = await refresh_unit(session_factory, source, "KOSPI", settings=settings,
                                    now=lambda: NOW, blocker=blocker)
        source.gate.set()
        done = await asyncio.wait_for(first, timeout=5)

        assert second.outcome == "busy"
        assert done.outcome == "replaced"
        assert source.calls == ["KOSPI"]

    async def test_끝나면_점유를_푼다(self, session_factory) -> None:
        source = StubListingSource({"KOSPI": [[page(kr_body(KOSPI_ROWS))]]})
        await refresh_unit(session_factory, source, "KOSPI", settings=listing_settings(),
                           now=lambda: NOW, blocker=AuthBlocker())
        assert await locks(session_factory) == []

    async def test_실패해도_점유를_푼다(self, session_factory) -> None:
        """풀지 않으면 그 단위는 다시 갱신할 수 없고 화면은 영원히 "갱신 중"이다."""
        source = StubListingSource({"KOSPI": [RuntimeError("예상하지 못한 오류")]})
        result = await refresh_unit(session_factory, source, "KOSPI",
                                    settings=listing_settings(), now=lambda: NOW,
                                    blocker=AuthBlocker())
        assert result.outcome == "failed"
        assert await locks(session_factory) == []


class Test정체_회수:
    async def test_기동_시_남은_점유를_푼다(self, session_factory) -> None:
        """프로세스가 하나다. 기동 시점에 남은 점유는 죽은 프로세스의 것이다."""
        async with session_factory() as s:
            await repo.try_lock(s, "KOSPI", NOW)
        await startup(session_factory)
        assert await locks(session_factory) == []

    async def test_심장박동이_10분_넘게_멈춘_점유를_회수한다(self, session_factory) -> None:
        async with session_factory() as s:
            await repo.try_lock(s, "KOSPI", NOW - dt.timedelta(minutes=11))
        async with session_factory() as s:
            await repo.try_lock(s, "KOSDAQ", NOW - dt.timedelta(minutes=9))
        async with session_factory() as s:
            reclaimed = await repo.reclaim_stale_locks(
                s, NOW, stale_after=dt.timedelta(minutes=10))
            await s.commit()
        assert reclaimed == ["KOSPI"]
        assert await locks(session_factory) == ["KOSDAQ"]

    async def test_심장박동을_갱신하면_회수되지_않는다(self, session_factory) -> None:
        async with session_factory() as s:
            await repo.try_lock(s, "KOSPI", NOW - dt.timedelta(minutes=30))
        async with session_factory() as s:
            await repo.heartbeat(s, "KOSPI", NOW - dt.timedelta(minutes=1))
            await s.commit()
        async with session_factory() as s:
            assert await repo.reclaim_stale_locks(
                s, NOW, stale_after=dt.timedelta(minutes=10)) == []
