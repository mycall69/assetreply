"""가상자산 일봉 수집 (T023) — 007 FR-008, FR-010~FR-014, FR-012a, FR-019, FR-020, FR-022, SC-005,
research R7-3·R7-10.

주식(005·006)의 수집 구조를 본뜬다 — 구간을 730일 청크로 나누고, 청크마다 원본을 남기고 upsert하고
**요청한 구간**을 커버리지로 기록해 커밋한다. 중단되면 받은 데까지는 남고 다음 실행이 빠진 구간만
받는다.

- **마감 전 일봉을 저장하지 않는다**(FR-022) — 원본에는 남는다
- **시작 가능 날짜는 수집 중 발견한다**(R7-10) — 요청 구간의 앞부분이 비면 첫 일봉이 시작 가능
  날짜다
- **가격을 읽지 못한 행이 든 청크는 아무것도 저장하지 않는다**(analyze M2) — 그 행만 버리면 그날이
  출처 결측으로 위장된다
- 실패는 종류(`blocked`·`format`·`network`·`empty`)를 남긴다(FR-020) — 할 일이 다르다
"""
from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from src.db.models import (
    CryptoCoin,
    CryptoCollectionJob,
    CryptoDaily,
    CryptoRawResponse,
    JobStatus,
)
from src.ingestion.investing.errors import (
    InvestingBlocked,
    InvestingFormatError,
    InvestingNetworkError,
)
from src.repository import crypto_daily, crypto_job
from src.worker.crypto_queue import CryptoWork
from src.worker.crypto_worker import run_crypto_job
from tests.integration.crypto_support import (
    BTC_ID,
    ETH_ID,
    LEASH_ID,
    UA_SENTINEL,
    StubDailySource,
    add_coin,
    crypto_settings,
)

D = dt.date.fromisoformat


async def job_for(session_factory, coin_id: int, source_id: str, start: str, end: str,  # type: ignore[no-untyped-def]
                  chunks: int = 1) -> CryptoWork:
    async with session_factory() as s:
        job_id, created = await crypto_job.acquire_or_get_running(
            s, coin_id, D(start), D(end), chunks_total=chunks)
        await s.commit()
    assert created
    return CryptoWork(job_id=job_id, coin_id=coin_id, source_id=source_id,
                      start=D(start), end=D(end))


async def run(session_factory, source: StubDailySource, work: CryptoWork) -> JobStatus:  # type: ignore[no-untyped-def]
    return await run_crypto_job(session_factory, source, work, settings=crypto_settings())


async def job_row(session_factory, job_id: int) -> CryptoCollectionJob:  # type: ignore[no-untyped-def]
    async with session_factory() as s:
        job = await crypto_job.get_job(s, job_id)
        assert job is not None
        return job


async def stored_days(session_factory, coin_id: int) -> list[dt.date]:  # type: ignore[no-untyped-def]
    async with session_factory() as s:
        return list((await s.execute(select(CryptoDaily.day).where(
            CryptoDaily.coin_id == coin_id).order_by(CryptoDaily.day))).scalars())


async def coin_row(session_factory, coin_id: int) -> CryptoCoin:  # type: ignore[no-untyped-def]
    async with session_factory() as s:
        coin = await s.get(CryptoCoin, coin_id)
        assert coin is not None
        return coin


@pytest.fixture
async def btc(session_factory) -> int:  # type: ignore[no-untyped-def]
    return await add_coin(session_factory)


