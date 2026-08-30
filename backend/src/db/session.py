"""비동기 세션 팩토리와 의존성 주입 (T018)."""

from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from src.config.settings import Settings, load_settings
from src.db.engine import create_engine

_engine: AsyncEngine | None = None
_factory: async_sessionmaker[AsyncSession] | None = None


def make_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """엔진에 묶인 세션 팩토리를 만든다.

    `expire_on_commit=False`인 이유는 커밋 후에도 반환 객체의 속성을 읽을 수 있어야
    하기 때문이다. 커밋마다 재조회가 발생하면 대량 수집에서 왕복이 폭증한다.
    """
    return async_sessionmaker(engine, expire_on_commit=False)


def init_engine(settings: Settings | None = None) -> AsyncEngine:
    """애플리케이션 수명 동안 공유할 엔진을 1회 생성한다."""
    global _engine, _factory
    if _engine is None:
        _engine = create_engine(settings or load_settings())
        _factory = make_session_factory(_engine)
    return _engine


async def shutdown_engine() -> None:
    global _engine, _factory
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _factory = None


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI 의존성. 요청 단위로 세션을 열고 닫는다."""
    if _factory is None:
        init_engine()
    assert _factory is not None
    async with _factory() as session:
        yield session
