"""잠정 → 확정 전환 (T060).

FR-037a: 전환은 **값을 다시 받아왔을 때만** 일어난다. 상태만 뒤집으면 출처가 마감 후
정정한 경우 틀린 값이 재현성 보장 구간으로 들어간다 (헌법 v5.0.0 원칙 V).
FR-037b: 잠정 레코드가 있다고 증분 수집이 그 날짜를 건너뛰면 안 된다.
FR-043: 전환 시점과 값 변화를 사후에 추적할 수 있어야 한다.
"""
from __future__ import annotations

import datetime as dt
from decimal import Decimal

from sqlalchemy import select

from src.db.models import FxCoverage, FxRawResponse
from src.ingestion.collector import collect_range, next_start_date
from src.ingestion.protocols import DailyQuote
from src.ingestion.today import store_provisional
from src.repository.fx_rate import get_rate

from .conftest import StubSource

START = dt.date(2026, 8, 1)
YESTERDAY = dt.date(2026, 8, 29)
TARGET = dt.date(2026, 8, 30)


async def _seed(session) -> None:
    session.add(FxCoverage(currency_code="USD", covered_from=START,
                           covered_through=YESTERDAY))
    # 어제 시점에 오늘(=TARGET)을 잠정으로 받아둔 상태
    await store_provisional(session, "USD", DailyQuote(TARGET, Decimal("1354.20"), 1))
    await session.commit()


async def test_증분_수집이_잠정_날짜를_건너뛰지_않는다(session_factory) -> None:
    """FR-037b — 커버리지가 잠정 때문에 전진해 있으면 이 검증이 실패한다."""
    async with session_factory() as s:
        await _seed(s)
        start = await next_start_date(s, "USD", default=START)
    assert start == TARGET


async def test_값을_다시_받아_확정으로_전환한다(session_factory) -> None:
    """FR-037a — 출처가 정정한 값(1358.90)으로 덮이고 확정이 된다."""
    src = StubSource({"USD": [(TARGET.isoformat(), "1358.90")]})
    async with session_factory() as s:
        await _seed(s)
        start = await next_start_date(s, "USD", default=START)
        await collect_range(s, src, "USD", start, TARGET, chunk_days=365)
        row = await get_rate(s, "USD", TARGET)

    assert row is not None
    assert row.is_provisional is False, "값을 덮었는데 잠정 상태가 남았다"
    assert row.base_rate == Decimal("1358.900000"), "정정된 값이 반영되지 않았다"


async def test_전환_후_커버리지가_전진한다(session_factory) -> None:
    src = StubSource({"USD": [(TARGET.isoformat(), "1358.90")]})
    async with session_factory() as s:
        await _seed(s)
        start = await next_start_date(s, "USD", default=START)
        await collect_range(s, src, "USD", start, TARGET, chunk_days=365)
        cov = (await s.execute(select(FxCoverage))).scalar_one()
    assert cov.covered_through == TARGET


async def test_잠정과_확정_시점의_원본_응답이_모두_남는다(session_factory) -> None:
    """FR-043 — 값 변화를 사후에 대조할 근거."""
    src = StubSource({"USD": [(TARGET.isoformat(), "1358.90")]})
    async with session_factory() as s:
        await _seed(s)  # 잠정 저장은 fetch_today 경로가 아니라 원본이 없다
        before = len(list((await s.execute(select(FxRawResponse))).scalars()))
        start = await next_start_date(s, "USD", default=START)
        await collect_range(s, src, "USD", start, TARGET, chunk_days=365)
        after = list((await s.execute(select(FxRawResponse))).scalars())

    assert len(after) > before, "확정 수집의 원본 응답이 남지 않았다"
    assert all(r.body is not None for r in after)


async def test_확정된_값은_다시_잠정이_되지_않는다(session_factory) -> None:
    """역방향 전이는 없다 (data-model 상태 전이)."""
    src = StubSource({"USD": [(TARGET.isoformat(), "1358.90")]})
    async with session_factory() as s:
        await _seed(s)
        await collect_range(s, src, "USD", TARGET, TARGET, chunk_days=365)
        # 같은 날짜를 다시 수집해도 확정은 유지된다
        await collect_range(s, src, "USD", TARGET, TARGET, chunk_days=365)
        row = await get_rate(s, "USD", TARGET)
    assert row is not None and row.is_provisional is False
