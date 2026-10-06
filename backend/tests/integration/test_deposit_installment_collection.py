"""정기적금 금리 수집 (011 T042) — FR-029, FR-030, research R11-2.

적금 금리는 008의 수집 경로(실행기 `collect_institution`·큐·잠금·커버리지·원본·사건)에 **새 금리
계열 키**로 담는다 — 스키마 변경이 없다. 실행기는 키 문자열만 본다.

- `commercial_bank_isav`로 받으면 예금은행 「정기적금(1-2년)」 전체 시계열이
  `deposit_rate`·`deposit_coverage`에 그 키로 저장된다
- 원본(`deposit_raw_response`)은 본문만이다(URL에 인증키가 있다)
- 항목 목록은 정기예금과 **함께** 쓴다 — 같은 통계표면 한 번만 받는다
- 다시 확인(2개월 겹침)·수정 사건(`deposit_rate_revised`)이 계열마다 성립한다
- 정기예금 키(`commercial_bank`)의 저장은 그대로다 — 두 계열이 섞이지 않는다
"""
from __future__ import annotations

import dataclasses
import datetime as dt

from sqlalchemy import select

from src.config.settings import Settings, _Secret, load_settings
from src.db.models import DepositRawResponse, JobStatus
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
ISAV = "commercial_bank_isav"


def settings() -> Settings:
    return dataclasses.replace(load_settings(), ecos_api_key=_Secret(KEY))


async def job_for(session_factory, series: str, start: str = "2015-01-01",  # type: ignore[no-untyped-def]
                  end: str = "2026-10-01") -> DepositWork:
    months = (D(end).year - D(start).year) * 12 + D(end).month - D(start).month + 1
    async with session_factory() as s:
        job_id, created = await deposit_job.acquire_or_get_running(
            s, series, D(start), D(end), months_total=months)
        await s.commit()
    assert created
    return DepositWork(job_id=job_id, institution=series, start_month=D(start),
                       end_month=D(end))


async def raws(session_factory) -> list[DepositRawResponse]:  # type: ignore[no-untyped-def]
    async with session_factory() as s:
        return list((await s.execute(
            select(DepositRawResponse).order_by(DepositRawResponse.id))).scalars())


class Test적금_계열_수집:
    async def test_계열_키로_전체_시계열을_저장한다(self, session_factory) -> None:
        source = StubDepositSource()
        work = await job_for(session_factory, ISAV)
        status = await run_deposit_job(session_factory, source, work, settings=settings(),
                                       now=NOW_UTC)
        assert status is JobStatus.SUCCEEDED
        # 처음은 항목의 시작 달(2003-01)부터 이번 달까지 한 번에
        assert source.series_calls == [(ISAV, D("2003-01-01"), D("2026-10-01"))]
        async with session_factory() as s:
            rates = await deposit_rate.get_rates(s, ISAV)
            coverage = await deposit_rate.get_coverage(s, ISAV)
            deposit = await deposit_rate.get_rates(s, "commercial_bank")
        assert len(rates) == 284
        assert rates[D("2015-01-01")] == rate_of(ISAV, "2015-01")
        assert coverage is not None
        assert (coverage.first_month, coverage.latest_month, coverage.checked_on) == (
            D("2003-01-01"), LATEST, TODAY)
        # 정기예금 키에는 아무것도 들어가지 않는다
        assert deposit == {}

    async def test_원본은_본문만이고_항목_목록은_정기예금과_함께_쓴다(
            self, session_factory) -> None:
        source = StubDepositSource()
        for series in (ISAV, "commercial_bank"):
            work = await job_for(session_factory, series)
            await run_deposit_job(session_factory, source, work, settings=settings(),
                                  now=NOW_UTC)
        rows = await raws(session_factory)
        assert [(r.institution, r.source_ref) for r in rows if r.endpoint == "item_list"] == [
            (None, "121Y002")]
        assert [(r.institution, r.source_ref) for r in rows if r.endpoint == "search"] == [
            (ISAV, "121Y002/BEABAA2122"), ("commercial_bank", "121Y002/BEABAA2118")]
        assert all(KEY not in r.body for r in rows)
        async with session_factory() as s:
            assert len(await deposit_rate.get_rates(s, ISAV)) == 284
            assert len(await deposit_rate.get_rates(s, "commercial_bank")) == 176

    async def test_상호금융_적금은_만기_구분_없는_정기적금이다(self, session_factory) -> None:
        source = StubDepositSource()
        work = await job_for(session_factory, "mutual_finance_isav")
        await run_deposit_job(session_factory, source, work, settings=settings(), now=NOW_UTC)
        rows = await raws(session_factory)
        assert [(r.institution, r.source_ref) for r in rows if r.endpoint == "search"] == [
            ("mutual_finance_isav", "121Y004/BEBB0200")]
        async with session_factory() as s:
            coverage = await deposit_rate.get_coverage(s, "mutual_finance_isav")
        assert coverage is not None and coverage.first_month == D("2012-01-01")


class Test적금_계열_다시_확인:
    async def test_마지막_받은_달의_2개월_전부터_요청한다(self, session_factory) -> None:
        await seed_rates(session_factory, ISAV, checked_on=D("2026-10-03"))
        source = StubDepositSource()
        work = await job_for(session_factory, ISAV)
        await run_deposit_job(session_factory, source, work, settings=settings(), now=NOW_UTC)
        assert source.series_calls == [(ISAV, D("2026-06-01"), D("2026-10-01"))]

    async def test_겹친_달의_값이_바뀌었으면_덮어쓰지_않고_사건만_남긴다(
            self, session_factory, captured) -> None:  # type: ignore[no-untyped-def]
        await seed_rates(session_factory, ISAV, checked_on=D("2026-10-03"))
        source = StubDepositSource(override={ISAV: {"202607": "9.99"}})
        work = await job_for(session_factory, ISAV)
        await run_deposit_job(session_factory, source, work, settings=settings(), now=NOW_UTC)
        async with session_factory() as s:
            rates = await deposit_rate.get_rates(s, ISAV)
        assert rates[D("2026-07-01")] == rate_of(ISAV, "2026-07")
        revised = [r for r in captured if getattr(r, "event", None) == "deposit_rate_revised"]
        assert [(r.__dict__["institution"], r.__dict__["month"], r.__dict__["new"])
                for r in revised] == [(ISAV, "2026-07", "9.99")]
