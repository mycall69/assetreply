"""오늘 새로고침 (T057, T058, T059).

FR-036: 오늘 하루치만 다시 받는다. 과거 구간을 재요청하지 않는다.
FR-036b: 같은 통화의 새로고침은 동시에 하나만. 중복은 진행 중인 것에 합류한다.
FR-039: 오늘 고시가 없으면 값을 만들어내지 않는다.
FR-040: 실패해도 저장된 과거 데이터가 유효하다.
SC-008: 새로고침 1회가 외부 호출 1회를 소비한다.
"""
from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from src.api.services.today_refresh import refresh_today
from src.db.dialect import upsert
from src.db.models import FxRate, FxRawResponse
from src.ingestion.ecos.errors import SourceUnavailable
from src.repository.fx_rate import get_rate

from .conftest import StubSource

TODAY = dt.date.today()
PAST = dt.date(2026, 1, 5)


async def _seed_past(session) -> None:
    await upsert(session, FxRate, [{
        "currency_code": "USD", "quote_date": PAST,
        "base_rate": Decimal("1300.000000"), "quote_unit": 1,
        "source": "ECOS:731Y001", "is_provisional": False}])
    await session.commit()


async def test_오늘_값을_잠정으로_저장한다(session_factory) -> None:
    src = StubSource({"USD": [(TODAY.isoformat(), "1354.20")]})
    async with session_factory() as s:
        result = await refresh_today(s, src, "USD", today=TODAY)
        row = await get_rate(s, "USD", TODAY)

    assert result.status == "updated"
    assert result.joined_existing is False
    assert row is not None and row.is_provisional is True
    assert row.base_rate == Decimal("1354.200000")


async def test_오늘_하루치만_요청한다(session_factory) -> None:
    """FR-036 — 과거 구간을 다시 받으면 호출 한도를 낭비한다."""
    src = StubSource({"USD": [(TODAY.isoformat(), "1354.20")]})
    async with session_factory() as s:
        await refresh_today(s, src, "USD", today=TODAY)

    assert src.requests == [("USD", TODAY, TODAY)]


async def test_호출_1회만_소비한다(session_factory) -> None:
    """SC-008."""
    src = StubSource({"USD": [(TODAY.isoformat(), "1354.20")]})
    async with session_factory() as s:
        await refresh_today(s, src, "USD", today=TODAY)
        count = (await s.execute(
            select(func.count()).select_from(FxRawResponse))).scalar_one()
    assert len(src.requests) == 1
    assert count == 1


async def test_오늘_고시가_없으면_값을_만들지_않는다(session_factory) -> None:
    """FR-039."""
    src = StubSource({"USD": []})
    async with session_factory() as s:
        result = await refresh_today(s, src, "USD", today=TODAY)
        row = await get_rate(s, "USD", TODAY)

    assert result.status == "no_quote_today"
    assert row is None


async def test_중복_요청은_진행_중인_것에_합류한다(session_factory) -> None:
    """FR-036b — 버튼을 연타해도 호출이 늘지 않는다."""
    src = StubSource({"USD": [(TODAY.isoformat(), "1354.20")]})
    async with session_factory() as s:
        await refresh_today(s, src, "USD", today=TODAY, release=False)
    async with session_factory() as s:
        second = await refresh_today(s, src, "USD", today=TODAY)

    assert second.joined_existing is True
    assert len(src.requests) == 1, "합류했는데도 외부를 다시 호출했다"


async def test_실패해도_과거_데이터가_유효하다(session_factory) -> None:
    """FR-040."""
    src = StubSource({"USD": [(TODAY.isoformat(), "1354.20")]})
    src.raise_on_call = SourceUnavailable("응답 없음")
    async with session_factory() as s:
        await _seed_past(s)
        with pytest.raises(SourceUnavailable):
            await refresh_today(s, src, "USD", today=TODAY)

    async with session_factory() as s:
        past = await get_rate(s, "USD", PAST)
    assert past is not None and past.base_rate == Decimal("1300.000000")


async def test_실패_후에도_잠금이_해제된다(session_factory) -> None:
    """잠금이 남으면 재시도가 영영 막힌다."""
    src = StubSource({"USD": []})
    src.raise_on_call = SourceUnavailable("응답 없음")
    async with session_factory() as s:
        with pytest.raises(SourceUnavailable):
            await refresh_today(s, src, "USD", today=TODAY)

    ok = StubSource({"USD": [(TODAY.isoformat(), "1354.20")]})
    async with session_factory() as s:
        result = await refresh_today(s, ok, "USD", today=TODAY)
    assert result.joined_existing is False
