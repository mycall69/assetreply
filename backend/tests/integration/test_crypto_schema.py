"""가상자산 스키마 (T007) — 007 data-model, FR-010, FR-031, 헌법 원칙 V·VI.

마이그레이션 하나로 테이블 11개. 가격은 `DECIMAL(36,14)` — 원값이 소수 14자리로 오고(research R7-3)
주식의 `DECIMAL(20,6)`은 2e-12달러를 0으로 만든다. `(coin_id, day)` 복합 기본 키가 수집의
멱등성이다.
"""
from __future__ import annotations

import asyncio

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncEngine

from src.config.settings import load_settings
from src.db.engine import create_engine, dispose_engine
from src.db.migrate import reset_schema, upgrade_head

TABLES = {"crypto_coin", "crypto_coin_refresh", "crypto_list_lock", "crypto_list_raw_body",
          "crypto_list_raw", "crypto_daily", "crypto_raw_response", "crypto_coverage",
          "crypto_collection_job", "crypto_collection_lock", "crypto_setting"}


@pytest.fixture
async def engine():  # type: ignore[no-untyped-def]
    eng = create_engine(load_settings())
    await reset_schema()
    yield eng
    await dispose_engine(eng)


async def columns(engine: AsyncEngine, table: str) -> dict[str, dict[str, object]]:
    async with engine.connect() as conn:
        rows = (await conn.execute(text(
            "SELECT column_name, data_type, numeric_precision, numeric_scale, is_nullable "
            "FROM information_schema.columns WHERE table_schema = DATABASE() AND table_name = :t"),
            {"t": table})).all()
    return {r[0]: {"type": r[1], "precision": r[2], "scale": r[3], "nullable": r[4] == "YES"}
            for r in rows}


async def test_테이블_11개(engine: AsyncEngine) -> None:
    async with engine.connect() as conn:
        names = set(await conn.run_sync(lambda c: inspect(c).get_table_names()))
    assert TABLES <= names


async def test_가격과_거래량의_정밀도(engine: AsyncEngine) -> None:
    cols = await columns(engine, "crypto_daily")
    for name in ("open", "high", "low", "close"):
        c = cols[name]
        assert (c["type"], c["precision"], c["scale"], c["nullable"]) == (
            "decimal", 36, 14, False), name
    v = cols["volume"]
    assert (v["type"], v["precision"], v["scale"]) == ("decimal", 38, 8)
    assert cols["volume"]["nullable"] is True


async def test_일봉의_기본_키와_코인의_유일_키(engine: AsyncEngine) -> None:
    async with engine.connect() as conn:
        pk = await conn.run_sync(lambda c: inspect(c).get_pk_constraint("crypto_daily"))
        uniques = await conn.run_sync(lambda c: inspect(c).get_indexes("crypto_coin"))
    assert pk["constrained_columns"] == ["coin_id", "day"]
    assert any(ix["unique"] and ix["column_names"] == ["source", "source_id"] for ix in uniques)


async def test_수수료율은_SPREAD이고_행이_없다(engine: AsyncEngine) -> None:
    cols = await columns(engine, "crypto_setting")
    assert (cols["trade_fee_rate"]["type"], cols["trade_fee_rate"]["precision"],
            cols["trade_fee_rate"]["scale"]) == ("decimal", 9, 6)
    async with engine.connect() as conn:
        assert (await conn.execute(text("SELECT COUNT(*) FROM crypto_setting"))).scalar() == 0


async def test_목록_점유에_진행_열이_있다(engine: AsyncEngine) -> None:
    """FR-005b — 진행 스트림이 이 행을 읽는다."""
    cols = await columns(engine, "crypto_list_lock")
    assert {"edition", "pages_done", "coins_seen"} <= set(cols)


async def test_하향_뒤_재상향(engine: AsyncEngine) -> None:
    from alembic import command

    from src.db.migrate import _run

    await asyncio.to_thread(_run, command.downgrade, "4fee5b817ff0")
    async with engine.connect() as conn:
        names = set(await conn.run_sync(lambda c: inspect(c).get_table_names()))
    assert not (TABLES & names)
    await upgrade_head()
    async with engine.connect() as conn:
        names = set(await conn.run_sync(lambda c: inspect(c).get_table_names()))
    assert TABLES <= names
