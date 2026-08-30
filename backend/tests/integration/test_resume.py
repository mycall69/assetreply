"""중단 후 재개 통합 테스트 (T042).

FR-010: 청크가 성공할 때마다 저장·커밋하고 커버리지를 갱신한다.
FR-011: 재실행 시 마지막 완료 청크의 다음 구간부터 재개한다.
"""
from __future__ import annotations

import datetime as dt

from sqlalchemy import select

from src.db.models import FxCoverage
from src.ingestion.collector import collect_range, next_start_date

from .conftest import StubSource

QUOTES = {"USD": [(f"2020-{m:02d}-01", "1200.00") for m in range(1, 13)]}


async def test_청크마다_커버리지가_갱신된다(session_factory) -> None:
    src = StubSource(QUOTES)
    async with session_factory() as s:
        await collect_range(s, src, "USD", dt.date(2020, 1, 1), dt.date(2020, 12, 31),
                            chunk_days=90)
        await s.commit()
        cov = (await s.execute(select(FxCoverage))).scalar_one()
    assert cov.covered_through == dt.date(2020, 12, 31)


async def test_재개_시작일은_커버리지_다음날이다(session_factory) -> None:
    """탐색 시작일까지 이미 채워진 상태의 순수 재개 시나리오.

    탐색 시작일이 `covered_from`보다 이르면 앞 구간을 먼저 채우는 것이 옳으므로
    (FR-002, test_backward_backfill.py) 여기서는 같은 날짜를 준다.
    """
    src = StubSource(QUOTES)
    async with session_factory() as s:
        await collect_range(s, src, "USD", dt.date(2020, 1, 1), dt.date(2020, 6, 30),
                            chunk_days=90)
        await s.commit()
        start = await next_start_date(s, "USD", default=dt.date(2020, 1, 1))
    assert start == dt.date(2020, 7, 1)


async def test_커버리지가_없으면_기본_시작일을_쓴다(session_factory) -> None:
    async with session_factory() as s:
        start = await next_start_date(s, "USD", default=dt.date(1995, 1, 1))
    assert start == dt.date(1995, 1, 1)


async def test_재실행이_이미_받은_구간을_다시_요청하지_않는다(session_factory) -> None:
    """FR-011·SC-004."""
    src = StubSource(QUOTES)
    async with session_factory() as s:
        await collect_range(s, src, "USD", dt.date(2020, 1, 1), dt.date(2020, 6, 30),
                            chunk_days=90)
        await s.commit()
        first_round = len(src.requests)
        start = await next_start_date(s, "USD", default=dt.date(2020, 1, 1))
        await collect_range(s, src, "USD", start, dt.date(2020, 12, 31), chunk_days=90)
        await s.commit()
    for _, frm, _to in src.requests[first_round:]:
        assert frm >= dt.date(2020, 7, 1), f"이미 수집한 구간을 재요청했다: {frm}"


async def test_중단되어도_완료_청크는_보존된다(session_factory) -> None:
    """FR-013: 이미 커밋된 구간의 데이터와 커버리지는 유효하다."""
    from src.ingestion.ecos.errors import SourceRateLimited

    src = StubSource(QUOTES)
    async with session_factory() as s:
        await collect_range(s, src, "USD", dt.date(2020, 1, 1), dt.date(2020, 3, 31),
                            chunk_days=90)
        await s.commit()
        src.raise_on_call = SourceRateLimited("한도 초과")
        try:
            await collect_range(s, src, "USD", dt.date(2020, 4, 1), dt.date(2020, 12, 31),
                                chunk_days=90)
        except SourceRateLimited:
            pass
        cov = (await s.execute(select(FxCoverage))).scalar_one()
    assert cov.covered_through == dt.date(2020, 3, 31)


async def test_선두_데이터없음_구간에서_최초제공일을_발견한다(session_factory) -> None:
    """research R3: 실제 최초 제공일을 런타임에 발견한다."""
    from src.db.models import Currency

    src = StubSource({"USD": [("1999-01-04", "1200.00")]})
    async with session_factory() as s:
        await collect_range(s, src, "USD", dt.date(1995, 1, 1), dt.date(1999, 12, 31),
                            chunk_days=365)
        await s.commit()
        cur = (await s.execute(select(Currency).where(Currency.code == "USD"))).scalar_one()
    assert cur.first_available_date == dt.date(1999, 1, 4)
