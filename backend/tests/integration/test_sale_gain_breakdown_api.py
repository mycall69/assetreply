"""해외 주식 매도 비용의 양도차익 구성 — 경로 (012 T079) — FR-019, SC-011, data-model 4.2,
contracts/rest-api.md 1.2.

- 주식 일시금·적립식 표 경로의 `summary.saleCost`에 `saleKrw`·`acquisitionKrw`·`feesKrw`가 있다.
  `saleKrw − acquisitionKrw − feesKrw = gain`(0원 차이)
- 취득가는 **모든 매수**(처음 매수·배당 재투자)의 `boughtShares × openPrice × fxRate` 합이다 —
  2026-10-07 보고(XLK)에서 차이의 대부분이 재투자 매수의 취득가였다
- 매도금액은 보유 주식만이다(예수금 제외) — 기준일 행 `balance × fxRate`의 원 미만 버림
- 국내 종목은 셋 모두 `null`이다
"""

from __future__ import annotations

import datetime as dt
from decimal import ROUND_FLOOR, Decimal

import pytest
from httpx2 import ASGITransport, AsyncClient
from sqlalchemy import select

from src.api.main import create_app
from src.db.dialect import upsert
from src.db.models import FxCoverage, FxRate, Stock, StockCoverage, StockDividend, StockPrice
from src.db.session import get_session

D = dt.date.fromisoformat
#: 2021-09-01(수) 배당락 → 09-03(금)이 둘째 거래일(재투자). 10-01에 주가가 오른다.
PRICE = {
    "2021-08-02": "100",
    "2021-09-01": "100",
    "2021-09-02": "100",
    "2021-09-03": "100",
    "2021-10-01": "110",
}
USD_FX = {
    "2021-08-02": "1150",
    "2021-09-01": "1160",
    "2021-09-02": "1165",
    "2021-09-03": "1170",
    "2021-10-01": "1190",
}


def floor(x: Decimal) -> Decimal:
    return x.quantize(Decimal("1"), rounding=ROUND_FLOOR)


@pytest.fixture
async def client(session_factory):  # type: ignore[no-untyped-def]
    async with session_factory() as s:
        await upsert(
            s,
            Stock,
            [
                {
                    "market": "NASDAQ",
                    "symbol": "AAPL",
                    "name": "Apple Inc.",
                    "currency": "USD",
                    "first_available_date": D("1980-12-12"),
                },
                {
                    "market": "KRX",
                    "symbol": "005930.KS",
                    "name": "삼성전자",
                    "currency": "KRW",
                    "first_available_date": D("1975-06-11"),
                },
            ],
        )
        await s.commit()
        ids = {r.symbol: int(r.id) for r in (await s.execute(select(Stock))).scalars()}
        for symbol, scale in (("AAPL", Decimal("1")), ("005930.KS", Decimal("700"))):
            await upsert(
                s,
                StockPrice,
                [
                    {
                        "stock_id": ids[symbol],
                        "quote_date": D(d),
                        "open_raw": Decimal(v) * scale,
                        "close_raw": Decimal(v) * scale,
                        "close_adjusted": Decimal(v) * scale,
                        "source": "yahoo:chart",
                    }
                    for d, v in PRICE.items()
                ],
            )
            await upsert(
                s,
                StockDividend,
                [
                    {
                        "stock_id": ids[symbol],
                        "ex_date": D("2021-09-01"),
                        "amount_per_share": Decimal("10") * scale,
                        "source": "yahoo:chart",
                    }
                ],
            )
            await upsert(
                s,
                StockCoverage,
                [
                    {
                        "stock_id": ids[symbol],
                        "covered_from": D("2021-08-01"),
                        "covered_through": D("2021-10-31"),
                    }
                ],
                preserve=(),
            )
        await upsert(
            s,
            FxRate,
            [
                {
                    "currency_code": "USD",
                    "quote_date": D(d),
                    "base_rate": Decimal(v),
                    "quote_unit": 1,
                    "source": "ECOS:731Y001",
                    "is_provisional": False,
                }
                for d, v in USD_FX.items()
            ],
        )
        await upsert(
            s,
            FxCoverage,
            [
                {
                    "currency_code": "USD",
                    "covered_from": D("2021-07-01"),
                    "covered_through": D("2021-10-31"),
                }
            ],
            preserve=(),
        )
        await s.commit()

    app = create_app()

    async def _session():  # type: ignore[no-untyped-def]
        async with session_factory() as s:
            yield s

    app.dependency_overrides[get_session] = _session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


