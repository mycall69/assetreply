"""기간 단위의 행 수 감축 (T022) — 004 SC-001, SC-011.

**픽스처가 짧으면 비율이 성립하지 않는다.** 한국 영업일은 월 약 20.8일이라 1/20은 긴
구간에서만 안정적이다. 실측 1/23은 60년 전체 기준이다 (data-model 7절). 짧은 픽스처로
검증하면 통과와 실패가 픽스처 모양에 좌우되어, 회귀가 생겨도 드러나지 않는다.
"""
from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest

from src.api.services.period_rows import period_page
from src.db.dialect import upsert
from src.db.models import FxRate

YEARS = 12
PAGE = 30
SATURDAY = 5


def _weekdays(start: dt.date, end: dt.date) -> list[dt.date]:
    """영업일 근사 — 주말을 뺀 모든 날. 한국 외환시장은 주말 고시를 하지 않는다."""
    days, day = [], start
    while day <= end:
        if day.weekday() < SATURDAY:
            days.append(day)
        day += dt.timedelta(days=1)
    return days


@pytest.fixture
async def seeded(session_factory):
    days = _weekdays(dt.date(2014, 1, 1), dt.date(2025, 12, 31))
    async with session_factory() as s:
        for i in range(0, len(days), 500):
            await upsert(s, FxRate, [
                {"currency_code": "USD", "quote_date": d,
                 "base_rate": Decimal("1300.00"), "quote_unit": 1,
                 "source": "ECOS:731Y001", "is_provisional": False}
                for d in days[i:i + 500]
            ])
        await s.commit()
    return session_factory, len(days)


async def _count(factory, unit: str) -> int:
    async with factory() as s:
        return len(await period_page(s, "USD", unit=unit, before=None, limit=5000))


async def test_월_단위는_일_단위의_20분의_1_이하다(seeded) -> None:
    """SC-011 — 12년(약 3,130 영업일)에서 검증한다."""
    factory, daily = seeded
    monthly = await _count(factory, "monthly")
    assert monthly == YEARS * 12
    assert monthly * 20 <= daily, f"월 {monthly}행 / 일 {daily}행 — 1/20을 넘는다"


async def test_주_단위도_행을_크게_줄인다(seeded) -> None:
    factory, daily = seeded
    weekly = await _count(factory, "weekly")
    assert weekly * 4 <= daily


async def test_월_단위는_스크롤만으로_끝까지_도달한다(seeded) -> None:
    """SC-001 — 30행씩 받아 전 구간을 훑는 데 드는 요청 수가 현실적이어야 한다."""
    factory, daily = seeded
    monthly = await _count(factory, "monthly")
    monthly_pages = -(-monthly // PAGE)
    daily_pages = -(-daily // PAGE)
    assert monthly_pages <= 10
    assert monthly_pages * 10 <= daily_pages, "단위를 넓혀도 요청 수가 줄지 않는다"


async def test_커서로_전_구간을_빠짐없이_훑는다(seeded) -> None:
    """FR-005, SC-004 — 같은 구간이 두 번 나오거나 건너뛰면 안 된다."""
    factory, _ = seeded
    seen: list[dt.date] = []
    cursor: dt.date | None = None
    async with factory() as s:
        while True:
            page = await period_page(
                s, "USD", unit="monthly", before=cursor, limit=PAGE)
            if not page:
                break
            seen.extend(r.quote_date for r in page)
            cursor = page[-1].quote_date
    assert len(seen) == len(set(seen)), "같은 기준일이 두 번 나왔다"
    assert len(seen) == YEARS * 12
    assert seen == sorted(seen, reverse=True)
