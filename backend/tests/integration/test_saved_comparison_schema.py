"""저장한 비교 테이블 (013 T062) — FR-016, data-model 1.

`saved_comparison` — `id` 자동 증가 PK, `name` varchar(100), `asset_class` varchar(16)(비원생
열거형), `condition` text, `saved_at` datetime(UTC), 모두 NOT NULL. 목록 색인 `(saved_at, id)`. 금액
열이 없다. 하향하면 이 테이블만 없어진다.
"""

from __future__ import annotations

import asyncio

import pytest
from alembic import command
from sqlalchemy import inspect, text

from src.config.settings import load_settings
from src.db.engine import create_engine, dispose_engine
from src.db.migrate import _run, reset_schema, upgrade_head


@pytest.fixture
async def engine():  # type: ignore[no-untyped-def]
    eng = create_engine(load_settings())
    await reset_schema()
    yield eng
    await dispose_engine(eng)


async def columns(engine) -> dict[str, tuple[str, str, int | None]]:  # type: ignore[no-untyped-def]
    async with engine.connect() as conn:
        # 원시 SQL — information_schema의 열 정보는 ORM으로 표현할 수 없다(테스트 전용 조회).
        rows = (await conn.execute(text(
            "SELECT column_name, data_type, is_nullable, character_maximum_length "
            "FROM information_schema.columns WHERE table_schema = DATABASE() "
            "AND table_name = 'saved_comparison'"))).all()
    return {r[0]: (r[1], r[2], r[3]) for r in rows}


class Test테이블:
    async def test_열과_형(self, engine) -> None:  # type: ignore[no-untyped-def]
        cols = await columns(engine)
        assert set(cols) == {"id", "name", "asset_class", "condition", "saved_at"}
        assert cols["id"][0] == "bigint"
        assert cols["name"] == ("varchar", "NO", 100)
        assert cols["asset_class"] == ("varchar", "NO", 16)
        assert cols["condition"][:2] == ("text", "NO")
        assert cols["saved_at"][:2] == ("datetime", "NO")

    async def test_기본_키와_목록_색인(self, engine) -> None:  # type: ignore[no-untyped-def]
        async with engine.connect() as conn:
            pk = await conn.run_sync(lambda c: inspect(c).get_pk_constraint("saved_comparison"))
            indexes = await conn.run_sync(lambda c: inspect(c).get_indexes("saved_comparison"))
            auto = (await conn.execute(text(
                # 원시 SQL — 자동 증가 표시(extra)는 ORM 검사기로 읽을 수 없다(테스트 전용 조회).
                "SELECT extra FROM information_schema.columns WHERE table_schema = DATABASE() "
                "AND table_name = 'saved_comparison' AND column_name = 'id'"))).scalar_one()
        assert pk["constrained_columns"] == ["id"]
        assert "auto_increment" in auto
        assert {"name": "ix_saved_comparison_list", "columns": ["saved_at", "id"]} in [
            {"name": i["name"], "columns": i["column_names"]} for i in indexes]

    async def test_처음엔_비어_있다(self, engine) -> None:  # type: ignore[no-untyped-def]
        async with engine.connect() as conn:
            # 원시 SQL — 행 수만 센다(테스트 전용 조회).
            count = (await conn.execute(text("SELECT COUNT(*) FROM saved_comparison"))).scalar_one()
        assert count == 0


class Test하향:
    async def test_하향하면_이_테이블만_없어지고_다시_올린다(self, engine) -> None:  # type: ignore[no-untyped-def]
        await asyncio.to_thread(_run, command.downgrade, "a6d2f9c41b83")
        async with engine.connect() as conn:
            names = await conn.run_sync(lambda c: inspect(c).get_table_names())
        assert "saved_comparison" not in names
        assert {"simulation_history", "history_setting"} <= set(names)
        await upgrade_head()
        async with engine.connect() as conn:
            names = await conn.run_sync(lambda c: inspect(c).get_table_names())
        assert "saved_comparison" in names
