"""종목별 수집 점유 (T020) — 005 FR-048, SC-028.

중복 수집은 **오류 없이 성공하면서** 출처 호출만 두 배로 쓴다. 출처가 한도를 공개하지
않으므로 그 대가를 미리 알 수 없다.

기본 키 INSERT 충돌이 곧 "이미 진행 중"을 뜻한다 — 003이 FX에서 쓴 것과 같은 수단이며,
모든 RDBMS에서 동일하게 동작하는 유일한 이식 가능 방법이다.
"""
from __future__ import annotations

import datetime as dt

import pytest
from sqlalchemy import select

from src.db.dialect import upsert
from src.db.models import JobStatus, Stock, StockCollectionJob
from src.repository.stock_job import (
    acquire_or_get_running,
    finish_job,
    get_job,
)

D = dt.date.fromisoformat


@pytest.fixture
async def stocks(session_factory) -> tuple[int, int]:
    async with session_factory() as s:
        await upsert(s, Stock, [
            {"market": "KRX", "symbol": "005930.KS", "name": "삼성전자",
             "currency": "KRW"},
            {"market": "NASDAQ", "symbol": "AAPL", "name": "Apple",
             "currency": "USD"}])
        await s.commit()
        rows = (await s.execute(select(Stock).order_by(Stock.symbol))).scalars().all()
        return int(rows[0].id), int(rows[1].id)  # AAPL, 005930.KS


class Test점유:
    async def test_처음_요청하면_작업이_생긴다(self, session_factory, stocks) -> None:
        stock_id = stocks[0]
        async with session_factory() as s:
            job_id, created = await acquire_or_get_running(
                s, stock_id, D("2021-01-01"), D("2021-12-31"), chunks_total=1)
            await s.commit()
        assert created is True
        assert job_id > 0

    async def test_진행_중이면_새_작업을_만들지_않는다(
        self, session_factory, stocks
    ) -> None:
        """FR-048, SC-028 — 그 작업의 ID를 돌려준다."""
        stock_id = stocks[0]
        async with session_factory() as s:
            first, _ = await acquire_or_get_running(
                s, stock_id, D("2021-01-01"), D("2021-12-31"), chunks_total=1)
            await s.commit()

        async with session_factory() as s:
            second, created = await acquire_or_get_running(
                s, stock_id, D("2021-01-01"), D("2021-12-31"), chunks_total=1)
            await s.commit()

        assert second == first
        assert created is False

        async with session_factory() as s:
            jobs = (await s.execute(select(StockCollectionJob))).scalars().all()
        assert len(jobs) == 1, "중복 작업이 생겼다"

    async def test_끝나면_점유가_풀린다(self, session_factory, stocks) -> None:
        stock_id = stocks[0]
        async with session_factory() as s:
            first, _ = await acquire_or_get_running(
                s, stock_id, D("2021-01-01"), D("2021-12-31"), chunks_total=1)
            await s.commit()
            await finish_job(s, first, JobStatus.SUCCEEDED)
            await s.commit()

        async with session_factory() as s:
            second, created = await acquire_or_get_running(
                s, stock_id, D("2022-01-01"), D("2022-12-31"), chunks_total=1)
            await s.commit()
        assert created is True
        assert second != first

    async def test_다른_종목은_서로_막지_않는다(self, session_factory, stocks) -> None:
        """점유는 종목 단위다. 한 종목이 돌 때 다른 종목을 막을 이유가 없다."""
        a, b = stocks
        async with session_factory() as s:
            await acquire_or_get_running(
                s, a, D("2021-01-01"), D("2021-12-31"), chunks_total=1)
            await s.commit()

        async with session_factory() as s:
            _, created = await acquire_or_get_running(
                s, b, D("2021-01-01"), D("2021-12-31"), chunks_total=1)
            await s.commit()
        assert created is True


class Test작업_상태:
    async def test_실패_사유가_남는다(self, session_factory, stocks) -> None:
        """조용히 끝나면 왜 멈췄는지 알 수 없다."""
        stock_id = stocks[0]
        async with session_factory() as s:
            job_id, _ = await acquire_or_get_running(
                s, stock_id, D("2021-01-01"), D("2021-12-31"), chunks_total=1)
            await s.commit()
            await finish_job(s, job_id, JobStatus.FAILED, error="출처 장애")
            await s.commit()
            job = await get_job(s, job_id)
        assert job is not None
        assert job.status is JobStatus.FAILED
        assert job.last_error == "출처 장애"
        assert job.finished_at is not None

    async def test_진행률을_갱신할_수_있다(self, session_factory, stocks) -> None:
        from src.repository.stock_job import advance_chunk

        stock_id = stocks[0]
        async with session_factory() as s:
            job_id, _ = await acquire_or_get_running(
                s, stock_id, D("2021-01-01"), D("2021-12-31"), chunks_total=3)
            await s.commit()
            await advance_chunk(s, job_id)
            await s.commit()
            job = await get_job(s, job_id)
        assert job is not None
        assert job.chunks_done == 1
        assert job.chunks_total == 3
