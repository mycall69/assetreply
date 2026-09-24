"""기록 적재·보관·조회 검증 (T049~T054, T063~T065).

Phase 5(기록)와 Phase 6(한도)의 백엔드 측면을 함께 본다.
"""
from __future__ import annotations

import datetime as dt

import pytest
from sqlalchemy import select

from src.api.errors import InvalidQuery
from src.db.models import FxCollectionEvent, FxCollectionJob, JobStatus
from src.observability.events import CHUNK_EMPTY, CHUNK_FAILED, CollectionEvent
from src.observability.sinks import EventPublisher
from src.repository.collection_event import (
    dropped_for_currency,
    list_by_currency,
    list_by_job,
    prune_to_recent_jobs,
    record,
)
from src.repository.job import create_job
from src.repository.raw_response import count_calls_on
from src.worker.runner import run_once

from .conftest import StubSource

RANGE = (dt.date(2020, 1, 1), dt.date(2020, 12, 31))
QUOTES = {"USD": [(f"2020-{m:02d}-01", "1200.00") for m in range(1, 13)]}


class Test양쪽_적재:
    async def test_수집_후_사건이_DB에_남는다(self, session_factory) -> None:
        await run_once(session_factory, StubSource(QUOTES), "USD", *RANGE, chunk_days=90)
        async with session_factory() as s:
            rows = list((await s.execute(select(FxCollectionEvent))).scalars())
        assert rows

    async def test_파일_로그에도_같은_사건이_간다(self, session_factory, captured) -> None:
        """두 경로가 같은 사건에서 생성되어야 한다 (FR-018, SC-007)."""
        await run_once(session_factory, StubSource(QUOTES), "USD", *RANGE, chunk_days=90)
        async with session_factory() as s:
            db_kinds = {e.kind for e in
                        (await s.execute(select(FxCollectionEvent))).scalars()}
        log_kinds = {getattr(r, "kind", None) for r in captured}
        assert db_kinds <= log_kinds, f"파일에만 없는 사건: {db_kinds - log_kinds}"


class Test결측과_실패_구별:
    async def test_값이_없으면_chunk_empty다(self, session_factory) -> None:
        """FR-021, SC-008 — 합치면 공백의 원인을 되짚을 수 없다."""
        await run_once(session_factory, StubSource({}), "USD", *RANGE, chunk_days=90)
        async with session_factory() as s:
            kinds = [e.kind for e in
                     (await s.execute(select(FxCollectionEvent))).scalars()]
        assert CHUNK_EMPTY in kinds
        assert CHUNK_FAILED not in kinds

    async def test_두_종류가_다른_값이다(self) -> None:
        assert CHUNK_EMPTY != CHUNK_FAILED


class Test기록_실패_처리:
    async def test_적재가_실패해도_수집은_끝까지_간다(self, session_factory) -> None:
        """FR-018a, SC-007b — 관찰 실패가 본 기능을 되돌리면 안 된다."""
        async def broken(_: CollectionEvent) -> None:
            raise RuntimeError("적재 실패")

        pub = EventPublisher(db_sink=broken)
        for _ in range(3):
            await pub.publish(CollectionEvent(job_id=1, currency="USD", kind=CHUNK_EMPTY))
        assert pub.dropped == 3  # 예외가 호출자에게 올라오지 않았다

    async def test_누락_건수가_작업에_남는다(self, session_factory) -> None:
        """FR-018b — DB 적재 실패를 DB에 남길 수 없는 순환을 건수로 끊는다."""
        async with session_factory() as s:
            job = await create_job(s, "USD", *RANGE, chunks_total=1)
            job.events_dropped = 4
            job.status = JobStatus.SUCCEEDED
            await s.commit()
            job_id = job.id
        async with session_factory() as s:
            stored = await s.get(FxCollectionJob, job_id)
        assert stored is not None and stored.events_dropped == 4


