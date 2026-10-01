"""수집 필요 판정과 작업 확보 (T093) — 005 FR-044, FR-047~049.

**표와 차트가 같은 판정을 쓴다.** 한쪽만 수집을 시작하면 같은 구간을 두 번 받거나,
한쪽은 비어 있고 한쪽은 **받은 만큼만 계산한 틀린 값**을 보여준다. 둘 다 숫자가
멀쩡해 보이므로 알아챌 신호가 없다 (FR-049).

판정 근거는 커버리지다. 받으러 갔다가 아무 값도 없었던 구간도 커버리지에는
기록되므로(상장폐지·거래정지), 한 번 시도한 구간을 영원히 다시 받으러 가지 않는다.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Stock
from src.repository.stock import get_coverage, missing_ranges
from src.repository.stock_job import acquire_or_get_running
from src.worker.stock_queue import StockWork, get_stock_queue
from src.worker.stock_runner import CHUNK_DAYS, split_into_chunks


@dataclass(frozen=True, slots=True)
class Collecting:
    """수집 중 응답에 실을 것 (FR-047)."""

    job_id: int
    missing_from: dt.date
    missing_through: dt.date


def collecting_json(stock: Stock, collecting: Collecting) -> dict[str, object]:
    """202 본문. **결과를 함께 싣지 않는다** (FR-049)."""
    return {
        "status": "collecting",
        "market": stock.market,
        "symbol": stock.symbol,
        "jobId": collecting.job_id,
        "missingFrom": collecting.missing_from.isoformat(),
        "missingThrough": collecting.missing_through.isoformat(),
        "progressUrl": f"/api/stocks/progress?jobId={collecting.job_id}",
    }


async def plan_collection(
    session: AsyncSession, stock: Stock, start: dt.date, end: dt.date
) -> Collecting | None:
    """받지 못한 구간이 있으면 작업을 확보한다. 다 받았으면 `None`.

    **이미 진행 중이면 새 작업을 만들지 않고 그 작업 ID를 준다**(FR-048). 중복 수집은
    오류 없이 성공하면서 출처 호출만 두 배로 쓰는데, 출처가 한도를 공개하지 않아 그
    대가를 미리 알 수 없다.
    """
    stock_id = int(stock.id)
    covered = await get_coverage(session, stock_id)
    gaps = missing_ranges(covered, start, end)
    if not gaps:
        return None

    missing_from = min(g[0] for g in gaps)
    missing_through = max(g[1] for g in gaps)
    chunks = sum(len(split_into_chunks(a, b, CHUNK_DAYS)) for a, b in gaps)

    job_id, created = await acquire_or_get_running(
        session, stock_id, missing_from, missing_through, chunks_total=chunks)
    if created:
        # 커밋해야 워커가 다른 세션에서 그 작업을 볼 수 있다.
        await session.commit()
        get_stock_queue().request(StockWork(
            job_id=job_id, stock_id=stock_id, symbol=stock.symbol,
            start=missing_from, end=missing_through))

    return Collecting(job_id, missing_from, missing_through)
