"""예금 수집 진행 (T014) — 008 FR-011, FR-016, contracts/rest-api `GET /api/deposit/progress`.

진행은 **받은 달 / 받을 달**이고, 받을 달은 그 실행에 **필요한 구간**(시작 달 ~ 이번 달)이라 처음
받을 때도 안다(analyze I1). 미발표 달은 끝까지 받지 못하므로 완료 때 받은 달 < 받을 달일 수 있다.
실패는 종류를 싣고, 사유에 인증키가 없다. **프레임마다 읽기 트랜잭션을 끝낸다**(006 R6-19).
"""
from __future__ import annotations

import datetime as dt
import json

from src.api.routes.deposit_progress import get_progress, stream_body
from src.db.models import JobStatus
from src.repository import deposit_job
from tests.integration.deposit_support import NOW_UTC, seed_rates

D = dt.date.fromisoformat


def parse(frame: str) -> tuple[str, dict]:  # type: ignore[type-arg]
    lines = dict(line.split(": ", 1) for line in frame.strip().splitlines())
    return lines["event"], json.loads(lines["data"])


async def make_job(session_factory) -> int:  # type: ignore[no-untyped-def]
    async with session_factory() as s:
        job_id, _ = await deposit_job.acquire_or_get_running(
            s, "commercial_bank", D("2020-01-01"), D("2026-10-01"), months_total=82)
        await s.commit()
    return job_id


async def frames(session_factory, job_id: int, max_frames: int = 5):  # type: ignore[no-untyped-def]
    async with session_factory() as s:
        return [parse(f) async for f in stream_body(s, job_id, max_frames=max_frames)]


class Test진행:
    async def test_처음_받을_때도_받을_달을_안다(self, session_factory) -> None:
        job_id = await make_job(session_factory)
        [(name, body)] = await frames(session_factory, job_id, max_frames=1)
        assert name == "snapshot"
        assert body == {"jobId": job_id, "status": "running", "institution": "commercial_bank",
                        "monthsDone": 0, "monthsTotal": 82, "missingFrom": "2020-01",
                        "missingThrough": "2026-10"}

    async def test_받은_달은_필요한_구간_중_받은_구간_안의_달이다(self, session_factory) -> None:
        job_id = await make_job(session_factory)
        await seed_rates(session_factory)
        [(_, body)] = await frames(session_factory, job_id, max_frames=1)
        assert (body["monthsDone"], body["monthsTotal"]) == (80, 82)

    async def test_끝나면_completed와_마지막_발표_달(self, session_factory) -> None:
        job_id = await make_job(session_factory)
        await seed_rates(session_factory)
        async with session_factory() as s:
            await deposit_job.finish_job(s, job_id, JobStatus.SUCCEEDED, now=NOW_UTC)
            await s.commit()
        events = await frames(session_factory, job_id)
        assert [name for name, _ in events] == ["snapshot", "completed"]
        assert events[-1][1] == {"jobId": job_id, "latestMonth": "2026-08"}

    async def test_실패는_종류와_사유를_싣는다(self, session_factory) -> None:
        job_id = await make_job(session_factory)
        async with session_factory() as s:
            await deposit_job.finish_job(
                s, job_id, JobStatus.FAILED,
                error=deposit_job.job_error("auth", "인증키 오류"), now=NOW_UTC)
            await s.commit()
        events = await frames(session_factory, job_id)
        assert events[-1] == ("failed", {"jobId": job_id, "reason": "인증키 오류", "kind": "auth"})

    async def test_프레임마다_새_스냅샷을_읽는다(self, session_factory, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        """같은 연결이 첫 스냅샷에 머물면 진행·완료가 오지 않는다(006 R6-19)."""
        from src.api.routes import deposit_progress

        job_id = await make_job(session_factory)

        async def no_wait(_: float) -> None:
            await seed_rates(session_factory)

        monkeypatch.setattr(deposit_progress.asyncio, "sleep", no_wait)
        events = await frames(session_factory, job_id, max_frames=2)
        assert [b["monthsDone"] for _, b in events] == [0, 80]

    async def test_스트림_머리글(self, session_factory) -> None:
        job_id = await make_job(session_factory)
        async with session_factory() as s:
            response = await get_progress(s, job_id)
        assert "no-transform" in response.headers["cache-control"]
        assert response.media_type == "text/event-stream"
