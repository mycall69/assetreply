"""비교 경로 테스트의 고정 데이터 (013 T010·T011·T043).

메뉴 경로와 비교 경로를 **같은 데이터·같은 질의**로 불러 견준다. 주식은 국내(KRX `005930.KS`)·해외
(NASDAQ `AAPL`)에 배당 재투자가 한 번 있고, 환율이 날마다 다르다(`test_sale_gain_breakdown_api`와
같은 꼴). 가상자산·예금·부동산은 각 메뉴 테스트의 도우미(`crypto_support`·`deposit_support`·
`test_realestate_simulation_api.Api`)를 그대로 쓴다.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from decimal import Decimal

from httpx2 import ASGITransport, AsyncClient
from sqlalchemy import func, select

from src.api.main import create_app
from src.db.dialect import upsert
from src.db.models import (
    FxCoverage,
    FxRate,
    SimulationHistory,
    Stock,
    StockCoverage,
    StockDividend,
    StockPrice,
)
from src.db.session import get_session

D = dt.date.fromisoformat

#: 2021-09-01(수) 배당락 → 09-03(금)이 둘째 거래일(재투자). 10-01에 주가가 오른다.
PRICE = {"2021-08-02": "100", "2021-09-01": "100", "2021-09-02": "100", "2021-09-03": "100",
         "2021-10-01": "110"}
USD_FX = {"2021-08-02": "1150", "2021-09-01": "1160", "2021-09-02": "1165", "2021-09-03": "1170",
          "2021-10-01": "1190"}

BASE = {"start": "2021-08-01", "end": "2021-10-31", "reinvest": "true"}
KRX = {**BASE, "market": "KRX", "symbol": "005930.KS", "principal": "10000000",
       "principalCurrency": "KRW"}
AAPL_USD = {**BASE, "market": "NASDAQ", "symbol": "AAPL", "principal": "10000",
            "principalCurrency": "USD"}
AAPL_KRW = {**BASE, "market": "NASDAQ", "symbol": "AAPL", "principal": "10000000",
            "principalCurrency": "KRW"}
#: 시세 시작일이 시작일보다 늦은 종목 — `before_listing`(price_start).
NEWCO = {**BASE, "market": "KRX", "symbol": "000660.KS", "principal": "10000000",
         "principalCurrency": "KRW"}
#: 받지 않은 종목 — 202.
EMPTY = {**BASE, "market": "KRX", "symbol": "035420.KS", "principal": "10000000",
         "principalCurrency": "KRW"}


async def seed_stocks(session_factory) -> dict[str, int]:  # type: ignore[no-untyped-def]
    async with session_factory() as s:
        await upsert(s, Stock, [
            {"market": "NASDAQ", "symbol": "AAPL", "name": "Apple Inc.", "currency": "USD",
             "first_available_date": D("1980-12-12")},
            {"market": "KRX", "symbol": "005930.KS", "name": "삼성전자", "currency": "KRW",
             "first_available_date": D("1975-06-11")},
            {"market": "KRX", "symbol": "000660.KS", "name": "SK하이닉스", "currency": "KRW",
             "first_available_date": D("2021-09-15")},
            {"market": "KRX", "symbol": "035420.KS", "name": "NAVER", "currency": "KRW",
             "first_available_date": D("2002-10-29")},
        ])
        await s.commit()
        ids = {r.symbol: int(r.id) for r in (await s.execute(select(Stock))).scalars()}
        for symbol, scale in (("AAPL", Decimal("1")), ("005930.KS", Decimal("700"))):
            await upsert(s, StockPrice, [
                {"stock_id": ids[symbol], "quote_date": D(d), "open_raw": Decimal(v) * scale,
                 "close_raw": Decimal(v) * scale, "close_adjusted": Decimal(v) * scale,
                 "source": "yahoo:chart"} for d, v in PRICE.items()])
            await upsert(s, StockDividend, [
                {"stock_id": ids[symbol], "ex_date": D("2021-09-01"),
                 "amount_per_share": Decimal("10") * scale, "source": "yahoo:chart"}])
            await upsert(s, StockCoverage, [
                {"stock_id": ids[symbol], "covered_from": D("2021-08-01"),
                 "covered_through": D("2021-10-31")}], preserve=())
        await upsert(s, FxRate, [
            {"currency_code": "USD", "quote_date": D(d), "base_rate": Decimal(v), "quote_unit": 1,
             "source": "ECOS:731Y001", "is_provisional": False} for d, v in USD_FX.items()])
        await upsert(s, FxCoverage, [
            {"currency_code": "USD", "covered_from": D("2021-07-01"),
             "covered_through": D("2021-10-31")}], preserve=())
        await s.commit()
    return ids


@asynccontextmanager
async def http(session_factory) -> AsyncIterator[AsyncClient]:  # type: ignore[no-untyped-def]
    app = create_app()

    async def _session():  # type: ignore[no-untyped-def]
        async with session_factory() as s:
            yield s

    app.dependency_overrides[get_session] = _session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


async def history_rows(session_factory) -> int:  # type: ignore[no-untyped-def]
    async with session_factory() as s:
        return int((await s.execute(select(func.count()).select_from(SimulationHistory)))
                   .scalar_one())


async def both(client: AsyncClient, menu: str, params: dict[str, str]):  # type: ignore[no-untyped-def]
    """같은 질의로 메뉴 표 경로·메뉴 시계열(1000점)·비교 경로를 부른다."""
    table = await client.get(menu, params=params)
    series = await client.get(f"{menu}/series", params={**params, "maxPoints": "1000"})
    compare = await client.get(f"/api/comparison{menu.removeprefix('/api')}", params=params)
    return table, series, compare
