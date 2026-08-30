"""커넥션 풀 테스트 (T013).

헌법 v4.0.0: 커넥션 풀링을 반드시 적용해야 하며(MUST), 요청마다 새 연결을 여는 구현을
금지한다(MUST NOT). 풀 크기와 타임아웃은 설정값으로 선언한다(MUST).
"""
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.pool import AsyncAdaptedQueuePool

from src.config.settings import load_settings
from src.db.engine import create_engine, dispose_engine


@pytest.fixture
async def engine():
    eng = create_engine(load_settings())
    yield eng
    await dispose_engine(eng)


def test_엔진이_큐_풀을_사용한다() -> None:
    """NullPool이면 매 요청 새 연결이 열려 헌법 위반이다."""
    eng = create_engine(load_settings())
    assert isinstance(eng.pool, AsyncAdaptedQueuePool)


def test_풀_설정이_설정값을_반영한다(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DB_POOL_SIZE", "7")
    eng = create_engine(load_settings())
    assert eng.pool.size() == 7


async def test_실제_연결이_된다(engine: AsyncEngine) -> None:
    async with engine.connect() as conn:
        assert (await conn.execute(text("SELECT 1"))).scalar() == 1


async def test_순차_요청이_연결을_재사용한다(engine: AsyncEngine) -> None:
    """요청마다 새 연결을 만들면 CONNECTION_ID가 매번 달라진다."""
    ids = []
    for _ in range(5):
        async with engine.connect() as conn:
            ids.append((await conn.execute(text("SELECT CONNECTION_ID()"))).scalar())
    assert len(set(ids)) == 1, f"연결이 재사용되지 않았다: {ids}"


async def test_반납된_연결이_풀에_남는다(engine: AsyncEngine) -> None:
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    assert engine.pool.checkedin() >= 1
