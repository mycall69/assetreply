"""멱등 수집과 정정 처리 통합 테스트 (T041).

FR-003: 재수집해도 중복 레코드를 만들지 않는다.
FR-003a/b: 출처가 정정하면 갱신하되 최초 수집 시각과 원본 응답은 보존한다.
"""
from __future__ import annotations

import datetime as dt
from decimal import Decimal

from sqlalchemy import func, select

from src.db.models import FxRate, FxRawResponse
from src.ingestion.collector import collect_range

from .conftest import StubSource


async def _collect(session_factory, value: str) -> None:
    src = StubSource({"USD": [("2005-03-15", value)]})
    async with session_factory() as s:
        await collect_range(s, src, "USD", dt.date(2005, 3, 15), dt.date(2005, 3, 15),
                            chunk_days=365)
        await s.commit()


async def test_최초_수집이_저장된다(session_factory) -> None:
    await _collect(session_factory, "1012.30")
    async with session_factory() as s:
        assert (await s.execute(select(func.count()).select_from(FxRate))).scalar() == 1


async def test_같은_구간_재수집이_중복을_만들지_않는다(session_factory) -> None:
    await _collect(session_factory, "1012.30")
    await _collect(session_factory, "1012.30")
    async with session_factory() as s:
        assert (await s.execute(select(func.count()).select_from(FxRate))).scalar() == 1


async def test_출처가_정정하면_갱신된다(session_factory) -> None:
    """FR-003a."""
    await _collect(session_factory, "1012.30")
    await _collect(session_factory, "1099.99")
    async with session_factory() as s:
        row = (await s.execute(select(FxRate))).scalar_one()
    assert row.base_rate == Decimal("1099.990000")


async def test_갱신되어도_최초_수집시각은_유지된다(session_factory) -> None:
    await _collect(session_factory, "1012.30")
    async with session_factory() as s:
        first = (await s.execute(select(FxRate))).scalar_one().ingested_at
    await _collect(session_factory, "1099.99")
    async with session_factory() as s:
        row = (await s.execute(select(FxRate))).scalar_one()
    assert row.ingested_at == first


async def test_원본_응답이_누적_보존된다(session_factory) -> None:
    """FR-003b·FR-004a: 갱신 전 값을 추적하는 유일한 근거."""
    await _collect(session_factory, "1012.30")
    await _collect(session_factory, "1099.99")
    async with session_factory() as s:
        n = (await s.execute(select(func.count()).select_from(FxRawResponse))).scalar()
    assert n == 2, "원본이 덮어써졌다"


async def test_수집_레코드에_출처와_시각이_기록된다(session_factory) -> None:
    """FR-004."""
    await _collect(session_factory, "1012.30")
    async with session_factory() as s:
        row = (await s.execute(select(FxRate))).scalar_one()
    assert row.source
    assert row.ingested_at is not None
