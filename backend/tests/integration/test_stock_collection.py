"""주식 시세 수집 (T018) — 005 FR-043~046, SC-022, SC-023.

**스텁 소스를 쓰며 네트워크 없이 통과해야 한다** (헌법 원칙 III).

출처가 호출 한도를 공개하지 않으므로 낭비의 대가를 미리 알 수 없다. 이미 받은 구간을
다시 받지 않는 것이 FR-044의 요구다.
"""
from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest
from sqlalchemy import select

from src.db.dialect import upsert
from src.db.models import Stock, StockPrice, StockRawResponse
from src.ingestion.yahoo.parse import (
    ChartData,
    ChartFetch,
    DailyPrice,
    DividendEvent,
    RawBody,
    SplitEvent,
)
from src.repository.stock import get_coverage
from src.worker.stock_runner import collect_range

D = dt.date.fromisoformat


class StubSource:
    """시세 출처 스텁. 실제 HTTP를 발생시키지 않는다."""

    def __init__(self) -> None:
        self.requests: list[tuple[str, dt.date, dt.date]] = []
        self.raise_on_call: Exception | None = None
        self.raise_after: int = 0

    async def fetch_chart(
        self, symbol: str, date_from: dt.date, date_to: dt.date
    ) -> ChartFetch:
        self.requests.append((symbol, date_from, date_to))
        if self.raise_on_call is not None and len(self.requests) > self.raise_after:
            raise self.raise_on_call
        days, day = [], date_from
        while day <= date_to:
            if day.weekday() < 5:
                days.append(day)
            day += dt.timedelta(days=1)
        return ChartFetch(
            data=ChartData(
                currency="KRW",
                first_trade_date=D("1975-06-11"),
                prices=[DailyPrice(d, Decimal("1000"), Decimal("1010"), Decimal("990"))
                        for d in days],
                dividends=[DividendEvent(days[0], Decimal("300"))] if days else [],
                splits=[SplitEvent(days[0], 2, 1)] if days else [],
            ),
            # 006 — 한 번 받을 때 원본이 둘이다: 청크와, 원주가를 되살리는 데 쓴 분할 기록.
            raws=[RawBody("chart", '{"chunk": true}', 200, date_from, date_to),
                  RawBody("splits", '{"splits": true}', 200, date_from, D("2026-10-03"))],
        )

    async def delay_between_chunks(self) -> None:
        return None


@pytest.fixture
async def stock_id(session_factory) -> int:
    async with session_factory() as s:
        await upsert(s, Stock, [{
            "market": "KRX", "symbol": "005930.KS", "name": "삼성전자",
            "currency": "KRW"}])
        await s.commit()
        return int((await s.execute(select(Stock))).scalar_one().id)


class Test요청_구간만_받는다:
    async def test_요청한_구간만_호출한다(self, session_factory, stock_id) -> None:
        """FR-043 — 종목 전체 이력을 미리 받지 않는다."""
        source = StubSource()
        async with session_factory() as s:
            await collect_range(s, source, stock_id, "005930.KS",
                                D("2021-01-01"), D("2021-03-31"))
            await s.commit()
        assert source.requests[0][1] == D("2021-01-01")
        assert source.requests[-1][2] == D("2021-03-31")

    async def test_받은_구간이_커버리지에_남는다(self, session_factory, stock_id) -> None:
        source = StubSource()
        async with session_factory() as s:
            await collect_range(s, source, stock_id, "005930.KS",
                                D("2021-01-01"), D("2021-03-31"))
            await s.commit()
            assert await get_coverage(s, stock_id) == (D("2021-01-01"), D("2021-03-31"))

    async def test_시세가_저장된다(self, session_factory, stock_id) -> None:
        source = StubSource()
        async with session_factory() as s:
            await collect_range(s, source, stock_id, "005930.KS",
                                D("2021-01-04"), D("2021-01-08"))
            await s.commit()
            rows = (await s.execute(select(StockPrice))).scalars().all()
        assert len(rows) == 5  # 그 주의 평일


