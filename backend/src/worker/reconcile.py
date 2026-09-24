"""미해결 작업 정리 (T023) — research R3-2, FR-005·005a.

프로세스가 비정상 종료하면 작업이 `running`인 채로, 점유가 잡힌 채로 남는다. 그대로
두면 **다음 수집 시작이 영구히 막힌다** — 점유가 있으니 새 작업이 잠금을 못 잡는다.

**기동 시 1회 + 주기 실행** 두 경로로 돈다.

기동 시 정리는 가장 흔한 경우를 즉시 해소한다 — 프로세스가 죽었다 살아난 직후가
그렇다. 그것만으로는 부족한데, 워커 태스크만 예외로 죽고 프로세스는 살아 있는 경우에는
기동 이벤트가 없기 때문이다. 그래서 주기 정리를 함께 둔다.

**조회 시점 지연 판정은 쓰지 않는다.** 아무도 화면을 열지 않으면 영원히 고쳐지지
않는다. 점유가 남아 있는 한 다음 수집이 막히므로, 관찰 여부와 무관하게 회복되어야 한다.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.repository.collection_lock import DEFAULT_STALE_SECONDS, stale_locks
from src.repository.job import finalize_as_partial, get_job

_log = logging.getLogger(__name__)

_REASON = "실행 프로세스가 응답하지 않아 점유를 회수했습니다."


async def reconcile_once(
    session: AsyncSession, *, stale_seconds: int = DEFAULT_STALE_SECONDS
) -> int:
    """미해결 작업을 한 번 정리한다. 정리한 작업 수를 돌려준다.

    커밋은 호출자가 한다 — 주기 루프와 기동 경로가 트랜잭션 경계를 다르게 잡는다.
    """
    locks = await stale_locks(session, older_than_seconds=stale_seconds)
    count = 0
    for lock in locks:
        job = await get_job(session, lock.job_id)
        if job is not None:
            await finalize_as_partial(session, job, reason=_REASON)
            count += 1
        # 작업을 찾지 못해도 점유는 회수한다. 남겨두면 막는 것은 똑같다.
        await session.delete(lock)
    return count


async def reconcile_loop(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    interval_seconds: int,
    stale_seconds: int = DEFAULT_STALE_SECONDS,
) -> None:
    """주기 정리 태스크. `lifespan`이 띄우고 종료 시 취소한다.

    한 번의 실패로 루프가 죽지 않는다. 정리가 멈추면 점유가 쌓여 수집이 막히므로,
    다음 주기에 다시 시도하는 편이 낫다.
    """
    while True:
        try:
            await asyncio.sleep(interval_seconds)
            async with session_factory() as session:
                cleaned = await reconcile_once(session, stale_seconds=stale_seconds)
                await session.commit()
            if cleaned:
                _log.info("미해결 작업 %d건을 정리했습니다.", cleaned)
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 — 정리가 멈추면 수집이 영구히 막힌다
            _log.exception("미해결 작업 정리에 실패했습니다. 다음 주기에 다시 시도합니다.")


async def reconcile_on_startup(
    session_factory: async_sessionmaker[AsyncSession],
) -> int:
    """기동 시 1회 정리. 실패해도 애플리케이션 기동을 막지 않는다.

    **하트비트 나이를 보지 않는다(`stale_seconds=0`).** 방금 기동했으므로 진행 중인
    수집이 있을 수 없고, 남아 있는 `running` 작업은 정의상 전부 고아다. 주기 정리와
    같은 900초 기준을 쓰면 프로세스가 죽은 직후 재기동해도 15분을 기다려야 수집을
    다시 시작할 수 있다 — FR-005가 막으려던 바로 그 상태다.
    """
    with contextlib.suppress(Exception):
        async with session_factory() as session:
            cleaned = await reconcile_once(session, stale_seconds=0)
            await session.commit()
            if cleaned:
                _log.info("기동 시 미해결 작업 %d건을 정리했습니다.", cleaned)
            return cleaned
    _log.warning("기동 시 미해결 작업 정리에 실패했습니다. 주기 정리가 이어서 시도합니다.")
    return 0
