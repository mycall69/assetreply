"""진행률 SSE 스트림 테스트 (T090).

contracts/sse-progress.md — `progress` 이벤트 간격은 10초를 넘지 않으며(SC-009),
재연결 시 현재 상태를 즉시 1회 전송한다.
"""
from __future__ import annotations

import datetime as dt

from src.api.progress import HEARTBEAT_SECONDS, ProgressEvent, format_sse, progress_stream
from src.db.models import JobStatus
from src.repository.job import create_job

RANGE = (dt.date(2020, 1, 1), dt.date(2020, 12, 31))


class TestSSE_형식:
    def test_이벤트_이름과_데이터를_담는다(self) -> None:
        raw = format_sse("progress", {"jobId": 1, "chunksDone": 3})
        assert raw.startswith("event: progress\n")
        assert '"chunksDone": 3' in raw or '"chunksDone":3' in raw

    def test_이벤트가_빈_줄로_끝난다(self) -> None:
        """SSE 프레임 구분자 — 없으면 클라이언트가 이벤트를 못 받는다."""
        assert format_sse("progress", {"a": 1}).endswith("\n\n")

    def test_개행이_들어간_값도_한_프레임을_깨뜨리지_않는다(self) -> None:
        raw = format_sse("completed", {"lastError": "줄1\n줄2"})
        body = [ln for ln in raw.splitlines() if ln.startswith("data: ")]
        assert len(body) == 1, "data 줄이 쪼개지면 프레임이 깨진다"


class Test하트비트_간격:
    def test_간격이_10초_이하다(self) -> None:
        """SC-009: 진행 상황이 갱신되지 않는 구간을 10초 이상 경험하지 않는다."""
        assert HEARTBEAT_SECONDS <= 10


class Test스트림:
    async def test_진행_중_작업의_상태를_즉시_보낸다(self, session_factory) -> None:
        """재연결 시 클라이언트가 공백 없이 따라잡아야 한다."""
        async with session_factory() as s:
            job = await create_job(s, "USD", *RANGE, chunks_total=4)
            job.chunks_done = 2
            await s.commit()
            events = [e async for e in progress_stream(s, job_id=job.id, max_events=1)]
        assert events[0].name == "progress"
        assert events[0].data["chunksDone"] == 2

    async def test_종료된_작업은_completed를_보내고_끝난다(self, session_factory) -> None:
        async with session_factory() as s:
            job = await create_job(s, "USD", *RANGE, chunks_total=4)
            job.status = JobStatus.SUCCEEDED
            job.chunks_done = 4
            job.finished_at = dt.datetime.now()
            await s.commit()
            events = [e async for e in progress_stream(s, job_id=job.id, max_events=5)]
        assert events[-1].name == "completed"
        assert events[-1].data["status"] == "succeeded"

    async def test_중단된_작업은_사유를_담는다(self, session_factory) -> None:
        """FR-013: 중단 사유를 사용자에게 알린다."""
        async with session_factory() as s:
            job = await create_job(s, "USD", *RANGE, chunks_total=4)
            job.status = JobStatus.PARTIAL
            job.chunks_done = 2
            job.last_error = "호출 한도 초과(INFO-300)가 반복되어 중단했습니다."
            job.finished_at = dt.datetime.now()
            await s.commit()
            events = [e async for e in progress_stream(s, job_id=job.id, max_events=5)]
        assert "INFO-300" in events[-1].data["lastError"]

    async def test_없는_작업은_error_이벤트다(self, session_factory) -> None:
        async with session_factory() as s:
            events = [e async for e in progress_stream(s, job_id=999999, max_events=5)]
        assert events[0].name == "error"

    async def test_진행_이벤트에_현재_구간이_담긴다(self, session_factory) -> None:
        async with session_factory() as s:
            job = await create_job(s, "USD", *RANGE, chunks_total=4)
            await s.commit()
            events = [e async for e in progress_stream(s, job_id=job.id, max_events=1)]
        data = events[0].data
        assert {"jobId", "currency", "status", "chunksTotal", "chunksDone"} <= set(data)


def test_ProgressEvent가_공개된다() -> None:
    assert ProgressEvent is not None