class Test재수집_방지:
    async def test_이미_받은_구간은_다시_받지_않는다(
        self, session_factory, stock_id
    ) -> None:
        """FR-044, SC-022 — 출처 호출을 낭비하지 않는다."""
        source = StubSource()
        async with session_factory() as s:
            await collect_range(s, source, stock_id, "005930.KS",
                                D("2021-01-01"), D("2021-03-31"))
            await s.commit()
        first_count = len(source.requests)

        async with session_factory() as s:
            await collect_range(s, source, stock_id, "005930.KS",
                                D("2021-01-01"), D("2021-03-31"))
            await s.commit()
        assert len(source.requests) == first_count, "같은 구간을 다시 받았다"

    async def test_빠진_구간만_받는다(self, session_factory, stock_id) -> None:
        source = StubSource()
        async with session_factory() as s:
            await collect_range(s, source, stock_id, "005930.KS",
                                D("2021-06-01"), D("2021-06-30"))
            await s.commit()
        source.requests.clear()

        async with session_factory() as s:
            await collect_range(s, source, stock_id, "005930.KS",
                                D("2021-01-01"), D("2021-12-31"))
            await s.commit()

        asked = [(f, t) for _, f, t in source.requests]
        # 6월은 이미 받았으므로 요청에 들어가면 안 된다.
        assert not any(f <= D("2021-06-15") <= t for f, t in asked), \
            f"이미 받은 6월을 다시 요청했다: {asked}"


class Test중단과_재개:
    async def test_중단되면_받은_데까지_커버리지가_남는다(
        self, session_factory, stock_id
    ) -> None:
        """FR-045, SC-023 — 처음부터 다시 받으면 구간이 길수록 끝나지 않는다."""
        source = StubSource()
        source.raise_on_call = RuntimeError("출처 장애")
        source.raise_after = 1  # 첫 청크만 성공

        async with session_factory() as s:
            with pytest.raises(RuntimeError):
                await collect_range(s, source, stock_id, "005930.KS",
                                    D("2020-01-01"), D("2022-12-31"))
            await s.commit()
            covered = await get_coverage(s, stock_id)

        assert covered is not None, "중단 지점까지의 커버리지가 남지 않았다"
        assert covered[0] == D("2020-01-01")
        assert covered[1] < D("2022-12-31")

    async def test_재개하면_중단_지점부터_받는다(self, session_factory, stock_id) -> None:
        source = StubSource()
        source.raise_on_call = RuntimeError("출처 장애")
        source.raise_after = 1

        async with session_factory() as s:
            with pytest.raises(RuntimeError):
                await collect_range(s, source, stock_id, "005930.KS",
                                    D("2020-01-01"), D("2022-12-31"))
            await s.commit()
            covered = await get_coverage(s, stock_id)
        assert covered is not None
        resume_from = covered[1]

        healthy = StubSource()
        async with session_factory() as s:
            await collect_range(s, healthy, stock_id, "005930.KS",
                                D("2020-01-01"), D("2022-12-31"))
            await s.commit()

        assert healthy.requests[0][1] > resume_from, \
            f"처음부터 다시 받았다: {healthy.requests[0]}"


class Test값을_만들어내지_않는다:
    async def test_주말에는_행이_생기지_않는다(self, session_factory, stock_id) -> None:
        """헌법 원칙 V — 휴장일을 값으로 메우지 않는다."""
        source = StubSource()
        async with session_factory() as s:
            await collect_range(s, source, stock_id, "005930.KS",
                                D("2021-01-04"), D("2021-01-10"))
            await s.commit()
            dates = {r.quote_date for r in (
                await s.execute(select(StockPrice))).scalars()}
        assert D("2021-01-09") not in dates  # 토
        assert D("2021-01-10") not in dates  # 일


class Test원본을_모두_남긴다:
    """006 T106 — FR-034, research R6-18, 헌법 시계열 불변식(원본과 정규화의 분리 저장).

    출처가 한 번에 원본을 둘 준다 — 청크와, 원주가를 되살리는 데 쓴 분할 기록. 분할 기록을 버리면
    되살린 값이 틀렸을 때 무엇으로 계산했는지 되짚을 수 없다.
    """

    async def test_청크와_분할_기록의_원본이_남는다(self, session_factory, stock_id) -> None:
        source = StubSource()
        async with session_factory() as s:
            await collect_range(s, source, stock_id, "005930.KS",
                                D("2021-01-01"), D("2021-03-31"))
            await s.commit()
        async with session_factory() as s:
            rows = (await s.execute(
                select(StockRawResponse).order_by(StockRawResponse.id))).scalars().all()
        assert [(r.stock_id, r.kind, r.body, r.status_code, r.requested_from, r.requested_to)
                for r in rows] == [
            (stock_id, "chart", '{"chunk": true}', 200, D("2021-01-01"), D("2021-03-31")),
            (stock_id, "splits", '{"splits": true}', 200, D("2021-01-01"), D("2026-10-03")),
        ]
