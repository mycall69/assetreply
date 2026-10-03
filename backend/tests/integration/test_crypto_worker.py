"""가상자산 수집 줄 (T027) — 007 FR-014, FR-015, SC-012, research R7-11.

**실행 주체를 거친다.** 수집 엔진을 만들어 두고 그것을 부르는 주체를 두지 않으면 작업이 "진행
중"으로 박힌다(003·005의 교훈). 가상자산 수집은 **주식 수집과 다른 줄**이다 — 출처가 달라 한쪽이
막혀도 다른 쪽이 기다리지 않는다(SC-012).
"""
from __future__ import annotations

import asyncio
import contextlib
import datetime as dt
import inspect
from decimal import Decimal

from sqlalchemy import select

from src.api import main
from src.db.dialect import upsert
from src.db.models import CryptoCollectionJob, JobStatus, Stock
from src.ingestion.yahoo.parse import ChartData, ChartFetch, DailyPrice, RawBody
from src.repository import crypto_job
from src.repository.stock_job import acquire_or_get_running
from src.worker import crypto_worker
from src.worker.crypto_queue import CryptoQueue, CryptoWork
from src.worker.stock_queue import StockQueue, StockWork
from src.worker.stock_worker import stock_worker_loop
from tests.integration.crypto_support import BTC_ID, StubDailySource, add_coin, crypto_settings

D = dt.date.fromisoformat


def test_lifespan이_가상자산_두_줄과_기동_정리를_등록한다() -> None:
    """등록을 빠뜨리면 요청이 큐에 쌓이기만 하고 실행되지 않는다. 태스크는
    6개다(FX·정리·주식·목록·코인 목록·코인 시세)."""
    body = inspect.getsource(main.lifespan)
    assert "crypto_worker_loop(" in body
    assert "crypto_list_worker_loop(" in body
    assert "crypto_startup(" in body
    assert body.count("asyncio.create_task(") == 6


async def test_기동_시_남은_가상자산_점유를_회수한다(session_factory) -> None:
    """프로세스가 하나다 — 기동 시점에 남은 점유는 죽은 프로세스의 것이다. 풀지 않으면 그 코인은
    다시 받을 수 없다."""
    coin_id = await add_coin(session_factory)
    async with session_factory() as s:
        job_id, _ = await crypto_job.acquire_or_get_running(
            s, coin_id, D("2020-01-01"), D("2021-12-31"), chunks_total=2)
        await s.commit()
    await crypto_worker.startup(session_factory)
    async with session_factory() as s:
        assert await crypto_job.running_job_id(s, coin_id) is None
        job = await s.get(CryptoCollectionJob, job_id)
    assert job is not None and job.status is not JobStatus.RUNNING
    assert crypto_job.split_error(job.last_error)[0] == "network"


class _GatedStockSource:
    """주식 출처 — 문이 열릴 때까지 응답하지 않는다."""

    def __init__(self) -> None:
        self.gate = asyncio.Event()
        self.entered = asyncio.Event()

    async def fetch_chart(self, symbol: str, date_from: dt.date, date_to: dt.date) -> ChartFetch:
        self.entered.set()
        await self.gate.wait()
        return ChartFetch(
            data=ChartData(currency="KRW", first_trade_date=D("1975-06-11"), prices=[DailyPrice(
                quote_date=date_from, open_raw=Decimal("40000"), close_raw=Decimal("40100"),
                close_adjusted=Decimal("40100"))]),
            raws=[RawBody("chart", "{}", 200, date_from, date_to)])

    async def delay_between_chunks(self) -> None:
        return None


async def test_주식_수집이_막혀도_가상자산_수집은_끝난다(session_factory) -> None:
    async with session_factory() as s:
        await upsert(s, Stock, [{"market": "KRX", "symbol": "005930.KS", "name": "삼성전자",
                                 "currency": "KRW", "first_available_date": D("1975-06-11")}])
        await s.commit()
        stock_id = int((await s.execute(select(Stock))).scalar_one().id)
        stock_job, _ = await acquire_or_get_running(
            s, stock_id, D("2021-08-01"), D("2021-08-31"), chunks_total=1)
        await s.commit()
    coin_id = await add_coin(session_factory)
    async with session_factory() as s:
        coin_job, _ = await crypto_job.acquire_or_get_running(
            s, coin_id, D("2020-01-01"), D("2021-12-31"), chunks_total=2)
        await s.commit()

    stock_source = _GatedStockSource()
    stock_queue, coin_queue = StockQueue(), CryptoQueue()
    stock_queue.request(StockWork(job_id=stock_job, stock_id=stock_id, symbol="005930.KS",
                                  start=D("2021-08-01"), end=D("2021-08-31")))
    coin_queue.request(CryptoWork(job_id=coin_job, coin_id=coin_id, source_id=BTC_ID,
                                  start=D("2020-01-01"), end=D("2021-12-31")))
    tasks = [
        asyncio.create_task(stock_worker_loop(session_factory, stock_source, stock_queue)),
        asyncio.create_task(crypto_worker.crypto_worker_loop(
            session_factory, StubDailySource({BTC_ID: ["btc_2020_2021.json"]}), coin_queue,
            settings=crypto_settings())),
    ]
    try:
        await asyncio.wait_for(stock_source.entered.wait(), timeout=3)
        async with asyncio.timeout(5):
            while coin_queue.is_active(coin_id):  # noqa: ASYNC110 — 큐에 완료 사건이 없다
                await asyncio.sleep(0.02)
        # 주식은 아직 출처에서 기다린다
        assert stock_queue.is_active(stock_id)
        stock_source.gate.set()
        async with asyncio.timeout(5):
            while stock_queue.is_active(stock_id):  # noqa: ASYNC110
                await asyncio.sleep(0.02)
    finally:
        for task in tasks:
            task.cancel()
        for task in tasks:
            with contextlib.suppress(asyncio.CancelledError):
                await task
    async with session_factory() as s:
        job = await s.get(CryptoCollectionJob, coin_job)
    assert job is not None and job.status is JobStatus.SUCCEEDED
