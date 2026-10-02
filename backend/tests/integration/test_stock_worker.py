"""주식 수집 워커 (T093) — 005 FR-045, FR-047, FR-048, SC-001a.

**003이 001·002에서 얻은 교훈이 여기에도 적용된다.** 수집 엔진을 만들어 두고 그것을
호출하는 주체를 두지 않으면, 작업이 "진행 중"으로 박힌 채 멈춘다. 화면에는 진행 표시가
돌고 있는데 실제로는 아무 일도 일어나지 않으며, 그 사실이 어디에도 드러나지 않는다.
"""
from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest
from sqlalchemy import select

from src.db.dialect import upsert
from src.db.models import (
    JobStatus,
    Stock,
    StockCollectionJob,
    StockCollectionLock,
    StockPrice,
)
from src.ingestion.yahoo.parse import ChartData, DailyPrice
from src.repository.stock_job import acquire_or_get_running
from src.worker.stock_queue import StockWork
from src.worker.stock_worker import run_stock_job

D = dt.date.fromisoformat


class StubSource:
    """시세 출처 스텁. **네트워크를 쓰지 않는다** (헌법 원칙 III)."""

    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.calls: list[tuple[dt.date, dt.date]] = []

    async def fetch_chart(
        self, symbol: str, date_from: dt.date, date_to: dt.date
    ) -> tuple[ChartData, str, int]:
        self.calls.append((date_from, date_to))
        if self.fail:
            raise RuntimeError("출처가 응답하지 않습니다")
        return (
            ChartData(
                currency="KRW",
                first_trade_date=D("1975-06-11"),
                prices=[DailyPrice(
                    quote_date=date_from, open_raw=Decimal("40000"),
                    close_raw=Decimal("40100"), close_adjusted=Decimal("40100"))],
            ),
            "{}", 200,
        )

    async def delay_between_chunks(self) -> None:
        """대기하지 않는다. 테스트가 실제 시간을 쓰면 느려지고 흔들린다."""


@pytest.fixture
async def stock_id(session_factory) -> int:
    async with session_factory() as s:
        await upsert(s, Stock, [{
            "market": "KRX", "symbol": "005930.KS", "name": "삼성전자",
            "currency": "KRW", "first_available_date": D("1975-06-11")}])
        await s.commit()
        return int((await s.execute(select(Stock))).scalar_one().id)


async def make_job(session_factory, stock_id: int) -> StockWork:
    async with session_factory() as s:
        job_id, created = await acquire_or_get_running(
            s, stock_id, D("2021-08-01"), D("2021-08-31"), chunks_total=1)
        await s.commit()
    assert created
    return StockWork(job_id=job_id, stock_id=stock_id, symbol="005930.KS",
                     start=D("2021-08-01"), end=D("2021-08-31"))


class Test성공:
    async def test_시세를_저장하고_작업을_끝낸다(
        self, session_factory, stock_id
    ) -> None:
        work = await make_job(session_factory, stock_id)
        status = await run_stock_job(session_factory, StubSource(), work)
        assert status is JobStatus.SUCCEEDED

        async with session_factory() as s:
            prices = list((await s.execute(select(StockPrice))).scalars())
            job = (await s.execute(select(StockCollectionJob))).scalar_one()
        assert len(prices) == 1
        assert job.status is JobStatus.SUCCEEDED

    async def test_청크마다_진행을_기록한다(self, session_factory, stock_id) -> None:
        """SC-001a — 기록하지 않으면 SSE가 같은 숫자만 반복해 보낸다."""
        work = await make_job(session_factory, stock_id)
        await run_stock_job(session_factory, StubSource(), work)
        async with session_factory() as s:
            job = (await s.execute(select(StockCollectionJob))).scalar_one()
        assert job.chunks_done == 1

    async def test_점유를_푼다(self, session_factory, stock_id) -> None:
        work = await make_job(session_factory, stock_id)
        await run_stock_job(session_factory, StubSource(), work)
        async with session_factory() as s:
            locks = list((await s.execute(select(StockCollectionLock))).scalars())
        assert locks == []


