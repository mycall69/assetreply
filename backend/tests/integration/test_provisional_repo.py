"""확정/잠정 구분 조회 테스트 (T005).

헌법 v5.0.0 원칙 V: 재현성 보장은 **확정값**에 대한 것이다. 확정 전용 조회 경로가
있어야 SC-003(같은 날짜를 반복 조회하면 항상 같은 값)을 구현할 수 있다.
"""
from __future__ import annotations

import datetime as dt
from decimal import Decimal

from src.db.models import FxRate
from src.repository.fx_rate import get_rate, series

TODAY = dt.date(2026, 8, 30)
YESTERDAY = dt.date(2026, 8, 29)


async def _seed(session) -> None:
    session.add(FxRate(currency_code="USD", quote_date=YESTERDAY,
                       base_rate=Decimal("1356.100000"), quote_unit=1,
                       source="ECOS:731Y001", is_provisional=False))
    session.add(FxRate(currency_code="USD", quote_date=TODAY,
                       base_rate=Decimal("1354.200000"), quote_unit=1,
                       source="ECOS:731Y001", is_provisional=True))
    await session.commit()


async def test_확정_전용_조회는_잠정을_제외한다(session_factory) -> None:
    async with session_factory() as s:
        await _seed(s)
        row = await get_rate(s, "USD", TODAY, confirmed_only=True)
    assert row is None, "확정 전용 조회가 잠정 행을 반환했다 — SC-003이 깨진다"


async def test_기본_조회는_잠정을_포함한다(session_factory) -> None:
    async with session_factory() as s:
        await _seed(s)
        row = await get_rate(s, "USD", TODAY)
    assert row is not None and row.is_provisional is True


async def test_시계열_확정_전용_조회(session_factory) -> None:
    async with session_factory() as s:
        await _seed(s)
        rows = await series(s, "USD", YESTERDAY, TODAY, confirmed_only=True)
    assert [r.quote_date for r in rows] == [YESTERDAY]


async def test_시계열_기본_조회는_잠정을_포함한다(session_factory) -> None:
    async with session_factory() as s:
        await _seed(s)
        rows = await series(s, "USD", YESTERDAY, TODAY)
    assert [r.quote_date for r in rows] == [YESTERDAY, TODAY]
    assert rows[-1].is_provisional is True
