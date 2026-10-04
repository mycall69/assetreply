"""가상자산 일봉 수집 (T031) — 007 FR-010~FR-012, FR-022, research R7-3·R7-11.

005의 주식 수집 구조를 잇는다 — 구간 분할, 커버리지 기반 재개, **청크마다 커밋**. 중단되면 받은
데까지는 남아야 다음 실행이 그 뒤부터 이어받는다.

**가격을 읽지 못한 청크는 아무것도 저장하지 않는다**(analyze M2). 응답 해석(`parse_daily`)이 그 청크
전체를 형식 오류로 내므로 일봉도 커버리지도 그 청크만큼 늘지 않는다 — 그 행만 버리면 그날이 출처
결측으로 위장된다.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Awaitable, Callable
from typing import Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from src.ingestion.investing.client import DailyFetch
from src.observability.logging_config import collection_logger
from src.repository import crypto_daily
from src.repository.stock import missing_ranges
from src.worker.stock_runner import split_into_chunks


class CryptoSource(Protocol):
    """가상자산 시세 출처. 어댑터를 교체할 수 있도록 Protocol에 의존한다(헌법 원칙 II·IV)."""

    async def fetch_daily(
        self, source_id: str, start: dt.date, end: dt.date, *, last_day: dt.date
    ) -> DailyFetch: ...


def utc_now() -> dt.datetime:
    """저장용 현재 시각 — UTC, 시간대 없는 값(헌법 시계열 불변식)."""
    return dt.datetime.now(dt.UTC).replace(tzinfo=None)


async def collect_range(
    session: AsyncSession,
    source: CryptoSource,
    *,
    coin_id: int,
    source_id: str,
    start: dt.date,
    end: dt.date,
    chunk_days: int,
    on_chunk: Callable[[], Awaitable[None]] | None = None,
) -> int:
    """`start`~`end`에서 **아직 받지 않은 구간만** 받아 저장한다. 저장한 일봉 행 수를 돌려준다.

    `end`보다 뒤의 행은 저장하지 않는다 — `end`는 계산 끝(UTC 어제) 이하이고, 출처는 마감 전인
    오늘의 일봉도 준다(FR-022).
    """
    gaps = missing_ranges(await crypto_daily.get_coverage(session, coin_id), start, end)
    stored = 0
    for gap_start, gap_end in gaps:
        for chunk_start, chunk_end in split_into_chunks(gap_start, gap_end, chunk_days):
            fetched = await source.fetch_daily(source_id, chunk_start, chunk_end, last_day=end)
            # 원본을 먼저 남긴다 — 정규화와 따로, 본문 그대로(헌법 원칙 V)
            await crypto_daily.store_raw(
                session, coin_id, requested_from=fetched.requested_from,
                requested_to=fetched.requested_to, status_code=fetched.status, body=fetched.raw,
                received_at=utc_now())
            rows = await crypto_daily.store_bars(session, coin_id, fetched.bars)
            await crypto_daily.record_coverage(session, coin_id, chunk_start, chunk_end)
            # 청크마다 커밋한다. 중단되면 받은 데까지는 남아야 재개가 성립한다.
            await session.commit()
            stored += rows
            collection_logger().info("crypto_collection_chunk", extra={
                "event": "crypto_collection_chunk", "coin": source_id,
                "from": chunk_start.isoformat(), "to": chunk_end.isoformat(), "rows": rows})
            if on_chunk is not None:
                await on_chunk()
    return stored
