"""주식 시계열의 주가 (010 T007) — FR-001, FR-002, FR-007, FR-008, SC-001, contracts/rest-api `GET
/api/stocks/simulation/series`.

- `priceKind "stock_open"`, `priceCurrency` = **종목 통화** — 원화 원금으로 미국 종목을 실행해도
  `USD`다(Clarifications). 잔고·수익률의
  기준(`basisCurrency` KRW)과 다르다
- 점의 `price` = 같은 조건 표(`/simulation`)의 그 날 행 `openPrice`(원주가 시가 — 문자열 그대로).
  점의 날짜는 **표의 행 날짜뿐**이다(일별 주가가
  아니다 — spec FR-001)
- `splits` = 구간 안의 분할 기록. 효력일(2021-08-31)은 점의 날짜가 아니다 — 원주가가 효력일 뒤 첫
  점에서 분할 비율만큼 꺾인다
"""
from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest
from httpx2 import ASGITransport, AsyncClient
from sqlalchemy import select

from src.api.main import create_app
from src.db.dialect import upsert
from src.db.models import (
    FxCoverage,
    FxRate,
    Stock,
    StockCoverage,
    StockDividend,
    StockPrice,
    StockSplit,
)
from src.db.session import get_session

D = dt.date.fromisoformat

# 2021-08 ~ 2021-11의 거래일. 2021-09-01에는 배당락 행과 달 첫 행이 겹친다(KRX).
DAYS = ["2021-08-02", "2021-08-03", "2021-08-30", "2021-09-01", "2021-09-02",
        "2021-10-01", "2021-10-05", "2021-11-01", "2021-11-02"]
SPLIT_DAY = "2021-08-31"  # 점의 날짜가 아니다 — 거래일이지만 달 첫 날도 배당락일도 아니다
FX = {"2021-08-02": "1150", "2021-09-01": "1160", "2021-10-01": "1190", "2021-11-01": "1200"}


def aapl_open(day: str) -> Decimal:
    """분할 전 약 400달러, 뒤 약 100달러 — 원주가다(Yahoo 반영가를 되살린 값과 같은 모양)."""
    base = Decimal("400") if day < SPLIT_DAY else Decimal("100")
    return base + Decimal(DAYS.index(day)) / 4


@pytest.fixture
async def client(session_factory):  # type: ignore[no-untyped-def]
    async with session_factory() as s:
        await upsert(s, Stock, [
            {"market": "KRX", "symbol": "005930.KS", "name": "삼성전자", "currency": "KRW",
             "first_available_date": D("1975-06-11")},
            {"market": "NASDAQ", "symbol": "AAPL", "name": "Apple Inc.", "currency": "USD",
             "first_available_date": D("1980-12-12")},
        ])
        await s.commit()
        ids = {r.symbol: int(r.id) for r in (await s.execute(select(Stock))).scalars()}
        krx, aapl = ids["005930.KS"], ids["AAPL"]
        rows = []
        for i, day in enumerate(DAYS):
            price = Decimal(40000 + 1000 * i)
            rows.append({"stock_id": krx, "quote_date": D(day), "open_raw": price,
                         "close_raw": price, "close_adjusted": price, "source": "yahoo:chart"})
            rows.append({"stock_id": aapl, "quote_date": D(day), "open_raw": aapl_open(day),
                         "close_raw": aapl_open(day), "close_adjusted": aapl_open(day),
                         "source": "yahoo:chart"})
        await upsert(s, StockPrice, rows)
        await upsert(s, StockDividend, [{"stock_id": krx, "ex_date": D("2021-09-01"),
                                         "amount_per_share": Decimal("300"),
                                         "source": "yahoo:chart"}])
        await upsert(s, StockSplit, [{"stock_id": aapl, "effective_date": D(SPLIT_DAY),
                                      "numerator": 4, "denominator": 1,
                                      "source": "yahoo:chart"}])
        await upsert(s, StockCoverage, [
            {"stock_id": sid, "covered_from": D("2021-08-01"), "covered_through": D("2021-11-30")}
            for sid in (krx, aapl)], preserve=())
        await upsert(s, FxRate, [{"currency_code": "USD", "quote_date": D(d),
                                  "base_rate": Decimal(v), "quote_unit": 1,
                                  "source": "ECOS:731Y001", "is_provisional": False}
                                 for d, v in FX.items()])
        await upsert(s, FxCoverage, [{"currency_code": "USD", "covered_from": D("2021-07-01"),
                                      "covered_through": D("2021-11-30")}], preserve=())
        await s.commit()

    app = create_app()

    async def _override():  # type: ignore[no-untyped-def]
        async with session_factory() as s:
            yield s

    app.dependency_overrides[get_session] = _override
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


