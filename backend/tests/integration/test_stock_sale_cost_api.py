"""주식 보드의 매도 수수료·세금 (010 반복 4, T070) — FR-030, SC-011, contracts/rest-api "반복 4".

`GET /api/stocks/simulation`의 `summary`에 **더하는** 키:

- `saleCost` — 기준일 상태(마지막 거래일)를 그 날 종가로 모두 판다고 가정한 수수료·세금(원화, 원
  미만 버림)
- `profitAfterSale` = `profit` − `saleCost.total`, `returnRateAfterSale` = 그 값 ÷ 원금(원화)
- 국내는 증권거래세(2026년 0.20%), 해외는 (원화 양도차익 − 250만 원) × 22% — 취득가는 매수마다 그 행
  환율
- 011(사용자 승인 2026-10-06, A2): 세율은 설정값이다 — 2023-01-01 앞의 기준일도 설정 세율로
  계산한다(010의 "표 밖은 비운다"를 대체)
- 기존 `summary` 키(`profit`·`returnRate` 등 — 보유 중)는 그대로다

시드의 마지막 거래일(2026-03-03)은 그 달 첫 거래일이라 표의 첫 행이 기준일 상태다.
"""

from __future__ import annotations

import datetime as dt
from decimal import ROUND_FLOOR, Decimal

import pytest
from httpx2 import ASGITransport, AsyncClient
from sqlalchemy import select

from src.api.main import create_app
from src.db.dialect import upsert
from src.db.models import FxCoverage, FxRate, Stock, StockCoverage, StockPrice
from src.db.session import get_session
from src.simulation.money import quantize_rate

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


@pytest.fixture
async def client(session_factory):  # type: ignore[no-untyped-def]
    async with session_factory() as s:
        await upsert(
            s,
            Stock,
            [
                {
                    "market": "KRX",
                    "symbol": "005930.KS",
                    "name": "삼성전자",
                    "currency": "KRW",
                    "first_available_date": D("1975-06-11"),
                },
                {
                    "market": "NASDAQ",
                    "symbol": "AAPL",
                    "name": "Apple Inc.",
                    "currency": "USD",
                    "first_available_date": D("1980-12-12"),
                },
            ],
        )
        await s.commit()
        ids = {r.symbol: int(r.id) for r in (await s.execute(select(Stock))).scalars()}
        rows = []
        for day in DAYS_2026 + DAYS_2021:
            for symbol, price in (("005930.KS", krx_price), ("AAPL", aapl_price)):
                open_, close = price(day)
                rows.append(
                    {
                        "stock_id": ids[symbol],
                        "quote_date": D(day),
                        "open_raw": open_,
                        "close_raw": close,
                        "close_adjusted": close,
                        "source": "yahoo:chart",
                    }
                )
        await upsert(s, StockPrice, rows)
        await upsert(
            s,
            StockCoverage,
            [
                {
                    "stock_id": sid,
                    "covered_from": D("2021-08-01"),
                    "covered_through": D("2026-03-31"),
                }
                for sid in ids.values()
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
                for d, v in FX.items()
            ],
        )
        await upsert(
            s,
            FxCoverage,
            [
                {
                    "currency_code": "USD",
                    "covered_from": D("2021-07-01"),
                    "covered_through": D("2026-03-31"),
                }
            ],
            preserve=(),
        )
        await s.commit()

    app = create_app()

    async def _override():  # type: ignore[no-untyped-def]
        async with session_factory() as s:
            yield s

    app.dependency_overrides[get_session] = _override
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


KRX_2026 = {
    "market": "KRX",
    "symbol": "005930.KS",
    "start": "2026-01-01",
    "principal": "10000000",
    "principalCurrency": "KRW",
    "reinvest": "true",
    "end": "2026-03-03",
}
AAPL_2026 = {**KRX_2026, "market": "NASDAQ", "symbol": "AAPL"}
KRX_2021 = {**KRX_2026, "start": "2021-08-01", "end": "2021-09-02"}


async def simulate(client: AsyncClient, params: dict[str, str]) -> dict:  # type: ignore[type-arg]
    response = await client.get("/api/stocks/simulation", params={**params, "limit": "200"})
    assert response.status_code == 200, response.text
    return response.json()  # type: ignore[no-any-return]


