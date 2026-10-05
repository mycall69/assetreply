"""부동산 수집 진행 (T018) — 009 FR-011, FR-014, contracts/rest-api `GET /api/realestate/progress`.

008과 같은 사건·머리글이다. 스냅샷은 종류마다 분모가 달라도 한 모양(`done`·`total`)이다 — 실거래는
받은 달/받을 달(처음부터 받을 달을 안다), 기본 정보는 받은 단지/단지 수, 행정구역은 받은 쪽/쪽 수.
실패는 종류를 싣고 사유에 인증키가 없다. **프레임마다 읽기 트랜잭션을 끝낸다**(006 R6-19).
"""
from __future__ import annotations

import json

import pytest

from src.api.routes.realestate_progress import get_progress, stream_body
from src.db.models import JobStatus
from src.repository import apt_job
from tests.integration.apt_support import NOW_UTC


def parse(frame: str) -> tuple[str, dict]:  # type: ignore[type-arg]
    lines = dict(line.split(": ", 1) for line in frame.strip().splitlines())
    return lines["event"], json.loads(lines["data"])


async def make_job(session_factory, kind: str = "trade", target: str = "11710",  # type: ignore[no-untyped-def]
                   total: int = 217) -> int:
    async with session_factory() as s:
        job_id, _ = await apt_job.acquire_or_get_running(s, kind, target, total=total)
        await s.commit()
    return job_id


async def frames(session_factory, job_id: int, max_frames: int = 5):  # type: ignore[no-untyped-def]
    async with session_factory() as s:
        return [parse(f) async for f in stream_body(s, job_id, max_frames=max_frames)]


class Test진행:
    @pytest.mark.parametrize(("kind", "target", "total"), [
        ("trade", "11710", 217), ("complex_details", "1171010700", 23), ("region", "regions", 21)])
    async def test_스냅샷은_한_모양(self, session_factory, kind: str, target: str,  # type: ignore[no-untyped-def]
                             total: int) -> None:
        job_id = await make_job(session_factory, kind, target, total)
        [(name, body)] = await frames(session_factory, job_id, max_frames=1)
        assert name == "snapshot"
        assert body == {"jobId": job_id, "kind": kind, "target": target, "status": "running",
                        "done": 0, "total": total}

    async def test_끝나면_completed(self, session_factory) -> None:  # type: ignore[no-untyped-def]
        job_id = await make_job(session_factory)
        async with session_factory() as s:
            await apt_job.set_progress(s, job_id, done=217)
            await apt_job.finish_job(s, job_id, JobStatus.SUCCEEDED, now=NOW_UTC)
            await s.commit()
        events = await frames(session_factory, job_id)
        assert [name for name, _ in events] == ["snapshot", "completed"]
        assert events[0][1]["done"] == 217
        assert events[-1][1] == {"jobId": job_id}

    async def test_실패는_종류와_사유를_싣는다(self, session_factory) -> None:  # type: ignore[no-untyped-def]
        job_id = await make_job(session_factory)
        async with session_factory() as s:
            await apt_job.finish_job(s, job_id, JobStatus.FAILED, now=NOW_UTC,
                                     error=apt_job.job_error("rate_limited", "하루 한도"))
            await s.commit()
        events = await frames(session_factory, job_id)
        assert events[-1] == ("failed", {"jobId": job_id, "kind": "rate_limited",
                                         "reason": "하루 한도"})

    async def test_모르는_작업(self, session_factory) -> None:  # type: ignore[no-untyped-def]
        events = await frames(session_factory, 987654)
        assert events == [("failed", {"jobId": 987654, "kind": None,
                                      "reason": "알 수 없는 작업입니다."})]

    async def test_프레임마다_새_스냅샷을_읽는다(self, session_factory, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        """같은 연결이 첫 스냅샷에 머물면 진행·완료가 오지 않는다(006 R6-19)."""
        from src.api.routes import realestate_progress

        job_id = await make_job(session_factory)

        async def no_wait(_: float) -> None:
            async with session_factory() as s:
                await apt_job.set_progress(s, job_id, done=120)
                await s.commit()

        monkeypatch.setattr(realestate_progress.asyncio, "sleep", no_wait)
        events = await frames(session_factory, job_id, max_frames=2)
        assert [b["done"] for _, b in events] == [0, 120]

    async def test_스트림_머리글(self, session_factory) -> None:  # type: ignore[no-untyped-def]
        job_id = await make_job(session_factory)
        async with session_factory() as s:
            response = await get_progress(s, job_id)
        assert "no-transform" in response.headers["cache-control"]
        assert response.headers["x-accel-buffering"] == "no"
        assert response.media_type == "text/event-stream"
