"""부동산 스키마 (T007) — 009 data-model 1~9절, FR-009, FR-012, FR-034, 헌법 원칙 V·VI.

마이그레이션 하나로 테이블 9개. 금액은 원 단위 `DECIMAL(15,0)`, 면적은 `DECIMAL(7,2)`, 비율은
`DECIMAL(9,6)` — `FLOAT`· `DOUBLE`은 없다. 거래의 유니크 키는 (자산 식별자, 날짜)를 **거래 사건**에
맞춘 것이다 — 같은 날 같은 층·면적·금액의 다른 호가 있어 응답 안 순번(`occurrence`)까지
넣는다(research R9-4). 원본에는 **URL 열이 없다** — 인증키가 질의 문자열에 있다(FR-013).
"""
from __future__ import annotations

import asyncio

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncEngine

from src.config.settings import load_settings
from src.db.engine import create_engine, dispose_engine
from src.db.migrate import reset_schema, upgrade_head

TABLES = {"apt_region", "apt_complex", "apt_trade", "apt_raw_response", "apt_trade_coverage",
          "apt_collection_job", "apt_collection_lock", "apt_api_usage", "apt_list_state",
          "apt_setting"}


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


def shape(col: dict[str, object]) -> tuple[object, ...]:
    return (col["type"], col["length"], col["nullable"])


async def pk(engine: AsyncEngine, table: str) -> list[str]:
    async with engine.connect() as conn:
        found = await conn.run_sync(lambda c: inspect(c).get_pk_constraint(table))
    return list(found["constrained_columns"])


async def test_테이블_10개(engine: AsyncEngine) -> None:
    """data-model의 9절 + 작업·점유가 둘 — 테이블은 열이다."""
    async with engine.connect() as conn:
        names = set(await conn.run_sync(lambda c: inspect(c).get_table_names()))
    assert TABLES <= names


async def test_행정구역(engine: AsyncEngine) -> None:
    cols = await columns(engine, "apt_region")
    assert shape(cols["code"]) == ("char", 10, False)
    assert shape(cols["level"]) == ("varchar", 8, False)
    assert shape(cols["parent_code"]) == ("char", 10, True)
    assert shape(cols["lawd_cd"]) == ("char", 5, True)
    assert shape(cols["name"]) == ("varchar", 40, False)
    assert shape(cols["full_name"]) == ("varchar", 80, False)
    assert shape(cols["source"]) == ("varchar", 16, False)
    assert cols["seen_at"]["nullable"] is False and cols["retired_at"]["nullable"] is True
    assert {"ingested_at", "seen_at", "retired_at"} <= set(cols)
    assert await pk(engine, "apt_region") == ["code"]


async def test_단지(engine: AsyncEngine) -> None:
    cols = await columns(engine, "apt_complex")
    assert shape(cols["umd_code"]) == ("char", 10, False)
    assert shape(cols["lawd_cd"]) == ("char", 5, False)
    assert shape(cols["apt_seq"]) == ("varchar", 20, True)
    assert shape(cols["kapt_code"]) == ("varchar", 20, True)
    assert shape(cols["name"]) == ("varchar", 80, False)
    assert shape(cols["jibun"]) == ("varchar", 20, True)
    assert (cols["move_in_year"]["type"], cols["move_in_year"]["nullable"]) == ("smallint", True)
    assert shape(cols["move_in_source"]) == ("varchar", 8, True)
    assert (cols["households"]["type"], cols["households"]["nullable"]) == ("int", True)
    assert cols["details_checked_at"]["nullable"] is True
    assert (cols["merged_into"]["type"], cols["merged_into"]["nullable"]) == ("bigint", True)
    async with engine.connect() as conn:
        uniques = await conn.run_sync(lambda c: inspect(c).get_unique_constraints("apt_complex"))
    assert sorted(tuple(u["column_names"]) for u in uniques) == [("apt_seq",), ("kapt_code",)]


