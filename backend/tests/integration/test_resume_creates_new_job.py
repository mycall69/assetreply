"""이어받기 검증 (T018, T019) — FR-005b, FR-008, FR-009, SC-003.

두 가지를 본다.

1. 중단된 지점부터 이어받되 **새 작업**으로 기록한다. 하나의 작업은 한 번의 실행
   시도를 뜻하므로, 여러 번의 시도가 한 작업에 합쳐져서는 안 된다.
2. 이미 받은 구간을 **다시 요청하지 않는다**. 중복 수집은 오류 없이 성공한 것처럼
   보이면서 일일 호출 한도만 소진시킨다.
"""
from __future__ import annotations

import datetime as dt

from sqlalchemy import select

from src.db.models import FxCollectionJob, JobStatus
from src.worker.runner import run_once

from .conftest import StubSource

FIRST = (dt.date(2020, 1, 1), dt.date(2020, 6, 30))
SECOND = (dt.date(2020, 7, 1), dt.date(2020, 12, 31))
QUOTES = {"USD": [(f"2020-{m:02d}-01", "1200.00") for m in range(1, 13)]}


class Test새_작업_생성:
    async def test_이어받으면_새_작업이_생긴다(self, session_factory) -> None:
        await run_once(session_factory, StubSource(QUOTES), "USD", *FIRST, chunk_days=90)
        await run_once(session_factory, StubSource(QUOTES), "USD", *SECOND, chunk_days=90)
        async with session_factory() as s:
            jobs = list((await s.execute(
                select(FxCollectionJob).order_by(FxCollectionJob.id))).scalars())
        assert len(jobs) == 2, "이어받기가 기존 작업을 재사용했다"

    async def test_기존_작업의_상태를_되돌리지_않는다(self, session_factory) -> None:
        await run_once(session_factory, StubSource(QUOTES), "USD", *FIRST, chunk_days=90)
        async with session_factory() as s:
            first = (await s.execute(
                select(FxCollectionJob).order_by(FxCollectionJob.id))).scalars().first()
            assert first is not None
            first_id, first_status = first.id, first.status

        await run_once(session_factory, StubSource(QUOTES), "USD", *SECOND, chunk_days=90)
        async with session_factory() as s:
            job = await s.get(FxCollectionJob, first_id)
        assert job is not None and job.status is first_status

    async def test_새_작업의_시작일이_이전_커버리지의_다음_날이다(self, session_factory) -> None:
        """FR-008의 직접 검증. `range_start`가 곧 이어받기 지점이다 (FR-011)."""
        await run_once(session_factory, StubSource(QUOTES), "USD", *FIRST, chunk_days=90)
        await run_once(session_factory, StubSource(QUOTES), "USD", *SECOND,
                       chunk_days=90, resume=True)
        async with session_factory() as s:
            jobs = list((await s.execute(
                select(FxCollectionJob).order_by(FxCollectionJob.id))).scalars())
        assert jobs[1].range_start == FIRST[1] + dt.timedelta(days=1)


class Test중복_수집_방지:
    async def test_이미_받은_구간을_다시_요청하지_않는다(self, session_factory) -> None:
        """SC-003 — 중복 호출은 조용히 한도만 태운다."""
        await run_once(session_factory, StubSource(QUOTES), "USD", *FIRST, chunk_days=90)
        second = StubSource(QUOTES)
        await run_once(session_factory, second, "USD", *FIRST, chunk_days=90, resume=True)
        assert second.requests == [], f"이미 받은 구간을 다시 요청했다: {second.requests}"

    async def test_전부_수집된_통화는_외부_호출_0회로_끝난다(self, session_factory) -> None:
        """FR-009 — 사용자가 '다시 확인'을 눌러도 한도를 쓰지 않는다."""
        await run_once(session_factory, StubSource(QUOTES), "USD", *FIRST, chunk_days=90)
        source = StubSource(QUOTES)
        await run_once(session_factory, source, "USD", *FIRST, chunk_days=90, resume=True)
        assert len(source.requests) == 0

    async def test_외부_호출이_없어도_작업은_생기고_완료된다(self, session_factory) -> None:
        """사용자가 '눌렀는데 아무 일도 없었다'고 느끼지 않게 한다."""
        await run_once(session_factory, StubSource(QUOTES), "USD", *FIRST, chunk_days=90)
        await run_once(session_factory, StubSource(QUOTES), "USD", *FIRST,
                       chunk_days=90, resume=True)
        async with session_factory() as s:
            jobs = list((await s.execute(
                select(FxCollectionJob).order_by(FxCollectionJob.id))).scalars())
        assert len(jobs) == 2
        assert jobs[1].status is JobStatus.SUCCEEDED
