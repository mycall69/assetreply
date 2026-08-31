"""Alembic 마이그레이션 테스트 (T014).

헌법 v4.0.0: 스키마 변경은 ORM 마이그레이션 도구로만 관리하며 수동 DDL을 금지한다.
"""
from decimal import Decimal

import pytest
from sqlalchemy import inspect, select, text
from sqlalchemy.ext.asyncio import AsyncEngine

from src.config.settings import load_settings
from src.db.engine import create_engine, dispose_engine
from src.db.migrate import reset_schema, upgrade_head
from src.db.models import Base, Currency, FxSpread


@pytest.fixture
async def engine():
    eng = create_engine(load_settings())
    await reset_schema()
    yield eng
    await dispose_engine(eng)


async def test_모든_테이블이_생성된다(engine: AsyncEngine) -> None:
    async with engine.connect() as conn:
        names = await conn.run_sync(lambda c: inspect(c).get_table_names())
    for t in Base.metadata.tables:
        assert t in names, f"{t} 테이블이 없다"
    assert "alembic_version" in names


async def test_ORM_메타데이터와_실제_스키마가_일치한다(engine: AsyncEngine) -> None:
    """autogenerate가 놓친 컬럼이 없는지 확인한다 (research R9의 주의사항)."""
    async with engine.connect() as conn:
        for table in Base.metadata.tables.values():
            actual = await conn.run_sync(
                lambda c, t=table.name: {col["name"] for col in inspect(c).get_columns(t)})
            expected = {c.name for c in table.columns}
            assert expected == actual, f"{table.name} 컬럼 불일치: {expected ^ actual}"


async def test_재실행해도_멱등하다(engine: AsyncEngine) -> None:
    await upgrade_head()
    async with engine.connect() as conn:
        n = (await conn.execute(text("SELECT COUNT(*) FROM alembic_version"))).scalar()
    assert n == 1


async def test_금액_컬럼에_부동소수점이_없다(engine: AsyncEngine) -> None:
    """헌법 원칙 VI를 실제 스키마에서 확인한다."""
    async with engine.connect() as conn:
        rows = (await conn.execute(text(
            "SELECT table_name, column_name FROM information_schema.columns "
            "WHERE table_schema = DATABASE() AND data_type IN ('float', 'double')"
        ))).all()
    assert rows == [], f"부동소수점 컬럼: {rows}"


async def test_통화_3종이_시드된다(engine: AsyncEngine) -> None:
    from src.db.session import make_session_factory
    async with make_session_factory(engine)() as s:
        rows = (await s.execute(select(Currency))).scalars().all()
    assert {r.code for r in rows} == {"USD", "JPY", "EUR"}


async def test_JPY는_100엔_단위로_시드된다(engine: AsyncEngine) -> None:
    """FR-007: JPY는 100엔당 원화로 고시된다."""
    from src.db.session import make_session_factory
    async with make_session_factory(engine)() as s:
        jpy = (await s.execute(select(Currency).where(Currency.code == "JPY"))).scalar_one()
    assert jpy.quote_unit == 100


async def test_스프레드_기본값이_시드된다(engine: AsyncEngine) -> None:
    """FR-024: 설정하지 않은 통화에 기본 스프레드를 적용한다."""
    from src.db.session import make_session_factory
    async with make_session_factory(engine)() as s:
        rows = {r.currency_code: r for r in (await s.execute(select(FxSpread))).scalars()}
    assert rows["USD"].cash_buy == Decimal("0.001800")
    assert rows["USD"].remit_send == Decimal("0.000500")
    assert rows["JPY"].cash_buy == Decimal("0.002000")
    assert isinstance(rows["EUR"].remit_receive, Decimal)


async def test_기존_행이_확정으로_채워진다(engine: AsyncEngine) -> None:
    """T004 — 마이그레이션 이후 과거 데이터가 잠정으로 오인되면 안 된다."""
    async with engine.connect() as conn:
        col = (await conn.execute(text(
            "SELECT COLUMN_DEFAULT, IS_NULLABLE FROM information_schema.columns "
            "WHERE table_schema = DATABASE() AND table_name = 'fx_rate' "
            "AND column_name = 'is_provisional'"))).first()
    assert col is not None, "is_provisional 컬럼이 없다"
    default, nullable = col
    assert nullable == "NO", "is_provisional은 NOT NULL이어야 한다"
    assert str(default) in ("0", "b'0'", "FALSE", "false"), f"기본값이 {default!r}"


async def test_잠금_테이블_기본키에_범위가_포함된다(engine: AsyncEngine) -> None:
    """T004 — FR-036a: 수집과 새로고침 잠금이 공존하려면 범위가 키에 있어야 한다."""
    async with engine.connect() as conn:
        cols = [r[0] for r in (await conn.execute(text(
            "SELECT COLUMN_NAME FROM information_schema.key_column_usage "
            "WHERE table_schema = DATABASE() AND table_name = 'fx_collection_lock' "
            "AND constraint_name = 'PRIMARY'"))).all()]
    assert set(cols) == {"scope", "currency_code"}, f"기본 키가 {cols}"
