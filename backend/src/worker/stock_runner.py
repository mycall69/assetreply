"""주식 시세 수집 (T019) — 005 FR-043~046, 헌법 원칙 I.

003이 FX에서 만든 구조를 잇는다 — 구간 분할, 커버리지 기반 재개, 청크마다의 커밋.

**점유는 자산군을 가로질러 공유하지 않는다.** FX 수집 중에 주식 수집을 막을 이유가
없고, 출처가 달라 호출 한도도 따로다 (research R5-7).

**청크마다 커밋한다.** 중단되면 받은 데까지는 남아야 다음 실행이 그 뒤부터 이어받는다.
한 번에 커밋하면 중단 시 전부 잃고, 구간이 길수록 영영 끝나지 않는다 (FR-045).
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Awaitable, Callable
from typing import Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from src.ingestion.yahoo.parse import ChartData
from src.repository.stock import Range, get_coverage, missing_ranges, record_coverage
from src.repository.stock_price import store_chart, store_raw

#: 한 번에 요청하는 날짜 폭. 출처가 한 응답에 수천 행을 담을 수 있지만, 길게 잡으면
#: 중단 시 잃는 구간이 커지고 본문도 커진다.
CHUNK_DAYS = 365 * 2


class StockSource(Protocol):
    """시세 출처. 어댑터를 교체할 수 있도록 Protocol에 의존한다 (헌법 원칙 II·IV)."""

    async def fetch_chart(
        self, symbol: str, date_from: dt.date, date_to: dt.date
    ) -> tuple[ChartData, str, int]: ...

    async def delay_between_chunks(self) -> None: ...


def split_into_chunks(start: dt.date, end: dt.date, days: int) -> list[Range]:
    """구간을 `days`일 단위로 나눈다. 마지막 청크는 짧을 수 있다."""
    chunks: list[Range] = []
    cursor = start
    step = dt.timedelta(days=days - 1)
    while cursor <= end:
        stop = min(cursor + step, end)
        chunks.append((cursor, stop))
        cursor = stop + dt.timedelta(days=1)
    return chunks


async def collect_range(
    session: AsyncSession,
    source: StockSource,
    stock_id: int,
    symbol: str,
    start: dt.date,
    end: dt.date,
    *,
    on_chunk: Callable[[], Awaitable[None]] | None = None,
) -> int:
    """`start`~`end`에서 **아직 받지 않은 구간만** 받아 저장한다 (FR-043, FR-044).

    저장한 일봉 행 수를 돌려준다. 받을 것이 없으면 0이고 출처를 부르지 않는다 —
    이미 받은 구간을 다시 받으면 호출을 낭비하고, 출처가 막혔을 때 이미 가진
    데이터로도 답하지 못하게 된다.

    `on_chunk`는 청크 하나를 저장·커밋한 뒤에 불린다. 진행을 기록하지 않으면 SSE가
    같은 숫자만 반복해 보내고 사용자는 멈춘 것으로 읽는다 (SC-001a).
    """
    covered = await get_coverage(session, stock_id)
    gaps = missing_ranges(covered, start, end)
    if not gaps:
        return 0

    stored = 0
    for gap_start, gap_end in gaps:
        for chunk_start, chunk_end in split_into_chunks(
            gap_start, gap_end, CHUNK_DAYS
        ):
            data, raw, status = await source.fetch_chart(
                symbol, chunk_start, chunk_end)

            await store_raw(
                session, stock_id=stock_id, kind="chart", body=raw,
                status_code=status, requested_from=chunk_start,
                requested_to=chunk_end)
            stored += await store_chart(session, stock_id, data)
            await record_coverage(session, stock_id, chunk_start, chunk_end)

            # 청크마다 커밋한다. 중단되면 받은 데까지는 남아야 재개가 성립한다.
            await session.commit()
            if on_chunk is not None:
                await on_chunk()
            await source.delay_between_chunks()

    return stored
