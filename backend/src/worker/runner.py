"""수집 실행 태스크 (T022, T026, T029) — research R3-1, FR-001·FR-007.

큐에서 통화를 꺼내 수집을 돌린다. **HTTP 요청과 수명을 공유하지 않으므로 화면을 떠나도
진행이 이어진다** (FR-001).

이벤트 발행이 여기 있는 이유는 `ingestion/`이 관측을 모르게 두기 위해서다. 수집 로직은
"무엇을 받아와 어떻게 저장하는가"만 알고, "무슨 일이 있었는지 어떻게 남기는가"는 이
계층이 책임진다 (헌법 원칙 IV).
"""

from __future__ import annotations

import asyncio
import contextlib
import datetime as dt
import logging

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.config.settings import Settings, load_settings
from src.db.models import FxCollectionJob
from src.ingestion.collector import collect_range, next_start_date, split_into_chunks
from src.ingestion.ecos.errors import SourceError, SourceRateLimited
from src.ingestion.protocols import FxRateSource
from src.observability.events import (
    CHUNK_EMPTY,
    CHUNK_FAILED,
    CHUNK_REQUESTED,
    CHUNK_STORED,
    JOB_FINISHED,
    JOB_STARTED,
    RATE_LIMITED,
    CollectionEvent,
)
from src.observability.sinks import EventPublisher, db_sink_for
from src.repository.collection_event import prune_to_recent_jobs
from src.repository.collection_lock import acquire_lock, heartbeat, release_lock
from src.repository.job import create_job, finalize_as_partial, finish_job
from src.worker.queue import StartQueue

_log = logging.getLogger(__name__)


async def run_once(
    session_factory: async_sessionmaker[AsyncSession],
    source: FxRateSource,
    currency_code: str,
    start: dt.date,
    end: dt.date,
    *,
    chunk_days: int,
    resume: bool = False,
    settings: Settings | None = None,
) -> FxCollectionJob | None:
    """한 통화의 수집을 끝까지 돌린다. 만들어진 작업을 돌려준다.

    `resume=True`면 이미 수집된 구간의 다음 날부터 받는다 (FR-008). 이미 전부 받았으면
    **외부 호출 없이** 완료로 끝낸다 (FR-009) — 사용자가 "다시 확인"을 눌러도 한도를
    쓰지 않아야 한다.

    점유를 잡지 못하면 `None`을 돌려준다. 이미 같은 통화가 진행 중이라는 뜻이다.
    """
    cfg = settings or load_settings()

    async with session_factory() as session:
        if resume:
            start = await next_start_date(session, currency_code, default=start)

        # 받을 것이 없으면 청크가 0개다. 작업은 만들되 외부를 호출하지 않는다 —
        # 사용자가 "눌렀는데 아무 일도 없었다"고 느끼지 않게 한다 (FR-009).
        chunks = split_into_chunks(start, end, chunk_days=chunk_days) if start <= end else []

        job = await create_job(session, currency_code, start, end,
                               chunks_total=len(chunks))
        if await acquire_lock(session, currency_code, job.id) is not None:
            await session.rollback()
            return None
        await session.commit()
        job_id = job.id

        publisher = EventPublisher(db_sink=db_sink_for(session))
        await publisher.publish(CollectionEvent(
            job_id=job_id, currency=currency_code, kind=JOB_STARTED,
            chunk_from=start, chunk_to=end))

        done, error = 0, None
        try:
            for chunk_start, chunk_end in chunks:
                await publisher.publish(CollectionEvent(
                    job_id=job_id, currency=currency_code, kind=CHUNK_REQUESTED,
                    chunk_from=chunk_start, chunk_to=chunk_end))

                stored = await collect_range(
                    session, source, currency_code, chunk_start, chunk_end,
                    chunk_days=chunk_days)

                # 출처가 값을 주지 않은 구간과 수집이 실패한 구간을 **반드시 구별한다**.
                # 합치면 나중에 시계열에 공백이 생겼을 때 원인을 좁힐 수 없다 (FR-021).
                await publisher.publish(CollectionEvent(
                    job_id=job_id, currency=currency_code,
                    kind=CHUNK_STORED if stored else CHUNK_EMPTY,
                    chunk_from=chunk_start, chunk_to=chunk_end,
                    rows_stored=stored if stored else None))

                done += 1
                await heartbeat(session, currency_code)
                await session.commit()
        except SourceRateLimited as exc:
            error = f"호출 한도를 소진했습니다: {exc}"
            await publisher.publish(CollectionEvent(
                job_id=job_id, currency=currency_code, kind=RATE_LIMITED, detail=error))
        except SourceError as exc:
            error = str(exc)
            await publisher.publish(CollectionEvent(
                job_id=job_id, currency=currency_code, kind=CHUNK_FAILED, detail=error))

        await finish_job(session, job, chunks_done=done, error=error)
        await publisher.publish(CollectionEvent(
            job_id=job_id, currency=currency_code, kind=JOB_FINISHED,
            detail=error or f"{done}/{len(chunks)} 구간 완료"))

        # 누락 건수는 작업 종료 시 한 번 쓴다. 사건마다 갱신하면 실패가 잦을 때 그
        # 갱신 자체가 부하가 된다 (research R3-4).
        job.events_dropped = publisher.dropped

        # 새 작업이 생길 때만 보관 경계가 밀리므로 여기서 정리하면 경계가 항상 맞는다.
        await prune_to_recent_jobs(session, currency_code,
                                   keep_jobs=cfg.event_retention_jobs)
        await release_lock(session, currency_code)
        await session.commit()
        return job


async def worker_loop(
    session_factory: async_sessionmaker[AsyncSession],
    source: FxRateSource,
    queue: StartQueue,
    *,
    settings: Settings | None = None,
) -> None:
    """큐를 비우며 수집을 돈다. `lifespan`이 띄우고 종료 시 취소한다.

    취소되면 진행 중이던 작업을 **부분 완료로 확정한 뒤** 끝낸다 (FR-007). 진행 중으로
    남기면 다음 기동에서 정리가 필요해지고, 그 사이 점유가 수집을 막는다.
    """
    cfg = settings or load_settings()
    current: str | None = None
    try:
        while True:
            current = await queue.pop()
            try:
                await run_once(
                    session_factory, source, current,
                    cfg.probe_start(current), dt.date.today() - dt.timedelta(days=1),
                    chunk_days=cfg.ecos_chunk_days, resume=True, settings=cfg)
            except Exception:  # noqa: BLE001 — 한 통화의 실패가 워커를 죽여서는 안 된다
                _log.exception("%s 수집에 실패했습니다.", current)
            finally:
                queue.done(current)
                current = None
    except asyncio.CancelledError:
        if current is not None:
            await _finalize_on_shutdown(session_factory, current)
            queue.done(current)
        raise


async def _finalize_on_shutdown(
    session_factory: async_sessionmaker[AsyncSession], currency_code: str
) -> None:
    """종료 시 진행 중이던 작업을 부분 완료로 확정하고 점유를 푼다 (FR-007)."""
    with contextlib.suppress(Exception):
        async with session_factory() as session:
            from sqlalchemy import select

            from src.db.models import JobStatus

            job = (await session.execute(
                select(FxCollectionJob)
                .where(FxCollectionJob.currency_code == currency_code)
                .where(FxCollectionJob.status == JobStatus.RUNNING)
                .order_by(FxCollectionJob.id.desc()))).scalars().first()
            if job is not None:
                await finalize_as_partial(
                    session, job, reason="서버가 종료되어 수집을 중단했습니다.")
            await release_lock(session, currency_code)
            await session.commit()
