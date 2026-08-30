"""날짜별 환율 조회 통합 테스트 (T038~T040).

contracts/rest-api.md의 `GET /api/fx/rates/{currency}` 응답 규약.
"""
from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest

from src.api.errors import OutOfRange
from src.api.services.rate_query import query_rate
from src.db.dialect import upsert
from src.db.models import FxCoverage, FxRate


async def _seed(session_factory, rows: list[tuple[str, str]],
                covered: tuple[str, str]) -> None:
    async with session_factory() as s:
        await upsert(s, FxRate, [
            {"currency_code": "USD", "quote_date": dt.date.fromisoformat(d),
             "base_rate": Decimal(v), "quote_unit": 1, "source": "TEST"}
            for d, v in rows])
        await upsert(s, FxCoverage, [{
            "currency_code": "USD",
            "covered_from": dt.date.fromisoformat(covered[0]),
            "covered_through": dt.date.fromisoformat(covered[1]),
        }], preserve=())
        await s.commit()


class Test고시가_있는_날:
    async def test_값과_단위와_출처를_반환한다(self, session_factory) -> None:
        await _seed(session_factory, [("2005-03-15", "1012.30")], ("2005-03-01", "2005-03-31"))
        async with session_factory() as s:
            r = await query_rate(s, "USD", dt.date(2005, 3, 15))
        assert r.status == "quoted"
        assert r.base_rate == Decimal("1012.300000")
        assert r.quote_unit == 1
        assert r.source == "TEST"

    async def test_반복_조회가_같은_값을_준다(self, session_factory) -> None:
        """SC-003: 재현성."""
        await _seed(session_factory, [("2005-03-15", "1012.30")], ("2005-03-01", "2005-03-31"))
        async with session_factory() as s:
            a = await query_rate(s, "USD", dt.date(2005, 3, 15))
            b = await query_rate(s, "USD", dt.date(2005, 3, 15))
        assert a.base_rate == b.base_rate


class Test고시가_없는_날:
    """FR-018·FR-018a·FR-018b — 값을 만들어내지 않는다."""

    async def test_고시_없음을_주_결과로_알린다(self, session_factory) -> None:
        await _seed(session_factory, [("2005-03-18", "1010.90")], ("2005-03-01", "2005-03-31"))
        async with session_factory() as s:
            r = await query_rate(s, "USD", dt.date(2005, 3, 19))
        assert r.status == "no_quote"
        assert r.base_rate is None, "주 결과에 값이 있으면 안 된다"

    async def test_직전_영업일을_참고로_제시한다(self, session_factory) -> None:
        await _seed(session_factory, [("2005-03-18", "1010.90")], ("2005-03-01", "2005-03-31"))
        async with session_factory() as s:
            r = await query_rate(s, "USD", dt.date(2005, 3, 19))
        assert r.reference is not None
        assert r.reference.quote_date == dt.date(2005, 3, 18)
        assert r.reference.base_rate == Decimal("1010.900000")

    async def test_참고값이_요청일_값이_아님을_표기한다(self, session_factory) -> None:
        await _seed(session_factory, [("2005-03-18", "1010.90")], ("2005-03-01", "2005-03-31"))
        async with session_factory() as s:
            r = await query_rate(s, "USD", dt.date(2005, 3, 19))
        assert "2005-03-19" in r.reference.note

    async def test_직전_영업일이_없으면_참고도_없다(self, session_factory) -> None:
        await _seed(session_factory, [("2005-03-18", "1010.90")], ("2005-03-01", "2005-03-31"))
        async with session_factory() as s:
            r = await query_rate(s, "USD", dt.date(2005, 3, 2))
        assert r.status == "no_quote"
        assert r.reference is None

    async def test_보간하지_않는다(self, session_factory) -> None:
        """SC-007: 임의로 만들어낸 값을 반환하는 사례가 0건."""
        await _seed(session_factory, [("2005-03-18", "1010.90"), ("2005-03-21", "1015.00")],
                    ("2005-03-01", "2005-03-31"))
        async with session_factory() as s:
            for day in (19, 20):
                r = await query_rate(s, "USD", dt.date(2005, 3, day))
                assert r.base_rate is None


class Test범위_밖:
    """FR-019."""

    async def test_커버리지_이전_날짜는_거부한다(self, session_factory) -> None:
        await _seed(session_factory, [("2005-03-15", "1012.30")], ("2005-03-01", "2005-03-31"))
        async with session_factory() as s:
            with pytest.raises(OutOfRange):
                await query_rate(s, "USD", dt.date(2004, 1, 1))

    async def test_오늘_이후는_거부한다(self, session_factory) -> None:
        await _seed(session_factory, [("2005-03-15", "1012.30")], ("2005-03-01", "2005-03-31"))
        async with session_factory() as s:
            with pytest.raises(OutOfRange):
                await query_rate(s, "USD", dt.date.today() + dt.timedelta(days=1))
