"""방언 격리 upsert 테스트 (T015).

헌법 v4.0.0: DB 종속 문법(upsert 구문)은 방언 추상화 뒤에 격리해야 한다 (research R12).
FR-003: 동일 구간을 여러 번 수집해도 중복 레코드를 만들지 않는다.
"""
import datetime as dt
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from src.config.settings import load_settings
from src.db.dialect import upsert
from src.db.engine import create_engine, dispose_engine
from src.db.migrate import reset_schema
from src.db.models import FxRate
from src.db.session import make_session_factory


@pytest.fixture
async def session_factory():
    eng = create_engine(load_settings())
    await reset_schema()
    yield make_session_factory(eng)
    await dispose_engine(eng)


def _row(rate: str) -> dict[str, object]:
    return {
        "currency_code": "USD",
        "quote_date": dt.date(2005, 3, 15),
        "base_rate": Decimal(rate),
        "quote_unit": 1,
        "source": "TEST",
    }


async def test_최초_삽입된다(session_factory) -> None:
    async with session_factory() as s:
        await upsert(s, FxRate, [_row("1012.300000")])
        await s.commit()
        assert (await s.execute(select(func.count()).select_from(FxRate))).scalar() == 1


async def test_같은_키_재삽입이_중복을_만들지_않는다(session_factory) -> None:
    """FR-003: 재수집해도 중복 레코드가 생기지 않는다."""
    async with session_factory() as s:
        await upsert(s, FxRate, [_row("1012.300000")])
        await upsert(s, FxRate, [_row("1012.300000")])
        await s.commit()
        assert (await s.execute(select(func.count()).select_from(FxRate))).scalar() == 1


async def test_값이_다르면_갱신된다(session_factory) -> None:
    """FR-003a: 출처가 정정하면 최신 값으로 갱신한다."""
    async with session_factory() as s:
        await upsert(s, FxRate, [_row("1012.300000")])
        await s.commit()
        await upsert(s, FxRate, [_row("1099.990000")])
        await s.commit()
        row = (await s.execute(select(FxRate))).scalar_one()
    assert row.base_rate == Decimal("1099.990000")


async def test_갱신되어도_최초_수집시각은_유지된다(session_factory) -> None:
    """FR-003a: ingested_at은 최초 값을 유지하고 updated_at만 바뀐다."""
    async with session_factory() as s:
        await upsert(s, FxRate, [_row("1012.300000")])
        await s.commit()
        first = (await s.execute(select(FxRate))).scalar_one().ingested_at
        await upsert(s, FxRate, [_row("1099.990000")])
        await s.commit()
        await s.refresh((await s.execute(select(FxRate))).scalar_one())
        row = (await s.execute(select(FxRate))).scalar_one()
    assert row.ingested_at == first


async def test_여러_행을_한번에_upsert한다(session_factory) -> None:
    rows = [
        {**_row("1000.000000"), "quote_date": dt.date(2005, 3, d)} for d in (15, 16, 17)
    ]
    async with session_factory() as s:
        await upsert(s, FxRate, rows)
        await upsert(s, FxRate, rows)
        await s.commit()
        assert (await s.execute(select(func.count()).select_from(FxRate))).scalar() == 3


def test_방언_API가_dialect_모듈_밖에_없다() -> None:
    """헌법 v4.0.0: 방언 구문은 db/dialect.py에만 존재해야 한다."""
    import pathlib
    root = pathlib.Path(__file__).resolve().parents[2] / "src"
    offenders = [
        str(p.relative_to(root))
        for p in root.rglob("*.py")
        if p.name != "dialect.py"
        and ("on_duplicate_key_update" in p.read_text(encoding="utf-8")
             or "on_conflict_do_update" in p.read_text(encoding="utf-8"))
    ]
    assert offenders == [], f"방언 API가 dialect.py 밖에서 사용됨: {offenders}"
