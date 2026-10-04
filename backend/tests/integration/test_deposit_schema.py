"""예금 스키마 (T006) — 008 data-model, FR-009, FR-029, FR-030, 헌법 원칙 V·VI.

마이그레이션 하나로 테이블 6개. 금리는 연 % 그대로 `DECIMAL(7,4)`, 세율은 비율 `DECIMAL(9,6)`.
`(institution, month)` 기본 키가 수집의 멱등성이다. 원본에는 **URL 열이 없다** — 인증키가 URL
경로에 있다(FR-014). 항목 목록 원본은 통계표 하나가 여러 투자처를 덮으므로 투자처를 비워 둔다
(analyze I2).
"""
from __future__ import annotations

import asyncio

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncEngine

from src.config.settings import load_settings
from src.db.engine import create_engine, dispose_engine
from src.db.migrate import reset_schema, upgrade_head

TABLES = {"deposit_rate", "deposit_raw_response", "deposit_coverage",
          "deposit_collection_job", "deposit_collection_lock", "deposit_setting"}


@pytest.fixture
async def engine():  # type: ignore[no-untyped-def]
    eng = create_engine(load_settings())
    await reset_schema()
    yield eng
    await dispose_engine(eng)


async def columns(engine: AsyncEngine, table: str) -> dict[str, dict[str, object]]:
    async with engine.connect() as conn:
        rows = (await conn.execute(text(
            "SELECT column_name, data_type, numeric_precision, numeric_scale, is_nullable, "
            "character_maximum_length "
            "FROM information_schema.columns WHERE table_schema = DATABASE() AND table_name = :t"),
            {"t": table})).all()
    return {r[0]: {"type": r[1], "precision": r[2], "scale": r[3], "nullable": r[4] == "YES",
                   "length": r[5]} for r in rows}


async def test_테이블_6개(engine: AsyncEngine) -> None:
    async with engine.connect() as conn:
        names = set(await conn.run_sync(lambda c: inspect(c).get_table_names()))
    assert TABLES <= names


async def test_금리는_연_퍼센트이고_기본_키가_투자처와_달이다(engine: AsyncEngine) -> None:
    cols = await columns(engine, "deposit_rate")
    rate = cols["rate"]
    assert (rate["type"], rate["precision"], rate["scale"], rate["nullable"]) == (
        "decimal", 7, 4, False)
    assert (cols["institution"]["type"], cols["institution"]["length"]) == ("varchar", 24)
    assert cols["month"]["type"] == "date"
    assert {"source", "ingested_at"} <= set(cols)
    async with engine.connect() as conn:
        pk = await conn.run_sync(lambda c: inspect(c).get_pk_constraint("deposit_rate"))
    assert pk["constrained_columns"] == ["institution", "month"]


async def test_원본에_URL_열이_없고_항목_목록은_투자처가_빈다(engine: AsyncEngine) -> None:
    cols = await columns(engine, "deposit_raw_response")
    assert not any("url" in name for name in cols), "인증키가 든 URL을 담을 자리가 있다"
    assert cols["institution"]["nullable"] is True
    assert (cols["source_ref"]["length"], cols["source_ref"]["nullable"]) == (32, False)
    assert cols["endpoint"]["nullable"] is False
    # utf8mb4에서 Text(16_777_215)는 MEDIUMTEXT의 바이트 한도를 넘어 LONGTEXT가 된다.
    # 005~007의 원본 본문 열도 모두 longtext다(D2 사용자 승인 2026-10-04).
    assert cols["body"]["type"] == "longtext"
    assert cols["result_code"]["nullable"] is True


async def test_커버리지의_세_날짜는_모두_필수다(engine: AsyncEngine) -> None:
    cols = await columns(engine, "deposit_coverage")
    for name in ("first_month", "latest_month", "checked_on"):
        assert (cols[name]["type"], cols[name]["nullable"]) == ("date", False), name
    async with engine.connect() as conn:
        pk = await conn.run_sync(lambda c: inspect(c).get_pk_constraint("deposit_coverage"))
    assert pk["constrained_columns"] == ["institution"]


async def test_작업_구간은_필수고_점유는_투자처마다_하나다(engine: AsyncEngine) -> None:
    """작업 구간 = 그 실행에 필요한 구간 — 요청 때 늘 안다(analyze I1·U2)."""
    job = await columns(engine, "deposit_collection_job")
    for name in ("range_start", "range_end", "months_total", "months_done"):
        assert job[name]["nullable"] is False, name
    async with engine.connect() as conn:
        pk = await conn.run_sync(lambda c: inspect(c).get_pk_constraint("deposit_collection_lock"))
    assert pk["constrained_columns"] == ["institution"]


async def test_세율은_SPREAD이고_행이_없다(engine: AsyncEngine) -> None:
    cols = await columns(engine, "deposit_setting")
    c = cols["interest_tax_rate"]
    assert (c["type"], c["precision"], c["scale"], c["nullable"]) == ("decimal", 9, 6, False)
    async with engine.connect() as conn:
        assert (await conn.execute(text("SELECT COUNT(*) FROM deposit_setting"))).scalar() == 0


async def test_하향_뒤_재상향(engine: AsyncEngine) -> None:
    from alembic import command

    from src.db.migrate import _run

    await asyncio.to_thread(_run, command.downgrade, "b7e3c9d14a26")
    async with engine.connect() as conn:
        names = set(await conn.run_sync(lambda c: inspect(c).get_table_names()))
    assert not (TABLES & names)
    assert "crypto_daily" in names, "앞 기능의 테이블까지 내렸다"
    await upgrade_head()
    async with engine.connect() as conn:
        names = set(await conn.run_sync(lambda c: inspect(c).get_table_names()))
    assert TABLES <= names