class Test보관_범위:
    async def _job_with_event(self, session_factory, currency: str = "USD") -> int:
        async with session_factory() as s:
            job = await create_job(s, currency, *RANGE, chunks_total=1)
            await s.commit()
            await record(s, CollectionEvent(job_id=job.id, currency=currency,
                                            kind=CHUNK_EMPTY))
            await s.commit()
            return job.id

    async def test_범위_안의_사건은_남는다(self, session_factory) -> None:
        job_id = await self._job_with_event(session_factory)
        async with session_factory() as s:
            await prune_to_recent_jobs(s, "USD", keep_jobs=20)
            await s.commit()
            assert await list_by_job(s, job_id)

    async def test_범위_밖의_사건은_지워진다(self, session_factory) -> None:
        """FR-023, SC-015."""
        first = await self._job_with_event(session_factory)
        for _ in range(3):
            await self._job_with_event(session_factory)
        async with session_factory() as s:
            await prune_to_recent_jobs(s, "USD", keep_jobs=2)
            await s.commit()
            assert await list_by_job(s, first) == []

    async def test_작업_행_자체는_남는다(self, session_factory) -> None:
        """작업 목록은 가볍고, 지우면 '언제 수집했는지'가 사라진다."""
        first = await self._job_with_event(session_factory)
        for _ in range(3):
            await self._job_with_event(session_factory)
        async with session_factory() as s:
            await prune_to_recent_jobs(s, "USD", keep_jobs=2)
            await s.commit()
            assert await s.get(FxCollectionJob, first) is not None

    async def test_다른_통화를_건드리지_않는다(self, session_factory) -> None:
        jpy = await self._job_with_event(session_factory, "JPY")
        for _ in range(3):
            await self._job_with_event(session_factory, "USD")
        async with session_factory() as s:
            await prune_to_recent_jobs(s, "USD", keep_jobs=1)
            await s.commit()
            assert await list_by_job(s, jpy)

    async def test_누락_합계를_돌려준다(self, session_factory) -> None:
        async with session_factory() as s:
            job = await create_job(s, "USD", *RANGE, chunks_total=1)
            job.events_dropped = 2
            await s.commit()
            assert await dropped_for_currency(s, "USD", keep_jobs=20) == 2


class Test조회_계약:
    async def test_통화로_조회된다(self, session_factory) -> None:
        await run_once(session_factory, StubSource(QUOTES), "USD", *RANGE, chunk_days=90)
        async with session_factory() as s:
            assert await list_by_currency(s, "USD", limit=10)

    async def test_매개변수가_없으면_거부한다(self) -> None:
        """contracts/rest-api 4절 — 400 invalid_query."""
        from src.api.routes.collection import get_events

        with pytest.raises(InvalidQuery):
            await get_events(session=None, job_id=None, currency=None)  # type: ignore[arg-type]


class Test호출_수:
    async def test_오늘_행_수를_센다(self, session_factory) -> None:
        """FR-024 — 별도 집계 테이블을 두지 않는다 (research R3-5)."""
        async with session_factory() as s:
            before = await count_calls_on(s, dt.date.today())
        source = StubSource(QUOTES)
        await run_once(session_factory, source, "USD", *RANGE, chunk_days=90)
        async with session_factory() as s:
            after = await count_calls_on(s, dt.date.today())
        assert after - before == len(source.requests)

    async def test_다른_날짜는_세지_않는다(self, session_factory) -> None:
        await run_once(session_factory, StubSource(QUOTES), "USD", *RANGE, chunk_days=90)
        async with session_factory() as s:
            assert await count_calls_on(s, dt.date.today() - dt.timedelta(days=1)) == 0


class Test한도_소진:
    async def test_한도_신호를_받으면_부분_완료로_끝난다(self, session_factory) -> None:
        """FR-025a, SC-013a — 사유 없이 끝나면 왜 멈췄는지 알 수 없다."""
        from src.ingestion.ecos.errors import SourceRateLimited

        source = StubSource(QUOTES)
        source.raise_on_call = SourceRateLimited("INFO-300")
        source.raise_after = 1
        job = await run_once(session_factory, source, "USD", *RANGE, chunk_days=90)
        assert job is not None
        async with session_factory() as s:
            stored = await s.get(FxCollectionJob, job.id)
        assert stored is not None
        assert stored.status is JobStatus.PARTIAL
        assert stored.last_error and "한도" in stored.last_error

    async def test_한도_사건이_기록에_남는다(self, session_factory) -> None:
        from src.ingestion.ecos.errors import SourceRateLimited

        source = StubSource(QUOTES)
        source.raise_on_call = SourceRateLimited("INFO-300")
        source.raise_after = 1
        await run_once(session_factory, source, "USD", *RANGE, chunk_days=90)
        async with session_factory() as s:
            kinds = [e.kind for e in
                     (await s.execute(select(FxCollectionEvent))).scalars()]
        assert "rate_limited" in kinds

    async def test_이미_받은_구간은_유효하다(self, session_factory) -> None:
        """FR-026 — 한도 소진은 데이터 손실이 아니다."""
        from src.db.models import FxRate
        from src.ingestion.ecos.errors import SourceRateLimited

        source = StubSource(QUOTES)
        source.raise_on_call = SourceRateLimited("INFO-300")
        source.raise_after = 2
        await run_once(session_factory, source, "USD", *RANGE, chunk_days=90)
        async with session_factory() as s:
            rates = list((await s.execute(select(FxRate))).scalars())
        assert rates, "한도 소진 전에 받은 데이터가 사라졌다"
