"""계산 끝이 휴장일·주말일 때의 기준일 (버그 stock-holiday-stale-warning) — 005 FR-014a·FR-014b,
SC-027.

2026-10-06(화)에 국내 종목을 실행하면 계산 끝(어제)은 10-05(월, 개천절 대체공휴일)다. 커버리지는
10-05까지이고 일봉은 10-02(금)에서 끝난다 — 받을 시세가 빠진 것이 아니다. 보드·표가 "⚠ 2026-10-02
이후 시세가 없습니다"를 띄우면 안 된다(`isFinal true`).

- 같은 시장의 다른 종목이 10-05에 거래했으면 그 종목만 끊긴 것이다 — 지금처럼 `isFinal false`다
- 일시금(`/api/stocks/simulation`)과 적립식(`/api/stocks/recurring-simulation`)이 같은 판정이다
- 시세 단절(`test_delisted.py` — 평일 수십 일)은 그대로 `isFinal false`다
"""
from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest
from httpx2 import ASGITransport, AsyncClient
from sqlalchemy import select

from src.api.main import create_app
from src.db.dialect import upsert
from src.db.models import Stock, StockCoverage, StockPrice
from src.db.session import get_session

D = dt.date.fromisoformat
DAYS = ["2026-10-01", "2026-10-02"]
SYMBOLS = ("111111.KS", "222222.KS")


async def seed(session_factory, *, extra: dict[str, list[str]] | None = None) -> None:  # type: ignore[no-untyped-def]
    """두 국내 종목 — 10-01·10-02 일봉, 커버리지 09-01 ~ 10-05. `extra`는 종목별로 더할 일봉
    날짜다."""
    async with session_factory() as s:
        await upsert(s, Stock, [{
            "market": "KRX", "symbol": sym, "name": f"종목{n}", "currency": "KRW",
            "first_available_date": D("2010-01-04")} for n, sym in enumerate(SYMBOLS)])
        await s.commit()
        ids = {st.symbol: int(st.id) for st in (await s.execute(select(Stock))).scalars()}
        rows = []
        for sym in SYMBOLS:
            for day in [*DAYS, *(extra or {}).get(sym, [])]:
                price = Decimal("50000")
                rows.append({"stock_id": ids[sym], "quote_date": D(day), "open_raw": price,
                             "close_raw": price + 500, "close_adjusted": price + 500,
                             "source": "yahoo:chart"})
        await upsert(s, StockPrice, rows)
        await upsert(s, StockCoverage, [{
            "stock_id": ids[sym], "covered_from": D("2026-09-01"),
            "covered_through": D("2026-10-05")} for sym in SYMBOLS], preserve=())
        await s.commit()


@pytest.fixture
async def client(session_factory):  # type: ignore[no-untyped-def]
    app = create_app()

    async def _override():  # type: ignore[no-untyped-def]
        async with session_factory() as s:
            yield s

    app.dependency_overrides[get_session] = _override
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


async def lump(client: AsyncClient, symbol: str, end: str) -> dict:  # type: ignore[type-arg]
    response = await client.get("/api/stocks/simulation", params={
        "market": "KRX", "symbol": symbol, "start": "2026-10-01", "principal": "1000000",
        "principalCurrency": "KRW", "reinvest": "true", "end": end})
    assert response.status_code == 200, response.text
    return response.json()["summary"]  # type: ignore[no-any-return]


async def test_계산_끝이_대체공휴일이면_최종이다(session_factory, client) -> None:  # type: ignore[no-untyped-def]
    await seed(session_factory)
    summary = await lump(client, SYMBOLS[0], "2026-10-05")
    assert (summary["asOf"], summary["isFinal"]) == ("2026-10-02", True)


async def test_계산_끝이_주말이면_최종이다(session_factory, client) -> None:  # type: ignore[no-untyped-def]
    await seed(session_factory)
    summary = await lump(client, SYMBOLS[0], "2026-10-04")
    assert (summary["asOf"], summary["isFinal"]) == ("2026-10-02", True)


async def test_같은_시장의_다른_종목이_거래한_날이_있으면_단절이다(  # type: ignore[no-untyped-def]
        session_factory, client) -> None:
    """10-05에 222222만 거래했다 — 111111만 끊긴 것이다(거래정지·상장폐지)."""
    await seed(session_factory, extra={SYMBOLS[1]: ["2026-10-05"]})
    halted = await lump(client, SYMBOLS[0], "2026-10-05")
    trading = await lump(client, SYMBOLS[1], "2026-10-05")
    assert (halted["asOf"], halted["isFinal"]) == ("2026-10-02", False)
    assert (trading["asOf"], trading["isFinal"]) == ("2026-10-05", True)


async def test_적립식도_같은_판정이다(session_factory, client) -> None:  # type: ignore[no-untyped-def]
    await seed(session_factory)
    response = await client.get("/api/stocks/recurring-simulation", params={
        "market": "KRX", "symbol": SYMBOLS[0], "start": "2026-10-01", "amount": "100000",
        "principalCurrency": "KRW", "frequency": "daily", "reinvest": "true", "end": "2026-10-05"})
    assert response.status_code == 200, response.text
    summary = response.json()["summary"]
    assert (summary["asOf"], summary["isFinal"]) == ("2026-10-02", True)
