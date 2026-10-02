"""목록 갱신 워커 (T036 보강) — 006 FR-013, FR-014.

**워커가 큐를 실제로 비우는지 본다.** 003·005는 엔진만 만들고 호출하는 주체를 두지
않아 작업이 "진행 중"으로 박혔다. 갱신 판정·교체 테스트는 모두 `refresh_unit`을 직접
부르므로, 워커 루프와 `lifespan` 등록이 빠져도 통과한다.
"""
from __future__ import annotations

import asyncio
import contextlib
import inspect

import pytest
from sqlalchemy import select

from src.api import main
from src.db.models import StockListing
from src.worker.listing_queue import ListingQueue
from src.worker.listing_worker import listing_worker_loop
from tests.integration.listing_support import (
    KOSDAQ_ROWS,
    KOSPI_ROWS,
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


class WatchedQueue(ListingQueue):
    """처리를 마친 단위를 알린다. 시간으로 기다리면 느린 환경에서 흔들린다."""

    def __init__(self) -> None:
        super().__init__()
        self.finished: dict[str, asyncio.Event] = {}

    def watch(self, unit: str) -> asyncio.Event:
        return self.finished.setdefault(unit, asyncio.Event())

    def done(self, unit: str) -> None:
        super().done(unit)
        self.watch(unit).set()


async def test_요청한_단위를_받아_교체한다(session_factory) -> None:
    queue = WatchedQueue()
    source = StubListingSource({
        "KOSPI": [RuntimeError("한 단위의 실패")],
        "KOSDAQ": [[page(kr_body(KOSDAQ_ROWS))]],
    })
    task = asyncio.create_task(listing_worker_loop(
        session_factory, source, queue, settings=listing_settings()))
    try:
        queue.request("KOSPI")
        queue.request("KOSDAQ")
        # 한 단위가 실패해도 루프가 끝나지 않고 다음 단위를 처리한다.
        await asyncio.wait_for(queue.watch("KOSDAQ").wait(), timeout=3)
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task

    assert source.calls == ["KOSPI", "KOSDAQ"]
    assert not queue.is_active("KOSPI")
    async with session_factory() as s:
        codes = list((await s.execute(select(StockListing.code))).scalars())
    assert codes == ["247540"]


async def test_큐가_비면_출처를_부르지_않는다(session_factory) -> None:
    """검색이 요청하지 않으면 받지 않는다 — 쓰지 않는 날에도 출처를 부르지 않는다(R6-3)."""
    source = StubListingSource({"KOSPI": [[page(kr_body(KOSPI_ROWS))]]})
    task = asyncio.create_task(listing_worker_loop(
        session_factory, source, ListingQueue(), settings=listing_settings()))
    await asyncio.sleep(0.05)
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task
    assert source.calls == []


def test_lifespan이_워커와_기동_정리를_등록한다() -> None:
    """등록을 빠뜨리면 갱신 요청이 큐에 쌓이기만 하고 실행되지 않는다."""
    body = inspect.getsource(main.lifespan)
    assert "listing_worker_loop(" in body
    assert "listing_startup(" in body
