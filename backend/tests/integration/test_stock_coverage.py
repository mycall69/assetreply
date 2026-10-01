"""수집 구간 기록과 빠진 구간 계산 (T017) — 005 FR-044.

**이미 받은 구간을 다시 받으면** 출처 호출을 낭비하고, 출처가 막혔을 때 이미 가진
데이터로도 답하지 못하게 된다. 출처가 호출 한도를 공개하지 않으므로 낭비의 대가를
미리 알 수 없다.
"""
from __future__ import annotations

import datetime as dt

import pytest
from sqlalchemy import select

from src.db.dialect import upsert
from src.db.models import Stock
from src.repository.stock import (
    get_coverage,
    missing_ranges,
    record_coverage,
)

D = dt.date.fromisoformat


@pytest.fixture
async def stock_id(session_factory) -> int:
    async with session_factory() as s:
        await upsert(s, Stock, [{
            "market": "KRX", "symbol": "005930.KS", "name": "삼성전자",
            "currency": "KRW"}])
        await s.commit()
        return int((await s.execute(select(Stock))).scalar_one().id)


class Test빠진_구간_계산:
    """순수 계산이라 DB 없이도 돈다."""

    def test_커버리지가_없으면_전부_빠져_있다(self) -> None:
        assert missing_ranges(None, D("2021-01-01"), D("2021-12-31")) == [
            (D("2021-01-01"), D("2021-12-31"))]

    def test_완전히_덮였으면_빠진_구간이_없다(self) -> None:
        """SC-022 — 같은 구간을 다시 받지 않는다."""
        assert missing_ranges(
            (D("2020-01-01"), D("2022-12-31")), D("2021-01-01"), D("2021-12-31")) == []

    def test_앞쪽이_빠지면_그만큼만_받는다(self) -> None:
        assert missing_ranges(
            (D("2021-06-01"), D("2021-12-31")), D("2021-01-01"), D("2021-12-31")) == [
            (D("2021-01-01"), D("2021-05-31"))]

    def test_뒤쪽이_빠지면_그만큼만_받는다(self) -> None:
        assert missing_ranges(
            (D("2021-01-01"), D("2021-06-30")), D("2021-01-01"), D("2021-12-31")) == [
            (D("2021-07-01"), D("2021-12-31"))]

    def test_양쪽이_빠지면_두_구간이다(self) -> None:
        assert missing_ranges(
            (D("2021-06-01"), D("2021-06-30")), D("2021-01-01"), D("2021-12-31")) == [
            (D("2021-01-01"), D("2021-05-31")),
            (D("2021-07-01"), D("2021-12-31"))]

    def test_커버리지가_요청_밖이면_전부_받는다(self) -> None:
        assert missing_ranges(
            (D("2010-01-01"), D("2010-12-31")), D("2021-01-01"), D("2021-12-31")) == [
            (D("2021-01-01"), D("2021-12-31"))]

    def test_경계가_맞닿으면_빈_구간을_만들지_않는다(self) -> None:
        """하루짜리 빈 구간을 만들면 그것 때문에 호출이 한 번 더 나간다."""
        assert missing_ranges(
            (D("2021-01-01"), D("2021-12-31")), D("2021-01-01"), D("2021-12-31")) == []


class Test커버리지_기록:
    async def test_처음_기록하면_그대로_남는다(self, session_factory, stock_id) -> None:
        async with session_factory() as s:
            await record_coverage(s, stock_id, D("2021-01-01"), D("2021-12-31"))
            await s.commit()
            got = await get_coverage(s, stock_id)
        assert got == (D("2021-01-01"), D("2021-12-31"))

    async def test_구간을_넓히면_합쳐진다(self, session_factory, stock_id) -> None:
        """FR-045 — 재개가 이것에 기댄다. 덮어쓰면 앞서 받은 구간을 잊는다."""
        async with session_factory() as s:
            await record_coverage(s, stock_id, D("2021-06-01"), D("2021-12-31"))
            await record_coverage(s, stock_id, D("2021-01-01"), D("2021-05-31"))
            await s.commit()
            got = await get_coverage(s, stock_id)
        assert got == (D("2021-01-01"), D("2021-12-31"))

    async def test_좁은_구간을_다시_기록해도_줄지_않는다(
        self, session_factory, stock_id
    ) -> None:
        async with session_factory() as s:
            await record_coverage(s, stock_id, D("2021-01-01"), D("2021-12-31"))
            await record_coverage(s, stock_id, D("2021-06-01"), D("2021-06-30"))
            await s.commit()
            got = await get_coverage(s, stock_id)
        assert got == (D("2021-01-01"), D("2021-12-31"))

    async def test_기록이_없으면_None이다(self, session_factory, stock_id) -> None:
        async with session_factory() as s:
            assert await get_coverage(s, stock_id) is None

    async def test_종목마다_따로_기록된다(self, session_factory, stock_id) -> None:
        """`fx_coverage`와 합치지 않은 이유와 같다 — 단위가 다르면 질의가 서로를 거른다."""
        async with session_factory() as s:
            await upsert(s, Stock, [{
                "market": "NASDAQ", "symbol": "AAPL", "name": "Apple",
                "currency": "USD"}])
            await s.commit()
            other = int((await s.execute(
                select(Stock).where(Stock.symbol == "AAPL"))).scalar_one().id)
            await record_coverage(s, stock_id, D("2021-01-01"), D("2021-12-31"))
            await s.commit()
            assert await get_coverage(s, other) is None
