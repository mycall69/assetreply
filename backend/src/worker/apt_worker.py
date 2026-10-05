"""부동산 수집 태스크 — 안에서 두 줄(실거래·목록) (009 T024, FR-011~FR-014, SC-011, SC-012).

**앱 수명과 함께 산다.** `lifespan`에 등록하지 않으면 작업이 "진행 중"으로 박힌다(003·005가 겪은
일). 출처가 다른 자산군과 달라 **수집 태스크가 따로다**(8번째). 태스크 안에서 실거래 줄과 목록 줄로
나뉜다 — 시·군·구 전체 이력(약 280회)이 행정구역 갱신·기본 정보 채우기를 막지 않는다. 두 줄은 같은
클라이언트(관문)를 쓴다 — 동시 요청 수와 자료별 하루 호출 수를 함께 지킨다.

- **실패해도 작업을 반드시 마감한다** — 마감하지 않으면 점유가 남아 그 대상을 다시 받을 수 없다
- 실패는 종류를 남긴다(FR-014). 사유는 클라이언트가 인증키를 지운 문구다(FR-013) — 한 번 더 가린다
- 수집 전용 로그에는 대상·구간·종류만 싣는다 — 사유 문구·URL은 싣지 않는다
"""

from __future__ import annotations

import asyncio
import datetime as dt
import logging
from collections.abc import Callable
from typing import Protocol

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.config.settings import Settings
from src.db.models import JobStatus
from src.ingestion.datagokr.errors import DataGoKrError
from src.observability.events import mask_secrets
from src.observability.logging_config import collection_logger
from src.repository import apt_job
from src.worker.apt_list_runner import (
    BasisSource,
    ComplexListSource,
    RegionSource,
    collect_details,
    collect_regions,
)
from src.worker.apt_queue import AptQueue, AptWork
from src.worker.apt_trade_runner import (
    ProbeStartMissing,
    TradeRun,
    TradeSource,
    collect_trades,
    sync_complexes,
)

_log = logging.getLogger(__name__)

_ORPHAN_REASON = ("점유 회수 — 실행 프로세스가 끝나 점유를 풀었습니다. "
                  "다시 실행하면 이어서 받습니다.")


class AptSource(TradeSource, RegionSource, BasisSource, ComplexListSource, Protocol):
    """부동산 수집이 부르는 출처 — 공공데이터포털 클라이언트 하나다."""


_shared: AptSource | None = None


def set_shared_source(source: AptSource | None) -> None:
    """앱 수명의 공공데이터포털 클라이언트를 둔다(`lifespan`). 요청 경로(단지 목록)와 수집 태스크가
    같은 관문을 지난다 — 동시 요청 수와 하루 호출 수를 함께 지킨다."""
    global _shared
    _shared = source


def shared_source() -> AptSource:
    if _shared is None:
        raise RuntimeError("공공데이터포털 클라이언트가 없습니다 — 앱 수명(lifespan) 밖입니다.")
    return _shared


def utc_now() -> dt.datetime:
    """저장용 현재 시각 — UTC, 시간대 없는 값(헌법 시계열 불변식)."""
    return dt.datetime.now(dt.UTC).replace(tzinfo=None)


def _event(event: str, **fields: object) -> None:
    collection_logger().info(event, extra={"event": event, **fields})


def _failure(exc: BaseException) -> tuple[str, str]:
    if isinstance(exc, DataGoKrError):
        return exc.kind, mask_secrets(str(exc)) or ""
    if isinstance(exc, ProbeStartMissing):
        return "format", str(exc)
    return "network", f"예상하지 못한 오류: {type(exc).__name__}"


async def _finish(factory: async_sessionmaker[AsyncSession], work: AptWork, *,
                  failure: tuple[str, str] | None, now: dt.datetime) -> JobStatus:
    status = JobStatus.SUCCEEDED if failure is None else JobStatus.FAILED
    error = None if failure is None else apt_job.job_error(*failure)
    async with factory() as session:
        await apt_job.finish_job(session, work.job_id, status, error=error, now=now)
        await session.commit()
    return status


async def startup(factory: async_sessionmaker[AsyncSession]) -> None:
    """기동 시 남은 점유를 푼다. 프로세스가 하나라(CLAUDE.md "단일 워커") 남은 점유는 죽은
    프로세스의 것이다."""
    async with factory() as session:
        released = await apt_job.release_orphans(session, reason=_ORPHAN_REASON)
        await session.commit()
    if released:
        _log.info("기동 시 부동산 수집 점유 %d건을 회수했습니다.", released)


