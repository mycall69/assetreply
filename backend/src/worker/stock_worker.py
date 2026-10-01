"""주식 수집 실행 태스크 (T093) — 005 FR-045, FR-047, FR-048.

003이 FX에서 얻은 교훈을 그대로 적용한다 — **엔진을 만들어 두고 그것을 호출하는
주체를 만들지 않으면 작업이 "진행 중"으로 박힌 채 멈춘다.** 화면에는 진행 표시가
돌고 있는데 실제로는 아무 일도 일어나지 않으며, 그 사실이 어디에도 드러나지 않는다.

**청크마다 진행을 기록한다.** 기록하지 않으면 SSE가 같은 숫자만 반복해 보내고,
사용자는 멈춘 것으로 읽어 새로고침한다 (SC-001a).
"""

from __future__ import annotations

import asyncio
import logging

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.db.models import JobStatus
from src.repository.stock_job import advance_chunk, finish_job
from src.worker.stock_queue import StockQueue, StockWork
from src.worker.stock_runner import StockSource, collect_range

_log = logging.getLogger(__name__)


async def run_stock_job(
    session_factory: async_sessionmaker[AsyncSession],
    source: StockSource,
    work: StockWork,
) -> JobStatus:
    """일감 하나를 끝까지 돌리고 작업을 마감한다.

    **실패해도 작업을 반드시 마감한다.** 마감하지 않으면 점유가 남아 그 종목은 다시
    수집할 수 없게 되고, 사용자에게는 "이미 진행 중"이라는 말만 돌아온다.
    """
    async with session_factory() as session:
        async def on_chunk() -> None:
            await advance_chunk(session, work.job_id)
            await session.commit()

        try:
            await collect_range(
                session, source, work.stock_id, work.symbol,
                work.start, work.end, on_chunk=on_chunk)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            _log.exception("주식 수집 실패 stock_id=%s", work.stock_id)
            # 사유를 남긴다. 조용히 끝나면 왜 멈췄는지 알 수 없고 다음 실행이 같은
            # 곳에서 또 멈춘다.
            await finish_job(session, work.job_id, JobStatus.FAILED, error=str(exc))
            await session.commit()
            return JobStatus.FAILED

        await finish_job(session, work.job_id, JobStatus.SUCCEEDED)
        await session.commit()
        return JobStatus.SUCCEEDED


async def stock_worker_loop(
    session_factory: async_sessionmaker[AsyncSession],
    source: StockSource,
    queue: StockQueue,
) -> None:
    """큐에서 일감을 꺼내 돌린다. 앱 수명과 함께 산다.

    **한 건이 실패해도 루프를 끝내지 않는다.** 끝내면 그 뒤의 모든 수집이 조용히
    멈추고, 화면에는 진행 표시만 남는다.
    """
    while True:
        work = await queue.pop()
        try:
            await run_stock_job(session_factory, source, work)
        except asyncio.CancelledError:
            raise
        except Exception:  # pragma: no cover — run_stock_job이 이미 삼킨다
            _log.exception("주식 수집 루프 오류 stock_id=%s", work.stock_id)
        finally:
            queue.done(work.stock_id)
