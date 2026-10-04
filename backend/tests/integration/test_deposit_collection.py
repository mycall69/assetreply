"""예금 금리 수집 (T012) — 008 FR-009, FR-010, FR-012, FR-014~FR-016, FR-020, SC-011,
research R8-3~R8-5.

- 처음 받으면 항목 확인 → **전체 시계열 하나**, 금리 upsert, 원본(본문만), 커버리지(첫 달·마지막
  발표 달·확인한 날 = 한국 시간 오늘)
- 다시 확인은 마지막 받은 달의 **2개월 전부터**(겹침) — 겹친 달의 값이 바뀌었으면 **덮어쓰지 않고**
  `deposit_rate_revised` 사건만 남긴다(R8-4)
- 미발표(`INFO-200`)는 실패가 아니다 — 마지막 발표 달은 그대로, 확인한 날은 오늘
- 실패하면 종류를 남기고 **확인한 날을 갱신하지 않는다** — 다음 날 다시 확인한다
- 인증키는 원본·실패 사유·사건 어디에도 없다(SC-011)
"""
from __future__ import annotations

import dataclasses
import datetime as dt

import pytest
from sqlalchemy import select

from src.config.settings import Settings, _Secret, load_settings
from src.db.models import DepositCollectionJob, DepositRawResponse, JobStatus
from src.ingestion.ecos.errors import (
    SourceAuthError,
    SourceError,
    SourceFormatError,
    SourceRateLimited,
    SourceUnavailable,
)
from src.repository import deposit_job, deposit_rate
from src.worker.deposit_queue import DepositWork
from src.worker.deposit_worker import run_deposit_job
from tests.integration.deposit_support import (
    LATEST,
    NOW_UTC,
    TODAY,
    StubDepositSource,
    rate_of,
    seed_rates,
)

D = dt.date.fromisoformat
KEY = "LEAKKEY1234567890XYZ"


def settings() -> Settings:
    return dataclasses.replace(load_settings(), ecos_api_key=_Secret(KEY))


async def job_for(session_factory, institution: str = "commercial_bank",  # type: ignore[no-untyped-def]
                  start: str = "2020-01-01", end: str = "2026-10-01") -> DepositWork:
    months = (D(end).year - D(start).year) * 12 + D(end).month - D(start).month + 1
    async with session_factory() as s:
        job_id, created = await deposit_job.acquire_or_get_running(
            s, institution, D(start), D(end), months_total=months)
        await s.commit()
    assert created
    return DepositWork(job_id=job_id, institution=institution,
                       start_month=D(start), end_month=D(end))


async def raws(session_factory) -> list[DepositRawResponse]:  # type: ignore[no-untyped-def]
    async with session_factory() as s:
        return list((await s.execute(
            select(DepositRawResponse).order_by(DepositRawResponse.id))).scalars())


class Test처음_받기:
    async def test_전체_시계열로_금리·커버리지·원본을_남긴다(self, session_factory) -> None:
        source = StubDepositSource()
        work = await job_for(session_factory)
        status = await run_deposit_job(session_factory, source, work, settings=settings(),
                                       now=NOW_UTC)
        assert status is JobStatus.SUCCEEDED
        # 처음은 START_TIME(2012-01)부터 이번 달까지 한 번에
        assert source.series_calls == [("commercial_bank", D("2012-01-01"), D("2026-10-01"))]
        async with session_factory() as s:
            rates = await deposit_rate.get_rates(s, "commercial_bank")
            coverage = await deposit_rate.get_coverage(s, "commercial_bank")
            job = await s.get(DepositCollectionJob, work.job_id)
        assert len(rates) == 176
        assert rates[D("2020-01-01")] == rate_of("commercial_bank", "2020-01")
        assert coverage is not None
        assert (coverage.first_month, coverage.latest_month, coverage.checked_on) == (
            D("2012-01-01"), LATEST, TODAY)
        # 필요한 구간 2020-01 ~ 2026-10 = 82개월 중 받은 달은 2026-08까지 80개월
        assert job is not None and (job.months_total, job.months_done) == (82, 80)

    async def test_원본은_본문만이고_항목_목록은_통계표당_한_행(self, session_factory) -> None:
        source = StubDepositSource()
        for institution in ("savings_bank", "credit_union"):
            work = await job_for(session_factory, institution)
            await run_deposit_job(session_factory, source, work, settings=settings(),
                                  now=NOW_UTC)
        rows = await raws(session_factory)
        item_lists = [r for r in rows if r.endpoint == "item_list"]
        assert [(r.institution, r.source_ref) for r in item_lists] == [(None, "121Y004")]
        searches = [(r.institution, r.source_ref) for r in rows if r.endpoint == "search"]
        assert searches == [("savings_bank", "121Y004/BEBBBE01"),
                            ("credit_union", "121Y004/BEBBBG01")]
        assert all(KEY not in r.body for r in rows)


