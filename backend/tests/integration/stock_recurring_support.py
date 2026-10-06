"""주식 적립식 통합 테스트의 시드 (011 T015·T016) — `test_stock_sale_cost_api.py`(010 반복 4)와 같은
시세·환율이다.

거래일: 2026-01-02, 01-05, 02-02, 02-03, 03-03 / 2021-08-02, 08-03, 09-01, 09-02. 시가 = 50,000 +
1,500 × 순번(국내) · 200 + 7.25 × 순번(AAPL), 종가 = 시가 + 700 · + 2.4. USD 매매기준율은 2026-01-02
1,430.5 · 02-02 1,445.2 · 03-03 1,460.8 · 2021-08-02 1,150 · 09-01 1,160만 있다(다른 날은 가장
가까운 이전 고시일).
"""

from __future__ import annotations

import datetime as dt
from decimal import ROUND_FLOOR, Decimal

from httpx2 import ASGITransport, AsyncClient
from sqlalchemy import select

from src.api.main import create_app
from src.db.dialect import upsert
from src.db.models import FxCoverage, FxRate, Stock, StockCoverage, StockPrice
from src.db.session import get_session

D = dt.date.fromisoformat
WON = Decimal("1")

DAYS_2026 = ["2026-01-02", "2026-01-05", "2026-02-02", "2026-02-03", "2026-03-03"]
DAYS_2021 = ["2021-08-02", "2021-08-03", "2021-09-01", "2021-09-02"]
FX = {
    "2026-01-02": "1430.5",
    "2026-02-02": "1445.2",
    "2026-03-03": "1460.8",
    "2021-08-02": "1150",
    "2021-09-01": "1160",
}


def floor(x: Decimal) -> Decimal:
    return x.quantize(WON, rounding=ROUND_FLOOR)


def krx_price(day: str) -> tuple[Decimal, Decimal]:
    days = DAYS_2026 + DAYS_2021
    base = Decimal(50000 + 1500 * days.index(day))
    return base, base + Decimal("700")


def aapl_price(day: str) -> tuple[Decimal, Decimal]:
    days = DAYS_2026 + DAYS_2021
    base = Decimal("200") + Decimal(days.index(day)) * Decimal("7.25")
    return base, base + Decimal("2.4")


async def seed(session_factory) -> dict[str, int]:  # type: ignore[no-untyped-def]
    """두 종목의 시세·커버리지와 USD 환율·커버리지를 넣는다. 종목 기호 → id."""
    async with session_factory() as s:
        await upsert(s, Stock, [
            {"market": "KRX", "symbol": "005930.KS", "name": "삼성전자", "currency": "KRW",
             "first_available_date": D("1975-06-11")},
            {"market": "NASDAQ", "symbol": "AAPL", "name": "Apple Inc.", "currency": "USD",
             "first_available_date": D("1980-12-12")},
        ])
        await s.commit()
        ids = {r.symbol: int(r.id) for r in (await s.execute(select(Stock))).scalars()}
        rows = []
        for day in DAYS_2026 + DAYS_2021:
            for symbol, price in (("005930.KS", krx_price), ("AAPL", aapl_price)):
                open_, close = price(day)
                rows.append({"stock_id": ids[symbol], "quote_date": D(day), "open_raw": open_,
                             "close_raw": close, "close_adjusted": close, "source": "yahoo:chart"})
        await upsert(s, StockPrice, rows)
        await upsert(s, StockCoverage, [
            {"stock_id": sid, "covered_from": D("2021-08-01"), "covered_through": D("2026-03-31")}
            for sid in ids.values()], preserve=())
        await upsert(s, FxRate, [
            {"currency_code": "USD", "quote_date": D(d), "base_rate": Decimal(v), "quote_unit": 1,
             "source": "ECOS:731Y001", "is_provisional": False} for d, v in FX.items()])
        await upsert(s, FxCoverage, [
            {"currency_code": "USD", "covered_from": D("2021-07-01"),
             "covered_through": D("2026-03-31")}], preserve=())
        await s.commit()
    return ids


def app_for(session_factory):  # type: ignore[no-untyped-def]
    app = create_app()

    async def _override():  # type: ignore[no-untyped-def]
        async with session_factory() as s:
            yield s

    app.dependency_overrides[get_session] = _override
    return app


def client_for(app) -> AsyncClient:  # type: ignore[no-untyped-def]
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


KRX_MONTHLY = {
    "market": "KRX", "symbol": "005930.KS", "start": "2026-01-02", "amount": "1000000",
    "principalCurrency": "KRW", "frequency": "monthly", "reinvest": "true", "end": "2026-03-03",
}
AAPL_WEEKLY = {**KRX_MONTHLY, "market": "NASDAQ", "symbol": "AAPL", "amount": "500000",
               "frequency": "weekly"}