async def test_국내_종목은_수수료와_증권거래세를_뺀다(client: AsyncClient) -> None:
    body = await simulate(client, KRX_2026)
    summary, latest = body["summary"], body["rows"][0]
    assert latest["date"] == "2026-03-03" == summary["asOf"]
    sale = Decimal(latest["balance"])
    fee = floor(sale * Decimal(body["condition"]["tradeFeeRate"]))
    tax = floor(sale * Decimal("0.0020"))
    assert summary["saleCost"] == {
        "fee": str(fee),
        "tax": str(tax),
        "total": str(fee + tax),
        "taxKind": "transaction_tax",
        "taxRate": "0.0020",
        "gain": None,
        "deduction": None,
    }
    after = Decimal(summary["profit"]) - (fee + tax)
    assert Decimal(summary["profitAfterSale"]) == after
    assert Decimal(summary["returnRateAfterSale"]) == quantize_rate(after / Decimal("10000000"))
    # 보유 중 값은 그대로다 — 표의 기준일 행과 같다
    assert (summary["profit"], summary["returnRate"]) == (latest["profit"], latest["returnRate"])


async def test_해외_종목은_원화_양도차익의_22퍼센트를_뺀다(client: AsyncClient) -> None:
    body = await simulate(client, AAPL_2026)
    summary, rows = body["summary"], body["rows"]
    latest = rows[0]
    fee_rate = Decimal(body["condition"]["tradeFeeRate"])
    fx = Decimal(latest["fxRate"])
    sale_usd = Decimal(latest["balance"])
    sale_krw = floor(sale_usd * fx)
    sell_fee = floor(sale_usd * fee_rate * fx)
    acquisition = floor(
        sum(
            (
                row["boughtShares"] * Decimal(row["openPrice"]) * Decimal(row["fxRate"])
                for row in rows
                if row["boughtShares"] > 0
            ),
            Decimal("0"),
        )
    )
    buy_fees = floor(
        sum(
            (
                Decimal(row["tradeFee"]) * Decimal(row["fxRate"])
                for row in rows
                if "tradeFee" in row
            ),
            Decimal("0"),
        )
    )
    gain = sale_krw - acquisition - buy_fees - sell_fee
    tax = floor(max(gain - Decimal("2500000"), Decimal("0")) * Decimal("0.22"))
    assert acquisition > 0 and gain > 0
    assert summary["saleCost"] == {
        "fee": str(sell_fee),
        "tax": str(tax),
        "total": str(sell_fee + tax),
        "taxKind": "capital_gains_tax",
        "taxRate": "0.22",
        "gain": str(gain),
        "deduction": "2500000",
    }
    assert Decimal(summary["profitAfterSale"]) == Decimal(summary["profit"]) - (sell_fee + tax)


async def test_2023년_전_기준일도_설정_세율로_계산한다(client: AsyncClient) -> None:
    """011 FR-037(사용자 승인 2026-10-06, A2) — 설정값이 010 반복 4의 시행일별 법령 표를 대체했다.
    2023-01-01 전 기준일도 "세금 비움"이 아니라 설정의 국내 매도 세율(기본 0.20%)로 계산한다.
    010에서 이 자리는 `test_세율_표_밖_기준일은_세금을_비운다`였다."""
    body = await simulate(client, KRX_2021)
    summary, newest = body["summary"], body["rows"][0]
    # 012 승인 2026-10-06 — 일 단위 표의 맨 위가 기준일(2021-09-02) 행이다(전에는 그 달 첫 거래일
    # 09-01 행이었다). 시드에 배당이
    # 없어 보유 수는 그대로이고, 매도금액 = 보유 × 기준일 종가(시드)
    assert summary["asOf"] == "2021-09-02" and newest["date"] == "2021-09-02"
    sale = newest["heldShares"] * krx_price("2021-09-02")[1]
    fee = floor(sale * Decimal(body["condition"]["tradeFeeRate"]))
    tax = floor(sale * Decimal("0.0020"))
    assert summary["saleCost"] == {
        "fee": str(fee),
        "tax": str(tax),
        "total": str(fee + tax),
        "taxKind": "transaction_tax",
        "taxRate": "0.0020",
        "gain": None,
        "deduction": None,
    }
    assert Decimal(summary["profitAfterSale"]) == Decimal(summary["profit"]) - (fee + tax)
    assert summary["returnRateAfterSale"] is not None