class Test청크:
    async def test_730일_청크로_받아_저장하고_요청_구간을_커버리지로_남긴다(
        self, session_factory, btc
    ) -> None:
        source = StubDailySource({BTC_ID: ["btc_2020_2021.json"]})
        work = await job_for(session_factory, btc, BTC_ID, "2020-01-01", "2021-12-31", chunks=2)
        assert await run(session_factory, source, work) is JobStatus.SUCCEEDED

        assert source.calls == [(BTC_ID, D("2020-01-01"), D("2021-12-30")),
                                (BTC_ID, D("2021-12-31"), D("2021-12-31"))]
        days = await stored_days(session_factory, btc)
        assert (len(days), days[0], days[-1]) == (731, D("2020-01-01"), D("2021-12-31"))
        async with session_factory() as s:
            assert await crypto_daily.get_coverage(s, btc) == (D("2020-01-01"), D("2021-12-31"))
            raws = list((await s.execute(select(CryptoRawResponse).order_by(
                CryptoRawResponse.id))).scalars())
            row = await s.get(CryptoDaily, (btc, D("2020-01-01")))
        assert [(r.requested_from, r.requested_to, r.status_code) for r in raws] == [
            (D("2020-01-01"), D("2021-12-30"), 200), (D("2021-12-31"), D("2021-12-31"), 200)]
        assert row is not None
        # 출처 원값(14자리) 그대로다 — 반올림·`float` 없음
        assert row.open == Decimal("7196.39111328125")
        assert row.source == "investing:historical"
        job = await job_row(session_factory, work.job_id)
        assert (job.status, job.chunks_done, job.last_error) == (JobStatus.SUCCEEDED, 2, None)

    async def test_두_번_넣어도_같은_행이다(self, session_factory, btc) -> None:
        source = StubDailySource({BTC_ID: ["btc_2011_06.json"]})
        fetched = await source.fetch_daily(BTC_ID, D("2011-06-01"), D("2011-07-31"),
                                           last_day=D("2026-10-02"))
        async with session_factory() as s:
            await crypto_daily.store_bars(s, btc, fetched.bars)
            await crypto_daily.store_bars(s, btc, fetched.bars)
            await s.commit()
            count = (await s.execute(select(func.count()).select_from(CryptoDaily))).scalar()
            empty = await s.get(CryptoDaily, (btc, D("2011-06-20")))
        assert count == 61
        # 출처가 빈 값으로 준 거래량은 NULL이다(FR-012a)
        assert empty is not None and empty.volume is None

    async def test_마감_전_일봉은_저장하지_않고_원본에는_남긴다(self, session_factory, btc) -> None:
        source = StubDailySource({BTC_ID: ["btc_recent.json"]})
        work = await job_for(session_factory, btc, BTC_ID, "2026-09-13", "2026-10-02")
        await run(session_factory, source, work)
        assert (await stored_days(session_factory, btc))[-1] == D("2026-10-02")

    async def test_중단_뒤_다시_받으면_빠진_구간만_받는다(self, session_factory, btc) -> None:
        source = StubDailySource({BTC_ID: ["btc_2020_2021.json"]})
        source.errors[2] = InvestingNetworkError("끊김")
        first = await job_for(session_factory, btc, BTC_ID, "2020-01-01", "2021-12-31", chunks=2)
        assert await run(session_factory, source, first) is JobStatus.FAILED
        async with session_factory() as s:
            assert await crypto_daily.get_coverage(s, btc) == (D("2020-01-01"), D("2021-12-30"))

        again = StubDailySource({BTC_ID: ["btc_2020_2021.json"]})
        second = await job_for(session_factory, btc, BTC_ID, "2020-01-01", "2021-12-31")
        assert await run(session_factory, again, second) is JobStatus.SUCCEEDED
        assert again.calls == [(BTC_ID, D("2021-12-31"), D("2021-12-31"))]

    async def test_같은_코인이_진행_중이면_새_작업을_만들지_않는다(
        self, session_factory, btc
    ) -> None:
        first = await job_for(session_factory, btc, BTC_ID, "2020-01-01", "2021-12-31")
        async with session_factory() as s:
            job_id, created = await crypto_job.acquire_or_get_running(
                s, btc, D("2020-01-01"), D("2021-12-31"), chunks_total=1)
        assert (job_id, created) == (first.job_id, False)


class Test시작_가능_날짜:
    async def test_요청보다_늦게_시작하면_첫_일봉이_시작_가능_날짜다(self, session_factory) -> None:
        eth = await add_coin(session_factory, ETH_ID, "ETH", "Ethereum", name_ko="이더리움")
        source = StubDailySource({ETH_ID: ["eth_first.json"]})
        work = await job_for(session_factory, eth, ETH_ID, "2015-06-01", "2017-05-31", chunks=2)
        await run(session_factory, source, work)
        assert (await coin_row(session_factory, eth)).first_available_date == D("2016-03-10")
        async with session_factory() as s:
            assert await crypto_daily.get_coverage(s, eth) == (D("2015-06-01"), D("2017-05-31"))

    async def test_요청_첫날부터_있으면_시작_가능_날짜를_모른다(self, session_factory, btc) -> None:
        source = StubDailySource({BTC_ID: ["btc_2020_2021.json"]})
        work = await job_for(session_factory, btc, BTC_ID, "2020-01-01", "2021-12-31", chunks=2)
        await run(session_factory, source, work)
        assert (await coin_row(session_factory, btc)).first_available_date is None

    async def test_일봉이_하나도_없으면_empty로_끝나고_시작_가능_날짜가_없다(
        self, session_factory
    ) -> None:
        leash = await add_coin(session_factory, LEASH_ID, "LEASH", "Doge Killer", name_ko=None)
        source = StubDailySource({LEASH_ID: ["leash_empty.json"]})
        work = await job_for(session_factory, leash, LEASH_ID, "2026-09-01", "2026-10-02")
        assert await run(session_factory, source, work) is JobStatus.FAILED
        job = await job_row(session_factory, work.job_id)
        assert crypto_job.split_error(job.last_error)[0] == "empty"
        assert (await coin_row(session_factory, leash)).first_available_date is None
        # 요청한 구간은 커버리지로 남는다 — 다음 실행이 같은 구간을 다시 받으러 가지 않는다
        async with session_factory() as s:
            assert await crypto_daily.get_coverage(s, leash) == (D("2026-09-01"), D("2026-10-02"))