class Test실패:
    async def test_실패해도_작업을_마감한다(self, session_factory, stock_id) -> None:
        """마감하지 않으면 점유가 남아 그 종목은 영영 다시 수집할 수 없다."""
        work = await make_job(session_factory, stock_id)
        status = await run_stock_job(session_factory, StubSource(fail=True), work)
        assert status is JobStatus.FAILED

        async with session_factory() as s:
            job = (await s.execute(select(StockCollectionJob))).scalar_one()
            locks = list((await s.execute(select(StockCollectionLock))).scalars())
        assert job.status is JobStatus.FAILED
        assert locks == [], "실패 뒤에도 점유가 남아 있다"

    async def test_실패_사유를_남긴다(self, session_factory, stock_id) -> None:
        """조용히 끝나면 왜 멈췄는지 알 수 없고 다음 실행이 같은 곳에서 또 멈춘다."""
        work = await make_job(session_factory, stock_id)
        await run_stock_job(session_factory, StubSource(fail=True), work)
        async with session_factory() as s:
            job = (await s.execute(select(StockCollectionJob))).scalar_one()
        assert job.last_error is not None
        assert "응답하지 않습니다" in job.last_error


class Test재수집:
    async def test_이미_받은_구간은_출처를_부르지_않는다(
        self, session_factory, stock_id
    ) -> None:
        """FR-044 — 호출을 낭비하면 출처가 막혔을 때 가진 것으로도 답하지 못한다."""
        work = await make_job(session_factory, stock_id)
        await run_stock_job(session_factory, StubSource(), work)

        second = await make_job(session_factory, stock_id)
        source = StubSource()
        await run_stock_job(session_factory, source, second)
        assert source.calls == []


class Test출처_열기:
    """006 T090에서 발견 — **주식 수집 워커가 출처를 열지 않았다.**

    `YahooStockClient`는 `async with`로 들어가야 HTTP 세션이 생긴다. `lifespan`이 연 적 없는
    클라이언트를 넘겨, 실제 경로의 모든 시세 수집이 "클라이언트 세션이 열려 있지 않습니다"로
    실패했다. 003이 FX 워커에서 같은 결함을 겪고 `worker_loop`가 출처를 직접 열게
    고쳤다(`worker/runner.py`). 스텁은 열 필요가 없어 005의 테스트가 모두 통과했다 — 그래서
    **열어야만 동작하는 스텁**으로 본다.
    """

    class _MustOpen(StubSource):
        def __init__(self) -> None:
            super().__init__()
            self.opened = False
            self.closed = False

        async def __aenter__(self):  # type: ignore[no-untyped-def]
            self.opened = True
            return self

        async def __aexit__(self, *_: object) -> None:
            self.closed = True

        async def fetch_chart(self, symbol, date_from, date_to):  # type: ignore[no-untyped-def]
            if not self.opened:
                raise RuntimeError("클라이언트 세션이 열려 있지 않습니다.")
            return await super().fetch_chart(symbol, date_from, date_to)

    async def test_워커가_출처를_열고_닫는다(self, session_factory, stock_id) -> None:
        import asyncio
        import contextlib

        from src.worker.stock_queue import StockQueue
        from src.worker.stock_worker import stock_worker_loop

        source = self._MustOpen()
        queue = StockQueue()
        work = await make_job(session_factory, stock_id)
        queue.request(work)
        task = asyncio.create_task(stock_worker_loop(session_factory, source, queue))
        try:
            async with asyncio.timeout(3):
                while queue.is_active(stock_id):  # noqa: ASYNC110 — 큐에 완료 사건이 없다
                    await asyncio.sleep(0.02)
        finally:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

        async with session_factory() as s:
            job = (await s.execute(select(StockCollectionJob))).scalar_one()
        assert job.status is JobStatus.SUCCEEDED, job.last_error
        assert source.closed, "종료 시 세션을 닫지 않으면 프로세스가 깨끗하게 끝나지 않는다"
