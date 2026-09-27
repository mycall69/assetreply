"""주·월 단위 페이지 조회 (T008) — 004 FR-008, FR-015, SC-006, SC-009.

**구간의 마지막 고시일을 뽑는다.** 금요일·말일을 먼저 찾고 실패하면 다시 찾는 2단계가
필요 없다 — 금요일은 그 주의 마지막 영업일이므로 두 경우가 한 번에 풀린다 (research R4-2).

빈 구간에 행이 생기면 그것은 값을 지어낸 것이다 (헌법 원칙 V).
"""
from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest

from src.api.services.period_rows import period_page
from src.db.dialect import upsert
from src.db.models import FxRate

# 2026-07-17(금) 결측 → 그 주는 07-16(목)이 마지막
# 2026-08-03 ~ 08-09 한 주 전체 결측 → 그 주는 행이 없어야 한다
DAYS = [
    "2026-07-13", "2026-07-14", "2026-07-15", "2026-07-16",
    "2026-07-20", "2026-07-21", "2026-07-22", "2026-07-23", "2026-07-24",
    "2026-07-27", "2026-07-28", "2026-07-29", "2026-07-30", "2026-07-31",
    "2026-08-10", "2026-08-11", "2026-08-12", "2026-08-13", "2026-08-14",
]


async def _seed(session_factory, days: list[str]) -> None:
    async with session_factory() as s:
        await upsert(s, FxRate, [
            {"currency_code": "USD", "quote_date": dt.date.fromisoformat(d),
             "base_rate": Decimal("1300.00") + Decimal(i), "quote_unit": 1,
             "source": "ECOS:731Y001", "is_provisional": False}
            for i, d in enumerate(days)
        ])
        await s.commit()


@pytest.fixture
async def seeded(session_factory):
    await _seed(session_factory, DAYS)
    return session_factory


async def _dates(factory, **kwargs) -> list[str]:
    async with factory() as s:
        rows = await period_page(s, "USD", **kwargs)
    return [r.quote_date.isoformat() for r in rows]


async def test_주_단위는_구간별_마지막_고시일만_돌려준다(seeded) -> None:
    """FR-008 — 금요일이 있으면 금요일, 없으면 그 주의 마지막 고시일."""
    assert await _dates(seeded, unit="weekly", before=None, limit=30) == [
        "2026-08-14", "2026-07-31", "2026-07-24", "2026-07-16"]


async def test_고시가_없는_주에는_행이_생기지_않는다(seeded) -> None:
    """FR-015, SC-009 — 인접 구간의 값을 복사하지 않는다."""
    dates = await _dates(seeded, unit="weekly", before=None, limit=30)
    assert not any("2026-08-03" <= d <= "2026-08-09" for d in dates)


async def test_돌려준_날짜는_모두_실제_고시일이다(seeded) -> None:
    """SC-006 — 존재하지 않는 날짜가 행으로 나오지 않는다."""
    dates = await _dates(seeded, unit="weekly", before=None, limit=30)
    assert set(dates) <= set(DAYS)


async def test_월_단위는_달마다_한_행이다(seeded) -> None:
    assert await _dates(seeded, unit="monthly", before=None, limit=30) == [
        "2026-08-14", "2026-07-31"]


async def test_커서는_기준일_기준으로_동작한다(seeded) -> None:
    """research R4-3 — 주·월 단위에서 `before`는 기준일 미만을 뜻한다."""
    assert await _dates(
        seeded, unit="weekly", before=dt.date(2026, 7, 31), limit=30) == [
        "2026-07-24", "2026-07-16"]


async def test_limit은_구간_수를_제한한다(seeded) -> None:
    assert await _dates(seeded, unit="weekly", before=None, limit=2) == [
        "2026-08-14", "2026-07-31"]


async def test_일_단위는_모든_고시일을_돌려준다(seeded) -> None:
    dates = await _dates(seeded, unit="daily", before=None, limit=50)
    assert dates == sorted(DAYS, reverse=True)


async def test_축적이_한_구간에_못_미치면_행이_하나다(session_factory) -> None:
    """spec Edge Cases — 오류가 아니다. 한 주치만 쌓였으면 주 단위에 한 행이 정상이다."""
    short = ["2026-09-14", "2026-09-15", "2026-09-16"]
    await _seed(session_factory, short)
    assert await _dates(session_factory, unit="weekly", before=None, limit=30) == [
        "2026-09-16"]
    assert await _dates(session_factory, unit="monthly", before=None, limit=30) == [
        "2026-09-16"]


async def test_데이터가_없으면_빈_목록이다(session_factory) -> None:
    assert await _dates(session_factory, unit="monthly", before=None, limit=30) == []
