"""잠정 레코드와 커버리지의 관계 (T006).

FR-037b / research R2-2 — **이번 기능에서 가장 조용한 함정.**

001의 재개 로직은 `covered_through + 1`부터 다시 받는다. 오늘 잠정 행을 저장하면서
커버리지를 오늘까지 밀면 다음 증분 수집이 오늘을 건너뛰고, 잠정값이 영원히 확정되지
않는다. 화면은 확정으로 바뀌지도 않고 정정도 반영되지 않는데 오류는 나지 않는다.
"""
from __future__ import annotations

import datetime as dt
from decimal import Decimal

from sqlalchemy import select

from src.db.models import FxCoverage
from src.ingestion.collector import next_start_date
from src.ingestion.protocols import DailyQuote
from src.ingestion.today import store_provisional

TODAY = dt.date(2026, 8, 30)
YESTERDAY = dt.date(2026, 8, 29)
START = dt.date(2026, 8, 1)


async def _seed_coverage(session) -> None:
    session.add(FxCoverage(currency_code="USD", covered_from=START,
                           covered_through=YESTERDAY))
    await session.commit()


async def test_잠정_저장이_커버리지를_전진시키지_않는다(session_factory) -> None:
    async with session_factory() as s:
        await _seed_coverage(s)
        await store_provisional(s, "USD", DailyQuote(TODAY, Decimal("1354.2"), 1),
                                today=TODAY, source="ECOS:731Y001")
        await s.commit()
        cov = (await s.execute(select(FxCoverage))).scalar_one()

    assert cov.covered_through == YESTERDAY, (
        "잠정 저장이 커버리지를 전진시켰다. 다음 증분 수집이 오늘을 건너뛰어 "
        "잠정값이 영원히 확정되지 않는다 (FR-037b)")


async def test_잠정_저장_후에도_재개_시작일이_오늘을_포함한다(session_factory) -> None:
    """확정 전환이 성립하는지 확인하는 핵심 검증."""
    async with session_factory() as s:
        await _seed_coverage(s)
        await store_provisional(s, "USD", DailyQuote(TODAY, Decimal("1354.2"), 1),
                                today=TODAY, source="ECOS:731Y001")
        await s.commit()
        start = await next_start_date(s, "USD", default=START)

    assert start == TODAY, f"재개 시작일이 {start} — 오늘을 건너뛴다"
