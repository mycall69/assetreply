"""시간축·스트림 계약 검증 (T033, T035) — contracts/rest-api 2·3절.

`activeJob`은 **진행 중일 때만 포함한다.** 값이 없을 때 키를 넣지 않는 것은 002가 세운
규약이다 — 정상 상태에 빈 객체를 두면 화면이 존재 여부가 아니라 내용을 검사해야 한다.

반대로 `busyWith`는 `null`을 명시한다. "확인했고 없다"와 "확인하지 않았다"가 구별되어야
화면이 시작 버튼을 막을지 판단할 수 있다 (FR-029).
"""
from __future__ import annotations

import datetime as dt

import pytest

from src.api.collection_stream import stream_body
from src.api.services.timeline import build_timeline
from src.repository.collection_lock import acquire_lock
from src.repository.job import create_job
from src.worker.queue import reset_queue

RANGE = (dt.date(2020, 1, 1), dt.date(2022, 12, 31))


@pytest.fixture(autouse=True)
def _clean_queue():
    reset_queue()
    yield
    reset_queue()


class Test시간축_응답:
    async def test_필수_필드가_모두_있다(self, session_factory, settings) -> None:
        async with session_factory() as s:
            body = await build_timeline(s, "USD", settings)
        for key in ("generatedAt", "callsToday", "currency", "targetFrom",
                    "targetTo", "coveredFrom", "coveredThrough", "busyWith"):
            assert key in body, key

    async def test_수집_이력이_없으면_커버리지가_null이다(self, session_factory, settings) -> None:
        async with session_factory() as s:
            body = await build_timeline(s, "JPY", settings)
        assert body["coveredFrom"] is None and body["coveredThrough"] is None

    async def test_targetTo는_항상_어제다(self, session_factory, settings) -> None:
        """오늘을 넣으면 영원히 채워지지 않는 구간이 생긴다."""
        async with session_factory() as s:
            body = await build_timeline(s, "USD", settings)
        assert body["targetTo"] == (dt.date.today() - dt.timedelta(days=1)).isoformat()

    async def test_진행_중이_아니면_activeJob_키가_없다(self, session_factory, settings) -> None:
        async with session_factory() as s:
            body = await build_timeline(s, "USD", settings)
        assert "activeJob" not in body

    async def test_진행_중이면_activeJob이_있다(self, session_factory, settings) -> None:
        async with session_factory() as s:
            job = await create_job(s, "USD", *RANGE, chunks_total=3)
            await acquire_lock(s, "USD", job.id)
            await s.commit()
            body = await build_timeline(s, "USD", settings)
        active = body["activeJob"]
        assert isinstance(active, dict)
        for key in ("jobId", "rangeStart", "chunksTotal", "chunksDone",
                    "currentChunk", "state"):
            assert key in active, key

    async def test_rangeStart가_이어받기_지점이다(self, session_factory, settings) -> None:
        """FR-011 — 작업이 어디서부터 시작했는지가 곧 그 값이다."""
        async with session_factory() as s:
            job = await create_job(s, "USD", dt.date(2021, 7, 1), RANGE[1],
                                   chunks_total=2)
            await acquire_lock(s, "USD", job.id)
            await s.commit()
            body = await build_timeline(s, "USD", settings)
        assert body["activeJob"]["rangeStart"] == "2021-07-01"  # type: ignore[index]

    async def test_busyWith는_다른_통화만_담는다(self, session_factory, settings) -> None:
        """자기 자신이 진행 중인 것은 '막을 이유'가 아니다."""
        async with session_factory() as s:
            same = await build_timeline(s, "USD", settings, busy_with="USD")
            other = await build_timeline(s, "USD", settings, busy_with="JPY")
        assert same["busyWith"] is None
        assert other["busyWith"] == "JPY"


class Test스트림:
    async def test_수집이_없으면_idle을_보낸다(self, session_factory, settings) -> None:
        frames = []
        async with session_factory() as s:
            async for frame in stream_body(s, "USD", settings, max_frames=1):
                frames.append(frame)
        assert frames and frames[0].startswith("event: idle")

    async def test_진행_중이면_snapshot을_보낸다(self, session_factory, settings) -> None:
        async with session_factory() as s:
            job = await create_job(s, "USD", *RANGE, chunks_total=3)
            await acquire_lock(s, "USD", job.id)
            await s.commit()
            frames = [f async for f in stream_body(s, "USD", settings, max_frames=1)]
        assert frames[0].startswith("event: snapshot")

    async def test_한_연결에서_수집이_끝나면_idle로_바뀐다(
            self, session_factory, settings, monkeypatch) -> None:
        """006 T113 보강 — FR-045a, FR-046, SC-017. 반복 2026-10-03.

        스트림은 연결 하나(세션 하나)로 오래 산다. 그 세션이 처음 읽은 값에 머물면 워커가 수집을
        끝내도 `snapshot`만 계속 보내, 환율을 기다리던 화면(006 `watchFx`)이 끝을 알지 못한다.
        """
        import src.api.collection_stream as stream_module
        from src.db.models import FxCollectionJob
        from src.repository.collection_lock import release_lock
        from src.repository.job import finish_job

        monkeypatch.setattr(stream_module, "HEARTBEAT_SECONDS", 0)
        async with session_factory() as s:
            job = await create_job(s, "USD", *RANGE, chunks_total=3)
            await acquire_lock(s, "USD", job.id)
            await s.commit()
        async with session_factory() as s:
            stream = stream_body(s, "USD", settings, max_frames=4)
            first = await anext(stream)
            # 워커가 수집을 끝낸다 — `worker/runner.py`처럼 작업을 마감하고 점유를 푼다. 점유만
            # 풀면 작업이 진행 중으로 남아 시간축은 "회수 대기"로 본다(첫 작성 때의 전제 오류).
            async with session_factory() as worker:
                finished = await worker.get(FxCollectionJob, job.id)
                assert finished is not None
                await finish_job(worker, finished, chunks_done=3)
                await release_lock(worker, "USD")
                await worker.commit()
            rest = [frame async for frame in stream]
        assert first.startswith("event: snapshot")
        assert any(frame.startswith("event: idle") for frame in rest), rest

    async def test_프레임에_개행이_섞이지_않는다(self, session_factory, settings) -> None:
        """data 줄이 쪼개지면 클라이언트가 이벤트를 받지 못한다."""
        async with session_factory() as s:
            frames = [f async for f in stream_body(s, "USD", settings, max_frames=1)]
        data_line = [ln for ln in frames[0].splitlines() if ln.startswith("data: ")]
        assert len(data_line) == 1

    async def test_snapshot_본문이_timeline과_같은_구조다(
        self, session_factory, settings
    ) -> None:
        """화면이 최초 진입과 갱신에서 다른 형태를 다루지 않게 한다 (FR-010)."""
        import json

        async with session_factory() as s:
            job = await create_job(s, "USD", *RANGE, chunks_total=3)
            await acquire_lock(s, "USD", job.id)
            await s.commit()
            rest = await build_timeline(s, "USD", settings)
            frames = [f async for f in stream_body(s, "USD", settings, max_frames=1)]
        payload = json.loads(frames[0].split("data: ", 1)[1])
        assert set(payload) == set(rest)
