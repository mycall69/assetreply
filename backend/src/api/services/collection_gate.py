"""동기 대기 / 백그라운드 위임 분기 (T051).

FR-035: 필요 구간이 임계값 이하이면 수집 완료까지 대기한 뒤 결과를 제시한다.
FR-035a: 임계값을 초과하면 즉시 진행 상태를 제시하고 완료 후 결과를 갱신한다.
FR-035b: 임계값은 설정값이며 기본 30일이다.

날짜 조회와 차트 요청이 이 모듈을 공유한다 (FR-032a).
"""

from __future__ import annotations

import datetime as dt
from enum import StrEnum

from sqlalchemy.ext.asyncio import AsyncSession


class CollectionDecision(StrEnum):
    """수집이 필요한지, 필요하다면 어느 경로로 갈지."""

    NONE = "none"
    WAIT = "wait"
    BACKGROUND = "background"


def decide_collection(*, missing_days: int, threshold_days: int) -> CollectionDecision:
    """부족한 일수와 임계값으로 경로를 정한다.

    30년치 백필은 수 분 이상 걸리므로 대기시키면 조회가 사실상 멈춘다. 반대로 며칠치
    증분까지 백그라운드로 넘기면 평소 조회가 두 단계가 된다.
    """
    if missing_days <= 0:
        return CollectionDecision.NONE
    return (CollectionDecision.WAIT if missing_days <= threshold_days
            else CollectionDecision.BACKGROUND)


async def ensure_background_job(
    session: AsyncSession, currency_code: str, end: dt.date, *, chunk_days: int
) -> int:
    """백그라운드 수집 작업을 확보하고 작업 ID를 돌려준다 (T099).

    이미 진행 중이면 새 작업을 만들지 않고 그 작업 ID를 준다 (FR-015b). 반환된 ID로
    `progressUrl`을 구성하므로, 여기서 작업을 만들지 않으면 클라이언트가 구독할 대상이
    없어진다.
    """
    from src.config.settings import load_settings
    from src.ingestion.collector import next_start_date, split_into_chunks
    from src.repository.collection_lock import acquire_lock
    from src.repository.job import create_job

    start = await next_start_date(
        session, currency_code, default=load_settings().probe_start(currency_code))
    chunks = split_into_chunks(start, end, chunk_days=chunk_days)
    job = await create_job(session, currency_code, start, end, chunks_total=len(chunks))
    existing = await acquire_lock(session, currency_code, job.id)
    if existing is not None:
        await session.rollback()
        return existing
    await session.commit()
    return job.id
