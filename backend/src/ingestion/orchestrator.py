"""수집 작업 오케스트레이션 (T095).

잠금 획득 → 작업 생성 → 청크 수집 → 상태 전이 → 잠금 해제.

FR-013: 중단되어도 이미 커밋된 구간과 커버리지는 유효하게 남는다.
FR-015a/b: 통화당 진행 중 작업은 하나이며, 중복 요청은 기존 작업에 합류한다.
FR-015c: 서로 다른 통화는 병행할 수 있다.
"""

from __future__ import annotations

import asyncio
import datetime as dt

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.db.models import FxCollectionJob
from src.ingestion.collector import collect_range, split_into_chunks
from src.ingestion.ecos.errors import SourceError
from src.ingestion.protocols import FxRateSource
from src.repository.collection_lock import acquire_lock, heartbeat, release_lock
from src.repository.job import create_job, finish_job, get_job


async def run_collection(
    session: AsyncSession,
    source: FxRateSource,
    currency_code: str,
    start: dt.date,
    end: dt.date,
    *,
    chunk_days: int,
) -> FxCollectionJob:
    """한 통화의 수집을 실행한다.

    이미 진행 중이면 새 작업을 만들지 않고 그 작업을 돌려준다 (FR-015b).
    """
    chunks = split_into_chunks(start, end, chunk_days=chunk_days)
    job = await create_job(session, currency_code, start, end, chunks_total=len(chunks))

    existing_id = await acquire_lock(session, currency_code, job.id)
    if existing_id is not None:
        await session.rollback()
        existing = await get_job(session, existing_id)
        assert existing is not None
        return existing

    await session.commit()

    done = 0
    error: str | None = None
    try:
        for chunk_start, chunk_end in chunks:
            await collect_range(session, source, currency_code, chunk_start, chunk_end,
                                chunk_days=chunk_days)
            done += 1
            # 청크 커밋 때 함께 갱신 — 추가 왕복이 없다 (research R6)
            await heartbeat(session, currency_code)
            await session.commit()
    except SourceError as exc:
        error = str(exc)

    await finish_job(session, job, chunks_done=done, error=error)
    await release_lock(session, currency_code)
    await session.commit()
    return job


async def run_all_currencies(
    session_factory: async_sessionmaker[AsyncSession],
    source: FxRateSource,
    currencies: list[str],
    start: dt.date,
    end: dt.date,
    *,
    chunk_days: int,
    max_concurrent: int,
) -> list[FxCollectionJob]:
    """여러 통화를 병행 수집한다 (FR-015c).

    통화마다 별도 세션을 쓴다 — 하나의 세션을 여러 태스크가 공유하면 SQLAlchemy가
    동시 사용을 허용하지 않는다.
    """
    limiter = asyncio.Semaphore(max_concurrent)

    async def _one(code: str) -> FxCollectionJob:
        async with limiter, session_factory() as s:
            return await run_collection(s, source, code, start, end, chunk_days=chunk_days)

    return list(await asyncio.gather(*(_one(c) for c in currencies)))
