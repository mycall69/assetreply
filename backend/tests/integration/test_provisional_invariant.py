"""잠정 레코드 불변식 (T088) — FR-037c.

"잠정 상태의 레코드는 통화당 최대 하나이며 그 날짜는 오늘이어야 한다."

이 불변식을 **쓰기 시점에** 강제한다. 오늘이 아닌 날짜를 잠정으로 쓸 수 있으면 과거에
잠정 레코드가 생기고, 그것은 확정 전환이 일어나지 않은 것과 구별되지 않는다. 두 원인이
같은 증상을 내면 원인을 좁힐 수 없다.

날짜를 오늘로 제한하면 "통화당 최대 하나"는 기본 키 `(currency_code, quote_date)`에서
자동으로 따라온다 — 오늘은 하루뿐이므로 행도 하나뿐이다.
"""
from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from src.db.models import FxRate
from src.ingestion.protocols import DailyQuote
from src.ingestion.today import store_provisional

TODAY = dt.date(2026, 8, 30)
YESTERDAY = dt.date(2026, 8, 29)
TOMORROW = dt.date(2026, 8, 31)


async def test_오늘_날짜는_잠정으로_저장된다(session_factory) -> None:
    async with session_factory() as s:
        await store_provisional(
            s, "USD", DailyQuote(TODAY, Decimal("1354.20"), 1), today=TODAY)
        await s.commit()
        row = (await s.execute(select(FxRate))).scalar_one()
    assert row.is_provisional is True


async def test_과거_날짜를_잠정으로_저장할_수_없다(session_factory) -> None:
    """과거의 잠정은 확정 전환 실패와 구별되지 않는다. 애초에 만들지 못하게 한다."""
    async with session_factory() as s:
        with pytest.raises(ValueError, match="오늘"):
            await store_provisional(
                s, "USD", DailyQuote(YESTERDAY, Decimal("1356.10"), 1), today=TODAY)


async def test_미래_날짜를_잠정으로_저장할_수_없다(session_factory) -> None:
    async with session_factory() as s:
        with pytest.raises(ValueError, match="오늘"):
            await store_provisional(
                s, "USD", DailyQuote(TOMORROW, Decimal("1350.00"), 1), today=TODAY)


async def test_거부된_저장은_행을_남기지_않는다(session_factory) -> None:
    async with session_factory() as s:
        with pytest.raises(ValueError):
            await store_provisional(
                s, "USD", DailyQuote(YESTERDAY, Decimal("1356.10"), 1), today=TODAY)
        await s.rollback()
        count = (await s.execute(select(func.count()).select_from(FxRate))).scalar_one()
    assert count == 0


async def test_같은_날_여러_번_받아도_잠정은_한_행이다(session_factory) -> None:
    """FR-037c의 "통화당 최대 하나"는 날짜 제한에서 자동으로 따라온다."""
    async with session_factory() as s:
        for rate in ("1354.20", "1352.80", "1358.90"):
            await store_provisional(
                s, "USD", DailyQuote(TODAY, Decimal(rate), 1), today=TODAY)
            await s.commit()
        rows = list((await s.execute(
            select(FxRate).where(FxRate.is_provisional.is_(True)))).scalars())

    assert len(rows) == 1
    assert rows[0].base_rate == Decimal("1358.900000")


async def test_통화마다_각각_한_행씩_가질_수_있다(session_factory) -> None:
    async with session_factory() as s:
        for code in ("USD", "JPY", "EUR"):
            await store_provisional(
                s, code, DailyQuote(TODAY, Decimal("1000.00"), 1), today=TODAY)
        await s.commit()
        rows = list((await s.execute(
            select(FxRate).where(FxRate.is_provisional.is_(True)))).scalars())

    assert {r.currency_code for r in rows} == {"USD", "JPY", "EUR"}
    assert len(rows) == 3