async def run_trade_job(factory: async_sessionmaker[AsyncSession], source: TradeSource,
                        work: AptWork, *, settings: Settings, now: dt.datetime) -> JobStatus:
    """시·군·구 하나의 실거래를 받고 작업을 마감한다. `now`는 UTC — 확인한 날(한국 시간)과 저장
    시각의 기준이다."""
    _event("apt_collection_started", kind=work.kind, lawd_cd=work.target, job=work.job_id)
    run = TradeRun()
    failure: tuple[str, str] | None = None
    try:
        await collect_trades(factory, source, work.target, work.job_id, settings=settings,
                             now=now, run=run)
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        if not isinstance(exc, DataGoKrError | ProbeStartMissing):
            _log.exception("실거래 수집 실패 lawd_cd=%s", work.target)
        failure = _failure(exc)
    try:
        await sync_complexes(factory, work.target, run)
    except asyncio.CancelledError:
        raise
    except Exception:
        _log.exception("단지 맞추기 실패 lawd_cd=%s", work.target)
    status = await _finish(factory, work, failure=failure, now=now)
    span: dict[str, str | None] = {"first": None, "last": None}
    if run.months:
        span = {"first": f"{run.months[0][:4]}-{run.months[0][4:]}",
                "last": f"{run.months[-1][:4]}-{run.months[-1][4:]}"}
    if failure is None:
        _event("apt_collection_completed", kind=work.kind, lawd_cd=work.target,
               job=work.job_id, months=len(run.months), **span)
    else:
        _event("apt_collection_failed", kind=failure[0], lawd_cd=work.target,
               job=work.job_id, months=len(run.months), **span)
    return status


async def run_list_job(factory: async_sessionmaker[AsyncSession], source: AptSource,
                       work: AptWork, *, settings: Settings, now: dt.datetime) -> JobStatus:
    """행정구역(전국) 또는 그 동의 단지 기본 정보를 받고 작업을 마감한다."""
    _event("apt_collection_started", kind=work.kind, target=work.target, job=work.job_id)
    failure: tuple[str, str] | None = None
    try:
        if work.kind == "region":
            await collect_regions(factory, source, work.job_id, now=now)
        else:
            await collect_details(factory, source, work.job_id, work.target, now=now)
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        if not isinstance(exc, DataGoKrError):
            _log.exception("목록 수집 실패 kind=%s target=%s", work.kind, work.target)
        failure = _failure(exc)
    status = await _finish(factory, work, failure=failure, now=now)
    if failure is None:
        _event("apt_collection_completed", kind=work.kind, target=work.target, job=work.job_id)
    else:
        _event("apt_collection_failed", kind=failure[0], target=work.target, job=work.job_id)
    return status


async def _lane(factory: async_sessionmaker[AsyncSession], source: AptSource, queue: AptQueue,
                *, settings: Settings, clock: Callable[[], dt.datetime]) -> None:
    """큐에서 일감을 꺼내 돌린다. **한 건이 실패해도 루프를 끝내지 않는다** — 끝내면 그 뒤의 모든
    수집이 조용히 멈춘다."""
    while True:
        work = await queue.pop()
        try:
            runner = run_trade_job if work.kind == "trade" else run_list_job
            await runner(factory, source, work, settings=settings, now=clock())
        except asyncio.CancelledError:
            raise
        except Exception:  # pragma: no cover — 실행 함수가 이미 삼킨다
            _log.exception("부동산 수집 루프 오류 kind=%s target=%s", work.kind, work.target)
        finally:
            queue.done(work.kind, work.target)


async def apt_worker_loop(factory: async_sessionmaker[AsyncSession], source: AptSource,
                          trade_queue: AptQueue, list_queue: AptQueue, *, settings: Settings,
                          clock: Callable[[], dt.datetime] = utc_now) -> None:
    """부동산 수집 태스크 — 실거래 줄과 목록 줄을 함께 돌린다(서로 기다리지 않는다)."""
    async with asyncio.TaskGroup() as group:
        group.create_task(_lane(factory, source, trade_queue, settings=settings, clock=clock))
        group.create_task(_lane(factory, source, list_queue, settings=settings, clock=clock))
