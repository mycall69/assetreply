"""주식 시계열의 주가 — 분할만 반영한 수정 종가 (010 반복 1, T042) — FR-001, FR-002, FR-008, SC-001,
contracts/rest-api `GET /api/stocks/simulation/series`.

반복 전(T007 — 이 파일의 처음 이름 `test_stock_series_price_api.py`)에는 점의 `price`가 표의
시작가(원주가 시가)였고 응답에 `splits`가 있었다. 이제:

- `priceKind "stock_adjusted_close"`, `priceCurrency` = 종목 통화(원화 원금으로 미국 종목을 실행해도
  `USD`)
- 점의 `price` = 그 날 원주가 종가 ÷ 그 날 뒤 분할 비율(research R10-13). 분할(2021-08-31, 4:1) 앞뒤
  점이 이어진다 — 4배 꺾임이 없다
- `splits` 키가 없다(분할 표식 없음 — FR-008). 점의 날짜는 지금처럼 표의 행 날짜뿐이다(일별 아님)
- 표(`/simulation`)의 시작가·잔고는 그대로다 — 수정 종가는 차트에만 있다
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


def close_raw(params: dict[str, str], day: str) -> Decimal:
    """준비한 원주가 종가 — 시가와 같게 넣었다."""
    if params["symbol"] == "AAPL":
        return aapl_open(day)
    return Decimal(40000 + 1000 * DAYS.index(day))


def expected(params: dict[str, str], day: str) -> Decimal:
    """그 날 원주가 종가 ÷ 그 날 뒤 분할 비율 — AAPL은 2021-08-31(4:1) 앞이면 ÷ 4."""
    ratio = Decimal(4) if params["symbol"] == "AAPL" and day < SPLIT_DAY else Decimal(1)
    return close_raw(params, day) / ratio


@pytest.mark.parametrize("params", [KRX, AAPL], ids=["KRX", "AAPL-원화원금"])
async def test_점의_가격은_그_날_수정_종가다(
        client: AsyncClient, params: dict[str, str]) -> None:
    table, series = await both(client, params)
    by_date = rows_by_date(table)
    # 점의 날짜는 그대로 월 첫 거래일·사건 날이다(일별 아님 — spec FR-001). 012 승인 2026-10-06 —
    # 표는 일 단위라 더 촘촘하다: 점마다 같은 날짜의
    # 표 행이 있다.
    assert {p["date"] for p in series["points"]} <= set(by_date)
    for point in series["points"]:
        assert Decimal(point["price"]) == expected(params, point["date"]), point["date"]
        assert "priceMissing" not in point


async def test_가격의_종류와_통화는_종목의_것이다(client: AsyncClient) -> None:
    _, krx = await both(client, KRX)
    _, aapl = await both(client, AAPL)
    assert (krx["priceKind"], krx["priceCurrency"]) == ("stock_adjusted_close", "KRW")
    assert (aapl["priceKind"], aapl["priceCurrency"]) == ("stock_adjusted_close", "USD")
    assert (aapl["principalCurrency"], aapl["basisCurrency"]) == ("KRW", "KRW")


async def test_분할_앞뒤가_이어지고_분할_기록을_싣지_않는다(client: AsyncClient) -> None:
    table, aapl = await both(client, AAPL)
    assert "splits" not in aapl
    prices = {p["date"]: Decimal(p["price"]) for p in aapl["points"]}
    assert SPLIT_DAY not in prices
    before, after = prices["2021-08-02"], prices["2021-09-01"]
    # 원주가는 400 → 100.75(분할 4배) — 수정 종가는 100 → 100.75로 이어진다
    assert Decimal("0.9") < before / after < Decimal("1.1")
    # 표의 시작가는 그대로 원주가다 — 수정 종가는 차트에만 있다
    rows = rows_by_date(table)
    assert Decimal(rows["2021-08-02"][0]["openPrice"]) == aapl_open("2021-08-02")


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
    assert "splits" not in series
