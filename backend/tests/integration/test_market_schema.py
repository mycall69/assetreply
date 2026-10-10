"""대시보드 지표 스키마 (014 T009) — FR-017, SC-006, data-model 1, 헌법 원칙 V·VI.

마이그레이션 하나로 테이블 넷이다. 종가는 `DECIMAL(20,6)`(주식과 같은 형 — 음수 가능),
`(indicator_id, trade_date)` 복합 기본
키가 수집의 멱등성이다. 원본은 정규화와 따로, 개정은 같은 것을 한 번만 남긴다.
"""

from __future__ import annotations

import pytest
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncEngine

from src.config.settings import load_settings
from src.db.engine import create_engine, dispose_engine
from src.db.migrate import _alembic_config, reset_schema

TABLES = {
    "market_indicator_daily",
    "market_indicator_raw",
    "market_indicator_coverage",
    "market_close_revision",
}


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
                    "SELECT column_name, data_type, numeric_precision, numeric_scale, is_nullable, "
                    "character_maximum_length FROM information_schema.columns "
                    "WHERE table_schema = DATABASE() AND table_name = :t"
                ),
                {"t": table},
            )
        ).all()
    return {
        r[0]: {
            "type": r[1],
            "precision": r[2],
            "scale": r[3],
            "nullable": r[4] == "YES",
            "length": r[5],
        }
        for r in rows
    }


def test_리비전은_저장한_비교_뒤다() -> None:
    script = ScriptDirectory.from_config(_alembic_config())
    # 014 승인 2026-10-10 — 반복 2026-10-10b에 시가 리비전이 그 뒤에 붙었다(머리가 아니다)
    dashboard = script.get_revision("c8d4f1a2e9b7")
    assert dashboard is not None
    assert dashboard.down_revision == "b3e7d5a1c924"
    assert "대시보드" in (dashboard.doc or "")


def test_시가_리비전은_대시보드_뒤다() -> None:
    """반복 2026-10-10b(T097) — 시가·고가·저가 열은 리비전 하나다."""
    # 014 승인 2026-10-10(반복 2026-10-10f T161) — 첫 거래일 리비전(a6c2e8f41b93)이 그 뒤에
    # 붙었다 — 시가 리비전은 머리가 아니다. 머리는 `test_stock_first_trade`가 본다(FR-033)
    script = ScriptDirectory.from_config(_alembic_config())
    ohlc = script.get_revision("d5e1a7c3b2f8")
    assert ohlc is not None
    assert ohlc.down_revision == "c8d4f1a2e9b7"
    assert "시가" in (ohlc.doc or "")


async def test_테이블_넷(engine: AsyncEngine) -> None:
    async with engine.connect() as conn:
        names = set(await conn.run_sync(lambda c: inspect(c).get_table_names()))
    assert names >= TABLES


async def test_일별_종가(engine: AsyncEngine) -> None:
    cols = await columns(engine, "market_indicator_daily")
    # 014 승인 2026-10-10 — 반복 2026-10-10b의 시가·고가·저가 열 셋(T097)
    assert set(cols) == {
        "indicator_id",
        "trade_date",
        "close",
        "open_price",
        "high_price",
        "low_price",
        "source",
        "ingested_at",
    }
    for name in ("open_price", "high_price", "low_price"):
        o = cols[name]
        assert (o["type"], o["precision"], o["scale"], o["nullable"]) == ("decimal", 20, 6, True)
    assert (cols["indicator_id"]["type"], cols["indicator_id"]["length"]) == ("varchar", 32)
    assert cols["trade_date"]["type"] == "date"
    c = cols["close"]
    assert (c["type"], c["precision"], c["scale"], c["nullable"]) == ("decimal", 20, 6, False)
    assert (cols["source"]["length"], cols["source"]["nullable"]) == (64, False)
    async with engine.connect() as conn:
        pk = await conn.run_sync(lambda c: inspect(c).get_pk_constraint("market_indicator_daily"))
        defaults = (
            await conn.execute(
                text(
                    "SELECT column_default FROM information_schema.columns "
                    "WHERE table_schema = DATABASE() AND table_name = 'market_indicator_daily' "
                    "AND column_name = 'ingested_at'"
                )
            )
        ).scalar()
    assert pk["constrained_columns"] == ["indicator_id", "trade_date"]
    assert defaults is not None


async def test_원본(engine: AsyncEngine) -> None:
    cols = await columns(engine, "market_indicator_raw")
    # `Text(16_777_215)`는 utf8mb4에서 LONGTEXT다 — 005·007 원본 표와 같다(014 T009 실측으로 고침).
    assert cols["body"]["type"] == "longtext"
    assert {
        "id",
        "indicator_id",
        "requested_from",
        "requested_to",
        "status_code",
        "received_at",
    } <= set(cols)
    async with engine.connect() as conn:
        indexes = await conn.run_sync(lambda c: inspect(c).get_indexes("market_indicator_raw"))
    assert any(ix["column_names"] == ["indicator_id", "received_at"] for ix in indexes)


async def test_커버리지(engine: AsyncEngine) -> None:
    cols = await columns(engine, "market_indicator_coverage")
    for name in (
        "first_day",
        "covered_from",
        "covered_through",
        "last_success_at",
        "last_failure_at",
        "last_failure_kind",
        "last_failure_message",
    ):
        assert cols[name]["nullable"] is True, name
    assert cols["last_failure_kind"]["length"] == 32
    assert cols["last_failure_message"]["length"] == 500
    async with engine.connect() as conn:
        pk = await conn.run_sync(
            lambda c: inspect(c).get_pk_constraint("market_indicator_coverage")
        )
    assert pk["constrained_columns"] == ["indicator_id"]


async def test_개정은_같은_것을_한_번만(engine: AsyncEngine) -> None:
    cols = await columns(engine, "market_close_revision")
    for name in ("stored_close", "source_close"):
        assert (cols[name]["type"], cols[name]["precision"], cols[name]["scale"]) == (
            "decimal",
            20,
            6,
        )
    async with engine.connect() as conn:
        indexes = await conn.run_sync(lambda c: inspect(c).get_indexes("market_close_revision"))
        uniques = await conn.run_sync(
            lambda c: inspect(c).get_unique_constraints("market_close_revision")
        )
    keyed = [ix["column_names"] for ix in indexes if ix["unique"]] + [
        u["column_names"] for u in uniques
    ]
    assert ["indicator_id", "trade_date", "source_close"] in keyed