BASE = {"start": "2021-08-01", "end": "2021-10-31", "reinvest": "true", "limit": "50"}
AAPL = {
    **BASE,
    "market": "NASDAQ",
    "symbol": "AAPL",
    "principal": "10000",
    "principalCurrency": "USD",
}
KRX = {
    **BASE,
    "market": "KRX",
    "symbol": "005930.KS",
    "principal": "10000000",
    "principalCurrency": "KRW",
}
RECURRING = {
    "start": "2021-08-01",
    "end": "2021-10-31",
    "reinvest": "true",
    "limit": "50",
    "frequency": "monthly",
}


async def get(client: AsyncClient, path: str, params: dict[str, str]) -> dict:
    res = await client.get(path, params=params)
    assert res.status_code == 200, res.text
    body: dict = res.json()
    return body


def identity(sale: dict) -> bool:
    return Decimal(sale["saleKrw"]) - Decimal(sale["acquisitionKrw"]) - Decimal(
        sale["feesKrw"]
    ) == Decimal(sale["gain"])


class Test일시금:
    async def test_해외는_매도금액_빼기_취득가_빼기_수수료가_차익이다(self, client) -> None:
        sale = (await get(client, "/api/stocks/simulation", AAPL))["summary"]["saleCost"]
        assert sale["taxKind"] == "capital_gains_tax"
        assert identity(sale)

    async def test_취득가는_처음_매수와_배당_재투자_매수의_합이다(self, client) -> None:
        body = await get(client, "/api/stocks/simulation", AAPL)
        rows = body["rows"]
        assert any(r["kind"] == "reinvest" and r["boughtShares"] > 0 for r in rows), (
            "재투자 매수가 있어야 뜻이 있다"
        )
        acquisition = floor(
            sum(
                (
                    r["boughtShares"] * Decimal(r["openPrice"]) * Decimal(r["fxRate"])
                    for r in rows
                    if r["boughtShares"] > 0
                ),
                Decimal("0"),
            )
        )
        first = floor(
            sum(
                (
                    r["boughtShares"] * Decimal(r["openPrice"]) * Decimal(r["fxRate"])
                    for r in rows
                    if r["kind"] == "buy"
                ),
                Decimal("0"),
            )
        )
        sale = body["summary"]["saleCost"]
        assert Decimal(sale["acquisitionKrw"]) == acquisition > first

    async def test_매도금액은_보유_주식만이다(self, client) -> None:
        body = await get(client, "/api/stocks/simulation", AAPL)
        summary = body["summary"]
        latest = [r for r in body["rows"] if r["date"] == summary["asOf"]][-1]
        expected = floor(Decimal(latest["balance"]) * Decimal(latest["fxRate"]))
        assert Decimal(summary["saleCost"]["saleKrw"]) == expected
        assert Decimal(summary["saleCost"]["saleKrw"]) < Decimal(summary["totalKrw"]), (
            "예수금은 팔지 않는다"
        )

    async def test_국내는_셋_모두_null이다(self, client) -> None:
        sale = (await get(client, "/api/stocks/simulation", KRX))["summary"]["saleCost"]
        assert sale["taxKind"] == "transaction_tax"
        assert (sale["saleKrw"], sale["acquisitionKrw"], sale["feesKrw"]) == (None, None, None)


class Test적립식:
    async def test_해외는_같은_식이_성립한다(self, client) -> None:
        body = await get(
            client,
            "/api/stocks/recurring-simulation",
            {
                **RECURRING,
                "market": "NASDAQ",
                "symbol": "AAPL",
                "amount": "1000",
                "principalCurrency": "USD",
            },
        )
        sale = body["summary"]["saleCost"]
        assert sale["taxKind"] == "capital_gains_tax"
        assert identity(sale)

    async def test_국내는_셋_모두_null이다(self, client) -> None:
        body = await get(
            client,
            "/api/stocks/recurring-simulation",
            {
                **RECURRING,
                "market": "KRX",
                "symbol": "005930.KS",
                "amount": "1000000",
                "principalCurrency": "KRW",
            },
        )
        sale = body["summary"]["saleCost"]
        assert (sale["saleKrw"], sale["acquisitionKrw"], sale["feesKrw"]) == (None, None, None)