class Test다시_확인:
    async def test_마지막_받은_달의_2개월_전부터_요청한다(self, session_factory) -> None:
        await seed_rates(session_factory, checked_on=D("2026-10-03"))
        source = StubDepositSource()
        work = await job_for(session_factory)
        await run_deposit_job(session_factory, source, work, settings=settings(), now=NOW_UTC)
        assert source.series_calls == [("commercial_bank", D("2026-06-01"), D("2026-10-01"))]

    async def test_미발표면_마지막_달은_그대로_확인한_날은_오늘(self, session_factory) -> None:
        await seed_rates(session_factory, checked_on=D("2026-10-03"))
        source = StubDepositSource()
        work = await job_for(session_factory)
        status = await run_deposit_job(session_factory, source, work, settings=settings(),
                                       now=NOW_UTC)
        async with session_factory() as s:
            coverage = await deposit_rate.get_coverage(s, "commercial_bank")
        assert status is JobStatus.SUCCEEDED
        assert coverage is not None
        assert (coverage.latest_month, coverage.checked_on) == (LATEST, TODAY)

    async def test_겹친_달의_값이_바뀌었으면_덮어쓰지_않고_사건만_남긴다(
            self, session_factory, captured) -> None:  # type: ignore[no-untyped-def]
        await seed_rates(session_factory, checked_on=D("2026-10-03"))
        source = StubDepositSource(override={"commercial_bank": {"202607": "9.99"}})
        work = await job_for(session_factory)
        await run_deposit_job(session_factory, source, work, settings=settings(), now=NOW_UTC)
        async with session_factory() as s:
            rates = await deposit_rate.get_rates(s, "commercial_bank")
        assert rates[D("2026-07-01")] == rate_of("commercial_bank", "2026-07")
        revised = [r for r in captured if getattr(r, "event", None) == "deposit_rate_revised"]
        assert len(revised) == 1
        event = revised[0].__dict__
        assert (event["institution"], event["month"], event["new"]) == (
            "commercial_bank", "2026-07", "9.99")
        assert event["old"] == str(rate_of("commercial_bank", "2026-07"))


class Test실패:
    @pytest.mark.parametrize(("error", "kind"), [
        (SourceAuthError("인증키 오류"), "auth"),
        (SourceRateLimited("호출 한도 초과"), "rate_limited"),
        (SourceFormatError("금리를 읽을 수 없습니다"), "format"),
        (SourceUnavailable("출처에 연결하지 못했습니다"), "network"),
    ])
    async def test_종류를_남기고_확인한_날을_갱신하지_않는다(
            self, session_factory, error: SourceError, kind: str) -> None:
        await seed_rates(session_factory, checked_on=D("2026-10-03"))
        work = await job_for(session_factory)
        status = await run_deposit_job(session_factory, StubDepositSource(error=error), work,
                                       settings=settings(), now=NOW_UTC)
        async with session_factory() as s:
            job = await s.get(DepositCollectionJob, work.job_id)
            coverage = await deposit_rate.get_coverage(s, "commercial_bank")
            running = await deposit_job.running_job_id(s, "commercial_bank")
        assert status is JobStatus.FAILED
        assert job is not None and deposit_job.split_error(job.last_error)[0] == kind
        assert coverage is not None and coverage.checked_on == D("2026-10-03")
        assert running is None, "실패해도 점유를 풀어야 한다"

    async def test_실패_사유와_사건에_인증키가_없다(self, session_factory, captured) -> None:  # type: ignore[no-untyped-def]
        work = await job_for(session_factory)
        error = SourceUnavailable(f"Cannot connect https://ecos.bok.or.kr/api/x/{KEY}/json")
        await run_deposit_job(session_factory, StubDepositSource(error=error), work,
                              settings=settings(), now=NOW_UTC)
        async with session_factory() as s:
            job = await s.get(DepositCollectionJob, work.job_id)
        assert job is not None and job.last_error is not None
        assert KEY not in job.last_error
        assert all(KEY not in str(r.__dict__) for r in captured)


class Test점유와_사건:
    async def test_같은_투자처가_진행_중이면_새_작업이_없다(self, session_factory) -> None:
        work = await job_for(session_factory)
        async with session_factory() as s:
            job_id, created = await deposit_job.acquire_or_get_running(
                s, "commercial_bank", D("2020-01-01"), D("2026-10-01"), months_total=82)
        assert (job_id, created) == (work.job_id, False)

    async def test_수집_로그에_시작과_완료가_남는다(self, session_factory, captured) -> None:  # type: ignore[no-untyped-def]
        work = await job_for(session_factory)
        await run_deposit_job(session_factory, StubDepositSource(), work, settings=settings(),
                              now=NOW_UTC)
        events = [r.__dict__ for r in captured if getattr(r, "event", "").startswith("deposit_")]
        names = [e["event"] for e in events]
        assert names[0] == "deposit_collection_started" and names[-1] == (
            "deposit_collection_completed")
        assert events[0]["institution"] == "commercial_bank"
        assert (events[0]["start"], events[0]["end"]) == ("2020-01", "2026-10")
        assert events[-1]["latest_month"] == "2026-08"
