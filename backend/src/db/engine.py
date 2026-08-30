"""SQLAlchemy 비동기 엔진과 커넥션 풀 (T017).

헌법 v4.0.0: 커넥션 풀링을 반드시 적용해야 하며(MUST), 요청마다 새 연결을 여는 구현을
금지한다(MUST NOT). 풀 크기와 타임아웃은 설정값으로 선언한다(MUST).
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from src.config.settings import Settings


def create_engine(settings: Settings) -> AsyncEngine:
    """설정값으로 비동기 엔진을 만든다.

    `pool_pre_ping`은 유휴 중 서버가 끊은 연결을 재사용해 실패하는 것을 막는다.
    30년치 백필처럼 오래 도는 작업에서 실제로 발생한다.
    """
    return create_async_engine(
        settings.database_url,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_timeout=settings.db_pool_timeout_seconds,
        pool_pre_ping=True,
    )


async def dispose_engine(engine: AsyncEngine) -> None:
    """풀의 모든 연결을 반납하고 엔진을 정리한다."""
    await engine.dispose()
