"""가상자산 수집 진행 (T025) — 007 FR-013, FR-020, SC-003, contracts/rest-api `GET
/api/crypto/progress`.

006 `GET /api/stocks/progress`와 같은 사건과 머리글이다. 진행은 **받은 날 / 받을 날**(달력
일수)이다(006 FR-045a). 실패는 종류(`kind`)를 싣는다 — 화면이 사유별로 다른 문구를 낸다(FR-020).
"""
from __future__ import annotations

import datetime as dt
import json

from src.api.routes.crypto_progress import get_progress, stream_body
from src.db.models import JobStatus
from src.repository import crypto_daily, crypto_job
from tests.integration.crypto_support import add_coin

D = dt.date.fromisoformat


def parse(frame: str) -> tuple[str, dict]:
    lines = dict(line.split(": ", 1) for line in frame.strip().splitlines())
    return lines["event"], json.loads(lines["data"])


async def make_job(session_factory, coin_id: int) -> int:  # type: ignore[no-untyped-def]
    async with session_factory() as s:
        job_id, _ = await crypto_job.acquire_or_get_running(
            s, coin_id, D("2020-01-01"), D("2021-12-31"), chunks_total=2)
        await s.commit()
    return job_id


async def frames(session_factory, job_id: int, max_frames: int = 5) -> list[tuple[str, dict]]:  # type: ignore[no-untyped-def]
    async with session_factory() as s:
        return [parse(f) async for f in stream_body(s, job_id, max_frames=max_frames)]


async def test_진행은_받은_날과_받을_날이다(session_factory) -> None:
    coin_id = await add_coin(session_factory)
    job_id = await make_job(session_factory, coin_id)
    async with session_factory() as s:
        await crypto_daily.record_coverage(s, coin_id, D("2020-01-01"), D("2021-12-30"))
        await crypto_job.advance_chunk(s, job_id)
        await s.commit()
    [(name, body)] = await frames(session_factory, job_id, max_frames=1)
    assert name == "snapshot"
    assert body == {"jobId": job_id, "status": "running", "chunksDone": 1, "chunksTotal": 2,
                    "daysDone": 730, "daysTotal": 731, "missingFrom": "2020-01-01",
                    "missingThrough": "2021-12-31"}


async def test_끝나면_completed를_보내고_닫는다(session_factory) -> None:
    coin_id = await add_coin(session_factory)
    job_id = await make_job(session_factory, coin_id)
    async with session_factory() as s:
        await crypto_job.finish_job(s, job_id, JobStatus.SUCCEEDED)
        await s.commit()
    events = await frames(session_factory, job_id)
    assert [name for name, _ in events] == ["snapshot", "completed"]
    assert events[-1][1] == {"jobId": job_id}


async def test_실패하면_사유와_종류를_보낸다(session_factory) -> None:
    coin_id = await add_coin(session_factory)
    job_id = await make_job(session_factory, coin_id)
    async with session_factory() as s:
        error = crypto_job.job_error("blocked", "시세 출처가 접근을 막았습니다.")
        await crypto_job.finish_job(s, job_id, JobStatus.FAILED, error=error)
        await s.commit()
    name, body = (await frames(session_factory, job_id))[-1]
    assert name == "failed"
    assert body == {"jobId": job_id, "reason": "시세 출처가 접근을 막았습니다.", "kind": "blocked"}


async def test_없는_작업은_실패다(session_factory) -> None:
    [(name, body)] = await frames(session_factory, 999999)
    assert name == "failed" and body["jobId"] == 999999


async def test_프레임마다_새로_읽는다(session_factory, monkeypatch) -> None:
    """006 R6-19 — 앞 프레임의 읽기 트랜잭션이 남으면 MySQL이 첫 스냅샷을 계속 보여 진행이 멈춘
    것처럼 보인다."""
    from src.api.routes import crypto_progress

    monkeypatch.setattr(crypto_progress, "POLL_SECONDS", 0.01)
    coin_id = await add_coin(session_factory)
    job_id = await make_job(session_factory, coin_id)
    async with session_factory() as reader:
        stream = stream_body(reader, job_id)
        _, first = parse(await anext(stream))
        async with session_factory() as writer:
            await crypto_job.advance_chunk(writer, job_id)
            await writer.commit()
        _, second = parse(await anext(stream))
        await stream.aclose()
    assert (first["chunksDone"], second["chunksDone"]) == (0, 1)


async def test_머리글이_변환을_막는다() -> None:
    response = await get_progress(session=None, job_id=1)  # type: ignore[arg-type]
    assert "no-transform" in response.headers["cache-control"]
    assert response.headers["x-accel-buffering"] == "no"
