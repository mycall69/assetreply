"""잠정값이 확정 구간을 오염시키지 않음 (T061).

FR-042 / SC-003 / 헌법 v5.0.0 원칙 V: 재현성 보장은 확정값에 대한 것이다. 잠정값은
재조회 시 달라질 수 있으나 **그 가변성이 확정 구간으로 번져서는 안 된다.**
"""
from __future__ import annotations

import datetime as dt
from decimal import Decimal

from src.ingestion.protocols import DailyQuote
from src.ingestion.today import store_provisional
from src.repository.fx_rate import get_rate

CONFIRMED = dt.date(2026, 8, 29)
TODAY = dt.date(2026, 8, 30)


async def _seed_confirmed(session) -> None:
    from src.db.dialect import upsert
    from src.db.models import FxRate

    await upsert(session, FxRate, [{
        "currency_code": "USD", "quote_date": CONFIRMED,
        "base_rate": Decimal("1356.100000"), "quote_unit": 1,
        "source": "ECOS:731Y001", "is_provisional": False}])
    await session.commit()


async def test_잠정값을_여러_번_갱신해도_확정값이_변하지_않는다(session_factory) -> None:
    async with session_factory() as s:
        await _seed_confirmed(s)
        before = (await get_rate(s, "USD", CONFIRMED)).base_rate

        for rate in ("1354.20", "1352.80", "1358.90"):
            await store_provisional(s, "USD", DailyQuote(TODAY, Decimal(rate), 1))
            await s.commit()

        after = (await get_rate(s, "USD", CONFIRMED)).base_rate

    assert before == after, "잠정 갱신이 확정 구간을 건드렸다 (FR-042 위반)"


async def test_잠정값은_재조회_시_달라질_수_있다(session_factory) -> None:
    """확정 전이므로 값이 바뀌는 것이 정상이다."""
    async with session_factory() as s:
        await store_provisional(s, "USD", DailyQuote(TODAY, Decimal("1354.20"), 1))
        await s.commit()
        first = (await get_rate(s, "USD", TODAY)).base_rate

        await store_provisional(s, "USD", DailyQuote(TODAY, Decimal("1358.90"), 1))
        await s.commit()
        second = (await get_rate(s, "USD", TODAY)).base_rate

    assert first != second
    assert second == Decimal("1358.900000")


async def test_확정_전용_조회는_잠정을_보지_않는다(session_factory) -> None:
    """SC-003의 구현 근거."""
    async with session_factory() as s:
        await _seed_confirmed(s)
        await store_provisional(s, "USD", DailyQuote(TODAY, Decimal("1354.20"), 1))
        await s.commit()
        assert await get_rate(s, "USD", TODAY, confirmed_only=True) is None
        assert await get_rate(s, "USD", CONFIRMED, confirmed_only=True) is not None