class Test실패:
    @pytest.mark.parametrize(("error", "kind"), [
        (InvestingBlocked("막힘"), "blocked"), (InvestingNetworkError("끊김"), "network"),
        (InvestingFormatError("모양"), "format")])
    async def test_실패_종류를_남긴다(
        self, session_factory, btc, error: Exception, kind: str
    ) -> None:
        source = StubDailySource({BTC_ID: ["btc_2020_2021.json"]})
        source.errors[1] = error
        work = await job_for(session_factory, btc, BTC_ID, "2020-01-01", "2021-12-31", chunks=2)
        assert await run(session_factory, source, work) is JobStatus.FAILED
        job = await job_row(session_factory, work.job_id)
        assert crypto_job.split_error(job.last_error)[0] == kind
        assert job.finished_at is not None
        async with session_factory() as s:
            assert await crypto_job.running_job_id(s, btc) is None

    async def test_가격을_읽지_못한_행이_든_청크는_아무것도_저장하지_않는다(
        self, session_factory, btc
    ) -> None:
        """analyze M2 — 둘째 청크(2021-12-31)의 시가가 `-`다. 첫 청크는 남고, 둘째 청크의 날은
        저장되지 않으며 커버리지도 늘지 않는다. 사유에 날짜와 필드가 실린다."""
        source = StubDailySource({BTC_ID: ["btc_2020_2021.json"]})
        source.corrupt[2] = "last_openRaw"
        work = await job_for(session_factory, btc, BTC_ID, "2020-01-01", "2021-12-31", chunks=2)
        assert await run(session_factory, source, work) is JobStatus.FAILED
        days = await stored_days(session_factory, btc)
        assert days[-1] == D("2021-12-30")
        async with session_factory() as s:
            assert await crypto_daily.get_coverage(s, btc) == (D("2020-01-01"), D("2021-12-30"))
        job = await job_row(session_factory, work.job_id)
        kind, message = crypto_job.split_error(job.last_error)
        assert kind == "format"
        assert message is not None and "2021-12-31" in message and "last_openRaw" in message


class Test사건:
    async def test_시작_청크_완료를_남기고_사용자_에이전트를_싣지_않는다(
        self, session_factory, btc, captured
    ) -> None:
        source = StubDailySource({BTC_ID: ["btc_2020_2021.json"]})
        work = await job_for(session_factory, btc, BTC_ID, "2020-01-01", "2021-12-31", chunks=2)
        await run(session_factory, source, work)
        events = [r.__dict__.get("event") for r in captured]
        assert events[0] == "crypto_collection_started"
        assert events.count("crypto_collection_chunk") == 2
        assert events[-1] == "crypto_collection_completed"
        assert captured[0].__dict__["coin"] == BTC_ID
        for record in captured:
            assert all(UA_SENTINEL not in str(v) for v in record.__dict__.values())

    async def test_실패를_종류와_함께_남긴다(self, session_factory, btc, captured) -> None:
        source = StubDailySource({BTC_ID: ["btc_2020_2021.json"]})
        source.errors[1] = InvestingBlocked(f"403 {UA_SENTINEL}")
        work = await job_for(session_factory, btc, BTC_ID, "2020-01-01", "2021-12-31", chunks=2)
        await run(session_factory, source, work)
        failed = [r for r in captured if r.__dict__.get("event") == "crypto_collection_failed"]
        assert failed and failed[0].__dict__["kind"] == "blocked"
        for record in captured:
            assert all(UA_SENTINEL not in str(v) for v in record.__dict__.values())
        assert UA_SENTINEL not in ((await job_row(session_factory, work.job_id)).last_error or "")
