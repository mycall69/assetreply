"""시간축 조합 (T038, T039) — research R3-6, FR-012·FR-013.

통화별로 시간축 막대에 필요한 값을 한 번에 모은다. **새로 저장하는 것이 없다** —
이어받기 지점은 `job.range_start`, 채워진 구간은 `fx_coverage`, 멈춤 판정은
`lock.heartbeat_at` 경과로 001·002가 이미 가진 데이터를 다르게 읽는다.
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config.settings import Settings
from src.db.models import Currency, FxCollectionJob, FxCollectionLock, JobStatus
from src.ingestion.collector import split_into_chunks
from src.repository.collection_lock import DEFAULT_STALE_SECONDS
from src.repository.coverage import get_coverage
from src.repository.raw_response import count_calls_on

Json = dict[str, object]

#: 진행 중 작업의 표시 상태. 세 값으로 나누는 이유는 FR-006a가 "회수를 기다리는 중"을
#: 요구하기 때문이다 — 두 값으로 합치면 사용자가 기다려야 하는지 알 수 없다.
RUNNING = "running"
STALLED = "stalled"
AWAITING_RECLAIM = "awaiting_reclaim"


def job_state(
    heartbeat_at: dt.datetime | None, *, stall_seconds: int, reclaim_seconds: int
) -> str:
    """하트비트 경과로 표시 상태를 정한다 (research R3-3).

    새 타이머나 컬럼을 만들지 않는다. 001이 청크 커밋마다 하트비트를 갱신하므로
    **경과 시간이 곧 "마지막 구간 완료 이후 시간"**이며, 그것이 진전 없음의 정의다.

    하트비트가 없으면(점유가 사라졌는데 작업은 진행 중) 회수 대상으로 본다.
    """
    if heartbeat_at is None:
        return AWAITING_RECLAIM
    elapsed = (dt.datetime.now() - heartbeat_at).total_seconds()
    if elapsed >= reclaim_seconds:
        return AWAITING_RECLAIM
    if elapsed >= stall_seconds:
        return STALLED
    return RUNNING


def chunk_bounds(
    range_start: dt.date, range_end: dt.date, *, chunks_done: int, chunk_days: int
) -> tuple[dt.date, dt.date] | None:
    """지금 받고 있는 구간을 계산한다. 다 끝났으면 `None`.

    **저장하지 않는다.** 작업의 시작일·완료 청크 수·청크 크기로 도출되므로 컬럼을
    더할 이유가 없다 (research R3-6).

    경계를 직접 계산하지 않고 **수집이 쓰는 분할 함수를 그대로 부른다.** 직접 계산하면
    윤년 같은 경계에서 실제 청크와 하루씩 어긋나고, 화면이 엉뚱한 구간을 강조하게 된다.
    """
    chunks = split_into_chunks(range_start, range_end, chunk_days=chunk_days)
    if chunks_done >= len(chunks):
        return None
    return chunks[chunks_done]


async def _active_job(session: AsyncSession, currency_code: str) -> FxCollectionJob | None:
    return (await session.execute(
        select(FxCollectionJob)
        .where(FxCollectionJob.currency_code == currency_code)
        .where(FxCollectionJob.status == JobStatus.RUNNING)
        .order_by(FxCollectionJob.id.desc()))).scalars().first()


async def _heartbeat(session: AsyncSession, currency_code: str) -> dt.datetime | None:
    return (await session.execute(
        select(FxCollectionLock.heartbeat_at)
        .where(FxCollectionLock.currency_code == currency_code)
        .where(FxCollectionLock.scope == "collection"))).scalars().first()


async def _target_from(
    session: AsyncSession, currency_code: str, settings: Settings
) -> dt.date:
    """시간축 왼쪽 끝. 출처가 실제로 제공하기 시작한 날을 우선한다 (헌법 v4.1.0)."""
    found = (await session.execute(
        select(Currency.first_available_date)
        .where(Currency.code == currency_code))).scalars().first()
    return found or settings.probe_start(currency_code)


async def build_timeline(
    session: AsyncSession, currency_code: str, settings: Settings, *,
    busy_with: str | None = None,
) -> Json:
    """한 통화의 시간축 자료를 만든다 (contracts/rest-api 2절).

    `activeJob`은 **진행 중일 때만 포함한다**. 값이 없을 때 키를 넣지 않는 것은 002가
    세운 규약이다 — 정상 상태에 빈 객체를 두면 화면이 존재 여부가 아니라 내용을
    검사해야 한다.

    반대로 `busyWith`는 `null`을 명시한다. "확인했고 없다"와 "확인하지 않았다"가
    구별되어야 화면이 시작 버튼을 막을지 판단할 수 있다 (FR-029).
    """
    today = dt.date.today()
    # 오른쪽 끝이 어제인 이유는 001의 규약 때문이다 — `covered_through`는 확정 수집만
    # 반영하므로 항상 어제 이하다. 오늘을 넣으면 영원히 채워지지 않는 구간이 생긴다.
    target_to = today - dt.timedelta(days=1)
    coverage = await get_coverage(session, currency_code)

    out: Json = {
        "generatedAt": dt.datetime.now().isoformat(),
        "callsToday": await count_calls_on(session, today),
        "currency": currency_code,
        "targetFrom": (await _target_from(session, currency_code, settings)).isoformat(),
        "targetTo": target_to.isoformat(),
        "coveredFrom": coverage.covered_from.isoformat() if coverage else None,
        "coveredThrough": coverage.covered_through.isoformat() if coverage else None,
        "busyWith": busy_with if busy_with != currency_code else None,
    }

    job = await _active_job(session, currency_code)
    if job is not None:
        current = chunk_bounds(job.range_start, job.range_end,
                               chunks_done=job.chunks_done,
                               chunk_days=settings.ecos_chunk_days)
        out["activeJob"] = {
            "jobId": job.id,
            # 이어받기 지점 (FR-011). 작업이 어디서부터 시작했는지가 곧 그 값이다.
            "rangeStart": job.range_start.isoformat(),
            "chunksTotal": job.chunks_total,
            "chunksDone": job.chunks_done,
            "currentChunk": (
                {"from": current[0].isoformat(), "to": current[1].isoformat()}
                if current else None),
            "state": job_state(
                await _heartbeat(session, currency_code),
                stall_seconds=settings.stall_threshold_seconds,
                reclaim_seconds=DEFAULT_STALE_SECONDS),
        }
    return out
