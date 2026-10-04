"""가상자산 수집 줄 (T031) — 007 FR-013~FR-015, FR-019, FR-020, research R7-10·R7-11.

**앱 수명과 함께 산다.** `lifespan`에 등록하지 않으면 작업이 "진행 중"으로 박힌다 — 003·005가 겪은
일이다. 주식 수집과 다른 줄이다 — 출처가 달라 한쪽이 막혀도 다른 쪽이 기다리지 않는다(SC-012). 출처
클라이언트는 `lifespan`이 열고 닫는다 — 목록 갱신 줄과 함께 쓰므로 이 줄이 닫으면 안 된다.

- **실패해도 작업을 반드시 마감한다** — 마감하지 않으면 점유가 남아 그 코인을 다시 받을 수 없다
- 실패는 종류를 남긴다(FR-020). 사유에서 사용자 에이전트를 지운다(FR-019)
- 수집이 끝나면 **시작 가능 날짜**를 본다(R7-10) — 요청 구간 앞부분이 비었으면 첫 일봉이 그 날짜다
- 끝나도 일봉이 하나도 없으면 `empty`로 마감한다 — 출처에 그 코인의 시세가 없다
"""

from __future__ import annotations

import asyncio
import logging

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.config.settings import Settings
from src.db.models import JobStatus
from src.ingestion.investing.errors import InvestingError
from src.observability.events import mask_secrets
from src.observability.logging_config import collection_logger
from src.repository import crypto_daily, crypto_job
from src.worker.crypto_queue import CryptoQueue, CryptoWork
from src.worker.crypto_runner import CryptoSource, collect_range

_log = logging.getLogger(__name__)

_ORPHAN_REASON = "실행 프로세스가 끝나 점유를 회수했습니다. 다시 실행하면 이어서 받습니다."
_EMPTY_REASON = "출처가 이 코인의 일봉을 주지 않았습니다."


def _event(event: str, **fields: object) -> None:
    """수집 전용 로그. 코인(출처 식별자)·구간·행 수·실패 종류만 싣는다 — 헤더·사유 문구는 싣지
    않는다."""
    collection_logger().info(event, extra={"event": event, **fields})


def _scrub(message: str, settings: Settings) -> str:
    if settings.investing_user_agent:
        message = message.replace(settings.investing_user_agent, "***")
    return mask_secrets(message) or ""


async def startup(session_factory: async_sessionmaker[AsyncSession]) -> None:
    """기동 시 남은 점유를 푼다. 프로세스가 하나라(CLAUDE.md "단일 워커") 남은 점유는 죽은
    프로세스의 것이다."""
    async with session_factory() as session:
        released = await crypto_job.release_orphans(session, reason=_ORPHAN_REASON)
        await session.commit()
    if released:
        _log.info("기동 시 가상자산 수집 점유 %d건을 회수했습니다.", released)


async def _record_first_available(session: AsyncSession, coin_id: int) -> None:
    """커버리지 시작보다 첫 일봉이 늦으면 그 날이 출처의 첫 일봉이다(R7-10) — 그 앞에는 일봉이
    없다는 확실한 근거다."""
    coverage = await crypto_daily.get_coverage(session, coin_id)
    first = await crypto_daily.first_bar_day(session, coin_id)
    if coverage is not None and first is not None and first > coverage[0]:
        await crypto_daily.record_first_available(session, coin_id, first)
        await session.commit()


async def run_crypto_job(
    session_factory: async_sessionmaker[AsyncSession],
    source: CryptoSource,
    work: CryptoWork,
    *,
    settings: Settings,
) -> JobStatus:
    """일감 하나를 끝까지 돌리고 작업을 마감한다."""
    _event("crypto_collection_started", coin=work.source_id, job=work.job_id,
           start=work.start.isoformat(), end=work.end.isoformat())
    async with session_factory() as session:
        async def on_chunk() -> None:
            await crypto_job.advance_chunk(session, work.job_id)
            await session.commit()

        failure: tuple[str, str] | None = None
        stored = 0
        try:
            stored = await collect_range(
                session, source, coin_id=work.coin_id, source_id=work.source_id,
                start=work.start, end=work.end, chunk_days=settings.investing_chunk_days,
                on_chunk=on_chunk)
        except asyncio.CancelledError:
            raise
        except InvestingError as exc:
            failure = (exc.kind, _scrub(str(exc), settings))
        except Exception as exc:
            _log.exception("가상자산 수집 실패 coin=%s", work.source_id)
            failure = ("network", f"예상하지 못한 오류: {type(exc).__name__}")

        # 받은 청크만으로도 시작 가능 날짜를 알 수 있다 — 실패해도 본다.
        await session.rollback()
        await _record_first_available(session, work.coin_id)
        if failure is None and await crypto_daily.first_bar_day(session, work.coin_id) is None:
            failure = ("empty", _EMPTY_REASON)

        if failure is not None:
            kind, message = failure
            await crypto_job.finish_job(session, work.job_id, JobStatus.FAILED,
                                        error=crypto_job.job_error(kind, message))
            await session.commit()
            _event("crypto_collection_failed", coin=work.source_id, job=work.job_id, kind=kind)
            return JobStatus.FAILED

        await crypto_job.finish_job(session, work.job_id, JobStatus.SUCCEEDED)
        await session.commit()
        _event("crypto_collection_completed", coin=work.source_id, job=work.job_id, rows=stored)
        return JobStatus.SUCCEEDED


async def crypto_worker_loop(
    session_factory: async_sessionmaker[AsyncSession],
    source: CryptoSource,
    queue: CryptoQueue,
    *,
    settings: Settings,
) -> None:
    """큐에서 일감을 꺼내 돌린다. **한 건이 실패해도 루프를 끝내지 않는다** — 끝내면 그 뒤의 모든
    수집이 조용히 멈춘다."""
    while True:
        work = await queue.pop()
        try:
            await run_crypto_job(session_factory, source, work, settings=settings)
        except asyncio.CancelledError:
            raise
        except Exception:  # pragma: no cover — run_crypto_job이 이미 삼킨다
            _log.exception("가상자산 수집 루프 오류 coin=%s", work.source_id)
        finally:
            queue.done(work.coin_id)
