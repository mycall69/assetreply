"""이력 스키마 (012 T042) — data-model 1, 헌법 DB 운영 규약.

마이그레이션 하나로 테이블 둘. `(asset_class, condition_key)`가 기본 키다 — 같은 조건은 한 행이고,
`db/dialect.upsert`가 기본 키로 충돌을 가른다.
자산군·보관 기간은 비원생 열거(`VARCHAR`)다 — DB를 바꿔도 같은 값이다. 시각은 시간대 없는 UTC다.
조건은 서버가 직렬화한 글(`TEXT`)이다 — JSON 열을 쓰지
않는다(research R12-9).
"""

from __future__ import annotations

import asyncio

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncEngine

from src.config.settings import load_settings
from src.db.engine import create_engine, dispose_engine
from src.db.migrate import reset_schema, upgrade_head

TABLES = {"simulation_history", "history_setting"}


@pytest.fixture
async def engine():  # type: ignore[no-untyped-def]
    eng = create_engine(load_settings())
    await reset_schema()
    yield eng
    await dispose_engine(eng)


async def columns(engine: AsyncEngine, table: str) -> dict[str, dict[str, object]]:
    async with engine.connect() as conn:
        rows = (
            await conn.execute(
                text(
                    "SELECT column_name, data_type, is_nullable, character_maximum_length "
                    "FROM information_schema.columns "
                    "WHERE table_schema = DATABASE() AND table_name = :t"
                ),
                {"t": table},
            )
        ).all()
    return {r[0]: {"type": r[1], "nullable": r[2] == "YES", "length": r[3]} for r in rows}


async def test_테이블_둘(engine: AsyncEngine) -> None:
    async with engine.connect() as conn:
        names = set(await conn.run_sync(lambda c: inspect(c).get_table_names()))
    assert TABLES <= names


async def test_이력의_기본_키와_열(engine: AsyncEngine) -> None:
    cols = await columns(engine, "simulation_history")
    assert set(cols) == {"asset_class", "condition_key", "condition", "last_run_at", "retain_from"}
    assert (cols["asset_class"]["type"], cols["asset_class"]["length"]) == ("varchar", 16)
    assert (cols["condition_key"]["type"], cols["condition_key"]["length"]) == ("varchar", 255)
    assert cols["condition"]["type"] == "text"
    assert (cols["last_run_at"]["type"], cols["retain_from"]["type"]) == ("datetime", "datetime")
    assert not any(c["nullable"] for c in cols.values())
    async with engine.connect() as conn:
        pk = await conn.run_sync(lambda c: inspect(c).get_pk_constraint("simulation_history"))
        indexes = await conn.run_sync(lambda c: inspect(c).get_indexes("simulation_history"))
    assert pk["constrained_columns"] == ["asset_class", "condition_key"]
    assert {"name": "ix_simulation_history_list", "columns": ["asset_class", "last_run_at"]} in [
        {"name": i["name"], "columns": i["column_names"]} for i in indexes
    ]


async def test_보관_기간은_비원생_열거이고_행이_없다(engine: AsyncEngine) -> None:
    cols = await columns(engine, "history_setting")
    assert set(cols) == {"id", "retention", "updated_at"}
    assert (
        cols["retention"]["type"],
        cols["retention"]["length"],
        cols["retention"]["nullable"],
    ) == ("varchar", 16, False)
    async with engine.connect() as conn:
        count = (await conn.execute(text("SELECT COUNT(*) FROM history_setting"))).scalar_one()
    assert count == 0  # 행이 없으면 기본 30일이다


async def test_하향_뒤_재상향(engine: AsyncEngine) -> None:
    from alembic import command

    from src.db.migrate import _run

    await asyncio.to_thread(_run, command.downgrade, "f4c2a8e19d35")
    async with engine.connect() as conn:
        names = set(await conn.run_sync(lambda c: inspect(c).get_table_names()))
    assert not (TABLES & names)
    assert "stock_setting" in names, "앞 기능의 테이블까지 내렸다"
    await upgrade_head()
    async with engine.connect() as conn:
        names = set(await conn.run_sync(lambda c: inspect(c).get_table_names()))
    assert TABLES <= names
