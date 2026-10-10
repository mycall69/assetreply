"""대시보드 지표 저장소 (014 T010) — FR-005, FR-017, FR-019, SC-003, SC-006, data-model 1, 헌법 원칙
V.

- 종가는 **없는 날만 넣는다**. 있는 날의 값이 출처에서 바뀌었으면 덮어쓰지 않고 개정 한 줄을 남긴다
  — 확정 값의 재현성(원칙 V)
- 커버리지는 **요청한 범위**다 — 받은 범위만 늘어난다(FR-019)
- 카드의 전일 종가는 저장된 이력에서 읽는다(FR-005)
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.db.models import MarketCloseRevision, MarketIndicatorDaily, MarketIndicatorRaw
from src.repository import market_daily

D = dt.date
AT = dt.datetime(2026, 10, 9, 5, 0, 0)


def _closes(*pairs: tuple[str, str]) -> list[tuple[dt.date, Decimal]]:
    return [(D.fromisoformat(d), Decimal(v)) for d, v in pairs]


async def _count(session: AsyncSession, model: type) -> int:
    return int((await session.execute(select(func.count()).select_from(model))).scalar_one())


async def test_없는_날만_넣는다(session_factory: async_sessionmaker[AsyncSession]) -> None:
    async with session_factory() as s:
        first = await market_daily.store_closes(
            s, "kospi", _closes(("2026-10-06", "6700.5"), ("2026-10-07", "6803.9")), detected_at=AT
        )
        await s.commit()
        again = await market_daily.store_closes(
            s,
            "kospi",
            _closes(("2026-10-07", "6803.900000"), ("2026-10-08", "6625.93")),
            detected_at=AT,
        )
        await s.commit()
        assert (first.inserted, again.inserted) == (2, 1)
        assert again.revisions == []
        assert await market_daily.closes(s, "kospi") == _closes(
            ("2026-10-06", "6700.500000"),
            ("2026-10-07", "6803.900000"),
            ("2026-10-08", "6625.930000"),
        )
        row = await s.get(MarketIndicatorDaily, ("kospi", D(2026, 10, 7)))
        assert row is not None and row.source == "yahoo:chart"


async def test_바뀐_확정_값은_덮어쓰지_않고_개정을_남긴다(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as s:
        await market_daily.store_closes(
            s, "dow", _closes(("2026-10-07", "46000.10")), detected_at=AT
        )
        await s.commit()
        result = await market_daily.store_closes(
            s, "dow", _closes(("2026-10-07", "46000.25")), detected_at=AT
        )
        await s.commit()
        assert result.inserted == 0
        assert [(r.trade_date, r.stored_close, r.source_close) for r in result.revisions] == [
            (D(2026, 10, 7), Decimal("46000.100000"), Decimal("46000.250000"))
        ]
        # 같은 개정을 다시 받아도 한 줄이다
        twice = await market_daily.store_closes(
            s, "dow", _closes(("2026-10-07", "46000.25")), detected_at=AT
        )
        await s.commit()
        assert twice.revisions == []
        assert await _count(s, MarketCloseRevision) == 1
        assert await market_daily.closes(s, "dow") == _closes(("2026-10-07", "46000.100000"))


async def test_원본을_그대로_넣는다(session_factory: async_sessionmaker[AsyncSession]) -> None:
    async with session_factory() as s:
        await market_daily.store_raw(
            s,
            "wti",
            requested_from=D(2020, 1, 1),
            requested_to=D(2021, 12, 31),
            status_code=200,
            body='{"chart": {}}',
            received_at=AT,
        )
        await s.commit()
        row = (await s.execute(select(MarketIndicatorRaw))).scalar_one()
        assert (row.indicator_id, row.body, row.status_code) == ("wti", '{"chart": {}}', 200)


async def test_커버리지는_요청_범위를_합친다(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as s:
        assert await market_daily.get_coverage(s, "sp500") is None
        await market_daily.record_coverage(s, "sp500", D(2024, 10, 9), D(2026, 10, 8))
        await market_daily.record_coverage(s, "sp500", D(2022, 10, 10), D(2024, 10, 8))
        await market_daily.record_first_day(s, "sp500", D(1927, 12, 30))
        await s.commit()
        cov = await market_daily.get_coverage(s, "sp500")
        assert cov is not None
        assert (cov.covered_from, cov.covered_through, cov.first_day) == (
            D(2022, 10, 10),
            D(2026, 10, 8),
            D(1927, 12, 30),
        )
        assert await market_daily.coverage_reaches(s, "sp500", D(2026, 10, 8))
        assert not await market_daily.coverage_reaches(s, "sp500", D(2026, 10, 9))
        assert not await market_daily.coverage_reaches(s, "nasdaq", D(2026, 10, 1))


async def test_성공과_실패를_기록한다(session_factory: async_sessionmaker[AsyncSession]) -> None:
    async with session_factory() as s:
        await market_daily.record_failure(
            s, "vix", at=AT, kind="rate_limited", message="한도" * 400
        )
        await s.commit()
        cov = await market_daily.get_coverage(s, "vix")
        assert cov is not None
        assert (cov.last_failure_kind, cov.last_failure_at, cov.covered_from) == (
            "rate_limited",
            AT,
            None,
        )
        assert cov.last_failure_message is not None and len(cov.last_failure_message) == 500
        later = AT + dt.timedelta(minutes=30)
        await market_daily.record_success(s, "vix", at=later)
        await s.commit()
        cov = await market_daily.get_coverage(s, "vix")
        assert cov is not None and cov.last_success_at == later
        # 실패 기록은 남는다 — 화면은 시각을 견줘 "성공 뒤의 실패"만 보인다(FR-019)
        assert cov.last_failure_at == AT


async def test_이력의_전일_종가와_구간(session_factory: async_sessionmaker[AsyncSession]) -> None:
    async with session_factory() as s:
        await market_daily.store_closes(
            s,
            "kospi",
            _closes(("2026-10-05", "6650"), ("2026-10-07", "6803.9"), ("2026-10-08", "6625.93")),
            detected_at=AT,
        )
        await s.commit()
        assert await market_daily.previous_close(s, "kospi", D(2026, 10, 8)) == (
            D(2026, 10, 7),
            Decimal("6803.900000"),
        )
        assert await market_daily.previous_close(s, "kospi", D(2026, 10, 7)) == (
            D(2026, 10, 5),
            Decimal("6650.000000"),
        )
        assert await market_daily.previous_close(s, "kospi", D(2026, 10, 5)) is None
        assert await market_daily.closes(s, "kospi", D(2026, 10, 6), D(2026, 10, 8)) == _closes(
            ("2026-10-07", "6803.900000"), ("2026-10-08", "6625.930000")
        )
        assert await market_daily.closes(s, "kosdaq") == []


# 반복 2026-10-10b(T097) — 시가·고가·저가. 종가와 같은 불변식이다: 새 날만 넣고 덮지 않는다(spec
# FR-017).
OHLC = {D(2026, 10, 7): (Decimal("6700"), Decimal("6810.5"), Decimal("6690"))}


async def test_시가_고가_저가는_새_날에만_넣고_덮지_않는다(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as s:
        await market_daily.store_closes(
            s, "kospi", _closes(("2026-10-07", "6803.9")), detected_at=AT, ohlc=OHLC
        )
        await s.commit()
        other = {D(2026, 10, 7): (Decimal("1"), Decimal("2"), Decimal("3"))}
        again = await market_daily.store_closes(
            s, "kospi", _closes(("2026-10-07", "6803.9")), detected_at=AT, ohlc=other
        )
        await s.commit()
        assert again.inserted == 0
        assert await market_daily.bars(s, "kospi") == [
            market_daily.Bar(
                D(2026, 10, 7),
                Decimal("6700.000000"),
                Decimal("6810.500000"),
                Decimal("6690.000000"),
                Decimal("6803.900000"),
            )
        ]


async def test_시가가_없으면_비운다(session_factory: async_sessionmaker[AsyncSession]) -> None:
    async with session_factory() as s:
        await market_daily.store_closes(
            s, "kospi", _closes(("2026-10-06", "6700.5")), detected_at=AT
        )
        await s.commit()
        (bar,) = await market_daily.bars(s, "kospi")
        assert (bar.open, bar.high, bar.low) == (None, None, None)


async def test_채우기는_비운_날만이고_다시_해도_같다(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as s:
        await market_daily.store_closes(
            s, "kospi", _closes(("2026-10-06", "6700.5")), detected_at=AT
        )
        await market_daily.store_closes(
            s, "kospi", _closes(("2026-10-07", "6803.9")), detected_at=AT, ohlc=OHLC
        )
        await s.commit()
        values = {
            D(2026, 10, 6): (Decimal("6650"), Decimal("6720"), Decimal("6640")),
            D(2026, 10, 7): (Decimal("9"), Decimal("9"), Decimal("9")),
        }
        assert await market_daily.fill_ohlc(s, "kospi", values) == 1
        await s.commit()
        assert await market_daily.fill_ohlc(s, "kospi", values) == 0
        await s.commit()
        bars = {b.date: b for b in await market_daily.bars(s, "kospi")}
        assert bars[D(2026, 10, 6)].open == Decimal("6650.000000")
        assert bars[D(2026, 10, 7)].open == Decimal("6700.000000")  # 있는 날은 덮지 않는다


async def test_원본_본문은_받은_차례다(session_factory: async_sessionmaker[AsyncSession]) -> None:
    async with session_factory() as s:
        for body, at in (("늦게", AT + dt.timedelta(hours=1)), ("먼저", AT)):
            await market_daily.store_raw(
                s,
                "kospi",
                requested_from=D(2026, 10, 1),
                requested_to=D(2026, 10, 8),
                status_code=200,
                body=body,
                received_at=at,
            )
        await s.commit()
        assert await market_daily.raw_bodies(s, "kospi") == ["먼저", "늦게"]


async def test_구간의_일봉(session_factory: async_sessionmaker[AsyncSession]) -> None:
    async with session_factory() as s:
        await market_daily.store_closes(
            s,
            "kospi",
            _closes(("2026-10-05", "1"), ("2026-10-06", "2"), ("2026-10-07", "3")),
            detected_at=AT,
        )
        await s.commit()
        bars = await market_daily.bars(s, "kospi", D(2026, 10, 6), D(2026, 10, 7))
        assert [b.date for b in bars] == [D(2026, 10, 6), D(2026, 10, 7)]