KRX = {"market": "KRX", "symbol": "005930.KS", "start": "2021-08-01", "principal": "86997",
       "principalCurrency": "KRW", "reinvest": "true", "end": "2021-11-30"}
AAPL = {**KRX, "market": "NASDAQ", "symbol": "AAPL", "principal": "1000000"}


async def both(client: AsyncClient, params: dict[str, str], **over: str) -> tuple[dict, dict]:  # type: ignore[type-arg]
    table = await client.get("/api/stocks/simulation", params={**params, "limit": "200"})
    series = await client.get("/api/stocks/simulation/series", params={**params, **over})
    assert (table.status_code, series.status_code) == (200, 200), (table.text, series.text)
    return table.json(), series.json()


def rows_by_date(table: dict) -> dict[str, list[dict]]:  # type: ignore[type-arg]
    out: dict[str, list[dict]] = {}  # type: ignore[type-arg]
    for row in table["rows"]:
        out.setdefault(row["date"], []).append(row)
    return out


@pytest.mark.parametrize("params", [KRX, AAPL], ids=["KRX", "AAPL-원화원금"])
async def test_점마다_가격이_표의_그_날_시작가와_같다(
        client: AsyncClient, params: dict[str, str]) -> None:
    table, series = await both(client, params)
    by_date = rows_by_date(table)
    # 점의 날짜 = 표의 날짜(일별 아님 — spec FR-001)
    assert sorted(by_date) == [p["date"] for p in series["points"]]
    for point in series["points"]:
        assert all(point["price"] == r["openPrice"] for r in by_date[point["date"]]), point["date"]
        assert "priceMissing" not in point


async def test_가격의_종류와_통화는_종목의_것이다(client: AsyncClient) -> None:
    _, krx = await both(client, KRX)
    _, aapl = await both(client, AAPL)
    assert (krx["priceKind"], krx["priceCurrency"]) == ("stock_open", "KRW")
    assert (aapl["priceKind"], aapl["priceCurrency"]) == ("stock_open", "USD")
    assert (aapl["principalCurrency"], aapl["basisCurrency"]) == ("KRW", "KRW")


async def test_분할은_구간_안의_기록이고_원주가가_효력일_뒤_첫_점에서_꺾인다(
        client: AsyncClient) -> None:
    _, aapl = await both(client, AAPL)
    assert aapl["splits"] == [{"date": SPLIT_DAY, "numerator": 4, "denominator": 1}]
    prices = {p["date"]: Decimal(p["price"]) for p in aapl["points"]}
    assert SPLIT_DAY not in prices
    before, after = prices["2021-08-02"], prices["2021-09-01"]
    assert Decimal("3.5") < before / after < Decimal("4.5")
    _, krx = await both(client, KRX)
    assert krx["splits"] == []


async def test_줄인_점의_가격은_그_날짜의_원래_값이다(client: AsyncClient) -> None:
    _, full = await both(client, KRX)
    _, small = await both(client, KRX, maxPoints="2")
    assert small["downsampled"] is True and len(small["points"]) == 2
    by_date = {p["date"]: p for p in full["points"]}
    for point in small["points"]:
        assert point == by_date[point["date"]]


async def test_기존_키는_그대로다(client: AsyncClient) -> None:
    _, series = await both(client, KRX)
    assert {"from", "to", "principalCurrency", "basisCurrency", "downsampled", "algorithm",
            "sourcePointCount", "points", "gaps"} <= set(series)
    assert {"date", "balance", "returnRate", "price"} == set(series["points"][0])
