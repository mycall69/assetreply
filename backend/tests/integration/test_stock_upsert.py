"""주식 시계열 저장 불변식 (T014, T023) — 헌법 시계열 불변식.

`(종목, 날짜)` 복합 유니크 키 + upsert가 수집의 **멱등성과 재개 가능성**을 만든다.
같은 구간을 다시 받아도 행이 늘지 않아야 중단 후 이어받기가 안전하다.

모든 레코드에 `source`·`ingested_at`이 남아야 한다. 같은 날짜의 값이 나중에 달라졌을 때
무엇이 언제 들어온 것인지 알 수 없으면 되짚을 수단이 없다 (FR-046).
"""
from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest
from sqlalchemy import select

from src.db.dialect import upsert
from src.db.models import Stock, StockDividend, StockPrice, StockSplit


@pytest.fixture
async def stock_id(session_factory) -> int:
    async with session_factory() as s:
        await upsert(s, Stock, [{
            "market": "KRX", "symbol": "005930.KS", "name": "삼성전자",
            "currency": "KRW", "first_available_date": dt.date(1975, 6, 11)}])
        await s.commit()
        row = (await s.execute(select(Stock))).scalar_one()
        return int(row.id)


def price_row(stock_id: int, date: str, open_raw: str) -> dict[str, object]:
    return {
        "stock_id": stock_id, "quote_date": dt.date.fromisoformat(date),
        "open_raw": Decimal(open_raw), "close_raw": Decimal(open_raw),
        "close_adjusted": Decimal(open_raw), "source": "yahoo:chart"}


class Test멱등성:
    async def test_같은_날짜를_두_번_저장해도_한_행이다(self, session_factory, stock_id) -> None:
        async with session_factory() as s:
            await upsert(s, StockPrice, [price_row(stock_id, "2021-08-02", "113500")])
            await upsert(s, StockPrice, [price_row(stock_id, "2021-08-02", "113500")])
            await s.commit()
            rows = (await s.execute(select(StockPrice))).scalars().all()
        assert len(rows) == 1

    async def test_값이_바뀌면_갱신된다(self, session_factory, stock_id) -> None:
        """출처가 값을 정정할 수 있다. 행이 둘이 되면 어느 것이 맞는지 알 수 없다."""
        async with session_factory() as s:
            await upsert(s, StockPrice, [price_row(stock_id, "2021-08-02", "113500")])
            await upsert(s, StockPrice, [price_row(stock_id, "2021-08-02", "114000")])
            await s.commit()
            row = (await s.execute(select(StockPrice))).scalar_one()
        assert row.open_raw == Decimal("114000.000000")

    async def test_최초_수집_시각이_정정으로_덮이지_않는다(
        self, session_factory, stock_id
    ) -> None:
        """`ingested_at`은 "언제 처음 들어왔나"다. 덮으면 그 정보가 사라진다."""
        async with session_factory() as s:
            await upsert(s, StockPrice, [price_row(stock_id, "2021-08-02", "113500")])
            await s.commit()
            first = (await s.execute(select(StockPrice))).scalar_one().ingested_at

        async with session_factory() as s:
            await upsert(s, StockPrice, [price_row(stock_id, "2021-08-02", "114000")])
            await s.commit()
            again = (await s.execute(select(StockPrice))).scalar_one().ingested_at
        assert again == first


class Test출처와_시각:
    async def test_시세에_출처와_받은_시각이_남는다(self, session_factory, stock_id) -> None:
        """FR-046 — 되짚을 수단이 이것뿐이다."""
        async with session_factory() as s:
            await upsert(s, StockPrice, [price_row(stock_id, "2021-08-02", "113500")])
            await s.commit()
            row = (await s.execute(select(StockPrice))).scalar_one()
        assert row.source == "yahoo:chart"
        assert row.ingested_at is not None

    async def test_배당에도_출처와_시각이_남는다(self, session_factory, stock_id) -> None:
        async with session_factory() as s:
            await upsert(s, StockDividend, [{
                "stock_id": stock_id, "ex_date": dt.date(2021, 12, 29),
                "amount_per_share": Decimal("1540"), "source": "yahoo:chart"}])
            await s.commit()
            row = (await s.execute(select(StockDividend))).scalar_one()
        assert row.source == "yahoo:chart"
        assert row.ingested_at is not None

    async def test_분할에도_출처와_시각이_남는다(self, session_factory, stock_id) -> None:
        """FR-010b — 제공처를 그대로 믿기로 한 이상 이 기록이 유일한 추적 수단이다."""
        async with session_factory() as s:
            await upsert(s, StockSplit, [{
                "stock_id": stock_id, "effective_date": dt.date(2018, 5, 4),
                "numerator": 50, "denominator": 1, "source": "yahoo:chart"}])
            await s.commit()
            row = (await s.execute(select(StockSplit))).scalar_one()
        assert (row.numerator, row.denominator) == (50, 1)
        assert row.source == "yahoo:chart"
        assert row.ingested_at is not None


class Test원주가와_수정주가:
    async def test_두_값이_따로_저장된다(self, session_factory, stock_id) -> None:
        """FR-012 — 섞으면 배당이 이중 계산되는데 차트가 매끄러워 신호가 없다."""
        async with session_factory() as s:
            await upsert(s, StockPrice, [{
                "stock_id": stock_id, "quote_date": dt.date(2021, 8, 2),
                "open_raw": Decimal("113500"), "close_raw": Decimal("113000"),
                "close_adjusted": Decimal("110000"), "source": "yahoo:chart"}])
            await s.commit()
            row = (await s.execute(select(StockPrice))).scalar_one()
        assert row.close_raw == Decimal("113000.000000")
        assert row.close_adjusted == Decimal("110000.000000")
        assert row.close_raw != row.close_adjusted

    async def test_수정주가가_없어도_저장된다(self, session_factory, stock_id) -> None:
        """출처가 주지 않는 경우가 있다. 원주가로 메우면 두 값이 같아져 구분이 사라진다."""
        async with session_factory() as s:
            await upsert(s, StockPrice, [{
                "stock_id": stock_id, "quote_date": dt.date(2021, 8, 2),
                "open_raw": Decimal("113500"), "close_raw": Decimal("113000"),
                "close_adjusted": None, "source": "yahoo:chart"}])
            await s.commit()
            row = (await s.execute(select(StockPrice))).scalar_one()
        assert row.close_adjusted is None
