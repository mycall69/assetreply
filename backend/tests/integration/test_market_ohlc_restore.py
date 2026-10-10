"""시가·고가·저가를 원본에서 되살린다 (014 반복 2026-10-10b T098) — FR-017, FR-019, SC-014,
research R14-18.

열이 생기기 전에 넣은 일봉(시가·고가·저가가 빔)을 **저장해 둔 원본 응답에서** 채운다 — 다시 받지
않는다(원칙 V의 원본 분리 저장). 출처 픽스처는 실측 본문이다(네트워크 없음).

- 원본의 같은 날 값(소수 6자리)이다. 두 번 돌려도 같다
- 같은 날이 원본 여럿에 있으면 가장 늦게 받은 원본이다
- 원본에 없는 날·0은 비운 채다. 종가·개정 표는 바뀌지 않는다
- 워커는 첫 바퀴 앞에 한 번 되살린다
"""

from __future__ import annotations

import datetime as dt
import inspect
import json
from decimal import Decimal
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.db.models import MarketCloseRevision
from src.ingestion.yahoo.market_parse import load, parse_daily
from src.repository import market_daily
from src.worker import market_runner, market_worker

FIX = Path(__file__).parents[1] / "contract" / "fixtures" / "market"
D = dt.date
AT = dt.datetime(2026, 10, 9, 5, 0, 0)
SIX = Decimal("0.000001")


def raw_text() -> str:
    return (FIX / "chart_KS11_2024_2025.json").read_text(encoding="utf-8")


def bars_of(raw: str) -> dict[dt.date, tuple[Decimal, Decimal, Decimal]]:
    """시험이 직접 읽는 원본 값 — 어댑터와 따로 계산한다."""
    from zoneinfo import ZoneInfo

    result = json.loads(raw, parse_float=Decimal)["chart"]["result"][0]
    zone = ZoneInfo(result["meta"]["exchangeTimezoneName"])
    quote = result["indicators"]["quote"][0]
    out = {}
    for i, stamp in enumerate(result["timestamp"]):
        if quote["close"][i] is None:
            continue
        day = dt.datetime.fromtimestamp(stamp, zone).date()
        out[day] = tuple(quote[k][i].quantize(SIX) for k in ("open", "high", "low"))
    return out


async def seed(
    factory: async_sessionmaker[AsyncSession], raw: str, *, received: dt.datetime = AT
) -> list[tuple[dt.date, Decimal]]:
    closes = parse_daily(load(raw), current_date=D(2026, 10, 9)).closes
    async with factory() as s:
        await market_daily.store_closes(s, "kospi", closes, detected_at=AT)
        await market_daily.store_raw(
            s,
            "kospi",
            requested_from=D(2024, 1, 1),
            requested_to=D(2025, 12, 31),
            status_code=200,
            body=raw,
            received_at=received,
        )
        await s.commit()
    return closes


async def test_원본의_같은_날_값으로_채운다(session_factory) -> None:  # type: ignore[no-untyped-def]
    raw = raw_text()
    closes = await seed(session_factory, raw)
    filled = await market_runner.restore_ohlc(session_factory)
    assert filled == {"kospi": len(closes)}
    expected = bars_of(raw)
    async with session_factory() as s:
        bars = await market_daily.bars(s, "kospi")
    assert len(bars) == len(closes)
    for bar in bars:
        assert (bar.open, bar.high, bar.low) == expected[bar.date]
    assert bars[0].open == Decimal("2645.469971")


async def test_다시_돌려도_같다(session_factory) -> None:  # type: ignore[no-untyped-def]
    await seed(session_factory, raw_text())
    await market_runner.restore_ohlc(session_factory)
    assert await market_runner.restore_ohlc(session_factory) == {}


async def test_원본이_여럿이면_늦게_받은_것이다(session_factory) -> None:  # type: ignore[no-untyped-def]
    raw = raw_text()
    await seed(session_factory, raw)
    body = json.loads(raw)
    body["chart"]["result"][0]["indicators"]["quote"][0]["open"][0] = 1234.5
    async with session_factory() as s:
        await market_daily.store_raw(
            s,
            "kospi",
            requested_from=D(2024, 1, 1),
            requested_to=D(2024, 1, 31),
            status_code=200,
            body=json.dumps(body),
            received_at=AT + dt.timedelta(days=1),
        )
        await s.commit()
    await market_runner.restore_ohlc(session_factory)
    async with session_factory() as s:
        first = (await market_daily.bars(s, "kospi", D(2024, 1, 2), D(2024, 1, 2)))[0]
    assert first.open == Decimal("1234.500000")


async def test_원본에_없는_날과_0은_비운다(session_factory) -> None:  # type: ignore[no-untyped-def]
    body = json.loads(raw_text())
    body["chart"]["result"][0]["indicators"]["quote"][0]["open"][0] = 0
    await seed(session_factory, json.dumps(body))
    async with session_factory() as s:
        await market_daily.store_closes(
            s, "kospi", [(D(2026, 1, 2), Decimal("4300"))], detected_at=AT
        )
        await s.commit()
    await market_runner.restore_ohlc(session_factory)
    async with session_factory() as s:
        jan2 = (await market_daily.bars(s, "kospi", D(2024, 1, 2), D(2024, 1, 2)))[0]
        outside = (await market_daily.bars(s, "kospi", D(2026, 1, 2), D(2026, 1, 2)))[0]
    assert jan2.open is None and jan2.high is not None
    assert (outside.open, outside.high, outside.low) == (None, None, None)


async def test_종가와_개정은_그대로다(session_factory) -> None:  # type: ignore[no-untyped-def]
    closes = await seed(session_factory, raw_text())
    await market_runner.restore_ohlc(session_factory)
    async with session_factory() as s:
        assert await market_daily.closes(s, "kospi") == [(d, v) for d, v in closes]
        revisions = (
            await s.execute(select(func.count()).select_from(MarketCloseRevision))
        ).scalar_one()
    assert revisions == 0


def test_워커는_첫_바퀴_앞에_되살린다() -> None:
    body = inspect.getsource(market_worker.market_worker_loop)
    assert "restore_ohlc(" in body
    assert body.index("restore_ohlc(") < body.index("run_round(")