async def test_거래(engine: AsyncEngine) -> None:
    cols = await columns(engine, "apt_trade")
    area, amount = cols["excl_area"], cols["amount"]
    assert (area["type"], area["precision"], area["scale"]) == ("decimal", 7, 2)
    assert (amount["type"], amount["precision"], amount["scale"]) == ("decimal", 15, 0)
    assert area["nullable"] is False and amount["nullable"] is False
    assert shape(cols["lawd_cd"]) == ("char", 5, False)
    assert shape(cols["deal_ym"]) == ("char", 6, False)
    assert (cols["deal_date"]["type"], cols["deal_date"]["nullable"]) == ("date", False)
    assert shape(cols["apt_seq"]) == ("varchar", 20, False)
    assert shape(cols["umd_code"]) == ("char", 10, False)
    assert shape(cols["apt_dong"]) == ("varchar", 20, False)
    assert (cols["floor"]["type"], cols["occurrence"]["type"]) == ("smallint", "smallint")
    assert shape(cols["dealing_type"]) == ("varchar", 8, True)
    assert (cols["cancelled"]["type"], cols["cancelled"]["nullable"]) == ("tinyint", False)
    assert (cols["cancelled_on"]["type"], cols["cancelled_on"]["nullable"]) == ("date", True)
    assert cols["missing_since"]["nullable"] is True
    assert shape(cols["missing_reason"]) == ("varchar", 16, True)
    assert shape(cols["source"]) == ("varchar", 16, False)
    assert {"ingested_at", "updated_at"} <= set(cols)
    async with engine.connect() as conn:
        uniques = await conn.run_sync(lambda c: inspect(c).get_unique_constraints("apt_trade"))
        indexes = await conn.run_sync(lambda c: inspect(c).get_indexes("apt_trade"))
    assert [u["column_names"] for u in uniques] == [
        ["lawd_cd", "deal_date", "apt_seq", "apt_dong", "floor", "excl_area", "amount",
         "occurrence"]]
    assert ["apt_seq", "deal_date"] in [i["column_names"] for i in indexes]


async def test_원본에_URL_열이_없다(engine: AsyncEngine) -> None:
    cols = await columns(engine, "apt_raw_response")
    assert not any("url" in name for name in cols), "인증키가 든 URL을 담을 자리가 있다"
    assert shape(cols["endpoint"]) == ("varchar", 24, False)
    assert shape(cols["request_ref"]) == ("varchar", 40, False)
    assert shape(cols["result_code"]) == ("varchar", 16, True)
    assert cols["body"]["type"] == "longtext"
    assert shape(cols["body_sha256"]) == ("char", 64, False)
    async with engine.connect() as conn:
        indexes = await conn.run_sync(lambda c: inspect(c).get_indexes("apt_raw_response"))
    found = [i["column_names"] for i in indexes]
    assert ["endpoint", "request_ref", "received_at"] in found and ["received_at"] in found


async def test_커버리지와_목록_상태(engine: AsyncEngine) -> None:
    cols = await columns(engine, "apt_trade_coverage")
    assert shape(cols["state"]) == ("varchar", 12, False)
    assert (cols["trade_rows"]["type"], cols["checked_on"]["type"]) == ("int", "date")
    assert cols["checked_on"]["nullable"] is False
    assert await pk(engine, "apt_trade_coverage") == ["lawd_cd", "deal_ym"]
    state = await columns(engine, "apt_list_state")
    assert shape(state["scope"]) == ("varchar", 20, False)
    assert state["refreshed_at"]["nullable"] is True
    assert shape(state["first_trade_ym"]) == ("char", 6, True)
    assert await pk(engine, "apt_list_state") == ["scope"]


async def test_작업_점유_하루_호출_수(engine: AsyncEngine) -> None:
    job = await columns(engine, "apt_collection_job")
    assert shape(job["kind"]) == ("varchar", 16, False)
    assert shape(job["target"]) == ("varchar", 20, False)
    for name in ("total", "done"):
        assert job[name]["nullable"] is False, name
    assert job["last_error"]["nullable"] is True
    assert await pk(engine, "apt_collection_lock") == ["kind", "target"]
    usage = await columns(engine, "apt_api_usage")
    assert (usage["calls"]["type"], usage["calls"]["nullable"]) == ("int", False)
    assert await pk(engine, "apt_api_usage") == ["api", "kst_date"]


async def test_설정은_SPREAD이고_행이_없다(engine: AsyncEngine) -> None:
    cols = await columns(engine, "apt_setting")
    c = cols["holding_tax_base_ratio"]
    assert (c["type"], c["precision"], c["scale"], c["nullable"]) == ("decimal", 9, 6, False)
    async with engine.connect() as conn:
        assert (await conn.execute(text("SELECT COUNT(*) FROM apt_setting"))).scalar() == 0


async def test_FLOAT_DOUBLE이_없다(engine: AsyncEngine) -> None:
    async with engine.connect() as conn:
        rows = (await conn.execute(text(
            "SELECT table_name, column_name FROM information_schema.columns "
            "WHERE table_schema = DATABASE() AND table_name LIKE 'apt\\_%' "
            "AND data_type IN ('float', 'double')"))).all()
    assert rows == []


async def test_하향_뒤_재상향(engine: AsyncEngine) -> None:
    from alembic import command

    from src.db.migrate import _run

    await asyncio.to_thread(_run, command.downgrade, "c4d8e2f91b07")
    async with engine.connect() as conn:
        names = set(await conn.run_sync(lambda c: inspect(c).get_table_names()))
    assert not (TABLES & names)
    assert "deposit_rate" in names, "앞 기능의 테이블까지 내렸다"
    await upgrade_head()
    async with engine.connect() as conn:
        names = set(await conn.run_sync(lambda c: inspect(c).get_table_names()))
    assert TABLES <= names
