"""예금 금리 수집 줄 (T019) — 008 FR-011~FR-016, SC-011, SC-012, research R8-6·R8-9.

**앱 수명과 함께 산다.** `lifespan`에 등록하지 않으면 작업이 "진행 중"으로 박힌다 — 003·005가 겪은
일이다. **환율 수집과 다른 줄이다**(SC-012) — 같은 ECOS 출처라 동시 요청 수와 한도 초과 백오프는
관문(`EcosGate`)이 두 줄을 함께 지키지만, 한쪽 작업이 다른 쪽을 기다리지는 않는다.

- **실패해도 작업을 반드시 마감한다** — 마감하지 않으면 점유가 남아 그 투자처를 다시 받을 수 없다
- 실패는 종류를 남긴다(FR-016). 사유에서 인증키를 지운다(FR-014, SC-011) — 키는 URL 경로에 있다
- 받은 달 수는 필요한 구간 중 받은 구간 안의 달이다 — 미발표 달은 받을 수 없어 받을 달보다 적을 수
  있다
"""

from __future__ import annotations

import asyncio
import datetime as dt
import logging
from collections.abc import Callable

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.config.settings import Settings
from src.db.models import JobStatus
from src.ingestion.ecos.deposit_parse import deposit_failure_kind
from src.ingestion.ecos.errors import SourceError
from src.observability.events import mask_secrets
from src.observability.logging_config import collection_logger
from src.repository import deposit_job
from src.worker.deposit_queue import DepositQueue, DepositWork
from src.worker.deposit_runner import DepositSource, collect_institution, months_between

_log = logging.getLogger(__name__)

_ORPHAN_REASON = "실행 프로세스가 끝나 점유를 회수했습니다. 다시 실행하면 다시 받습니다."


def _event(event: str, **fields: object) -> None:
    """수집 전용 로그. 투자처·구간·실패 종류만 싣는다 — URL·사유 문구는 싣지 않는다(인증키)."""
    collection_logger().info(event, extra={"event": event, **fields})


def _scrub(message: str, settings: Settings) -> str:
    key = settings.ecos_api_key.reveal()
    if key:
        message = message.replace(key, "***")
    return mask_secrets(message) or ""


def utc_now() -> dt.datetime:
    """저장용 현재 시각 — UTC, 시간대 없는 값(헌법 시계열 불변식)."""
    return dt.datetime.now(dt.UTC).replace(tzinfo=None)


async def startup(session_factory: async_sessionmaker[AsyncSession]) -> None:
    """기동 시 남은 점유를 푼다. 프로세스가 하나라(CLAUDE.md "단일 워커") 남은 점유는 죽은
    프로세스의 것이다."""
    async with session_factory() as session:
        released = await deposit_job.release_orphans(session, reason=_ORPHAN_REASON)
        await session.commit()
    if released:
        _log.info("기동 시 예금 수집 점유 %d건을 회수했습니다.", released)


async def run_deposit_job(
    session_factory: async_sessionmaker[AsyncSession],
    source: DepositSource,
    work: DepositWork,
    *,
    settings: Settings,
    now: dt.datetime,
) -> JobStatus:
    """일감 하나를 끝까지 돌리고 작업을 마감한다. `now`는 UTC — 확인한 날(한국 시간)과 저장 시각의
    기준이다."""
    _event("deposit_collection_started", institution=work.institution, job=work.job_id,
           start=f"{work.start_month:%Y-%m}", end=f"{work.end_month:%Y-%m}")
    async with session_factory() as session:
        failure: tuple[str, str] | None = None
        try:
            collected = await collect_institution(
                session, source, institution=work.institution, to_month=work.end_month,
                overlap_months=settings.deposit_recheck_overlap_months, now=now)
            done = months_between(max(work.start_month, collected.first_month),
                                  min(work.end_month, collected.latest_month))
            await deposit_job.set_months_done(session, work.job_id, done)
            await deposit_job.finish_job(session, work.job_id, JobStatus.SUCCEEDED, now=now)
            await session.commit()
        except asyncio.CancelledError:
            raise
        except SourceError as exc:
            failure = (deposit_failure_kind(exc), _scrub(str(exc), settings))
        except Exception as exc:
            _log.exception("예금 금리 수집 실패 institution=%s", work.institution)
            failure = ("network", f"예상하지 못한 오류: {type(exc).__name__}")

        if failure is not None:
            # 받은 것도 남기지 않는다 — 요청이 하나라 반쪽 결과가 없다. 확인한 날도 그대로다
            # (FR-010).
            await session.rollback()
            kind, message = failure
            await deposit_job.finish_job(session, work.job_id, JobStatus.FAILED,
                                         error=deposit_job.job_error(kind, message), now=now)
            await session.commit()
            _event("deposit_collection_failed", institution=work.institution, job=work.job_id,
                   kind=kind)
            return JobStatus.FAILED

    _event("deposit_collection_completed", institution=work.institution, job=work.job_id,
           latest_month=f"{collected.latest_month:%Y-%m}")
    return JobStatus.SUCCEEDED


async def deposit_worker_loop(
    session_factory: async_sessionmaker[AsyncSession],
    source: DepositSource,
    queue: DepositQueue,
    *,
    settings: Settings,
    clock: Callable[[], dt.datetime] = utc_now,
) -> None:
    """큐에서 일감을 꺼내 돌린다. **한 건이 실패해도 루프를 끝내지 않는다** — 끝내면 그 뒤의 모든
    수집이 조용히 멈춘다."""
    while True:
        work = await queue.pop()
        try:
            await run_deposit_job(session_factory, source, work, settings=settings, now=clock())
        except asyncio.CancelledError:
            raise
        except Exception:  # pragma: no cover — run_deposit_job이 이미 삼킨다
            _log.exception("예금 수집 루프 오류 institution=%s", work.institution)
        finally:
            queue.done(work.institution)
