"""주식 표의 종가와 종가 평가 잔고 (010 반복 3, T059) — FR-028, SC-009, contracts/rest-api "반복 3".

표(`/api/stocks/simulation`) 행마다:

- `closePrice` = 그 날 저장소의 원주가 종가(`close_raw`). 시가와 다르게 넣는다 — 기존 통합 테스트는
  둘을 같게 넣어 잔고가 어느 쪽으로
  평가되는지 가리지 못했다(research R10-18 실측)
- `balance` = `heldShares` × `closePrice`(종목 통화). 원화 원금 해외 종목의 `balanceKrw`는 이 잔고를
  그 행 환율로 환산한 값이다
- `openPrice`는 그대로 원주가 시가다(매수 가격)
- 시계열(`/series`)의 `balance`는 표와 같은 잔고다(KRW 평가 — FR-002)
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
from src.simulation.fx_convert import to_principal

D = dt.date.fromisoformat

DAYS = [
    "2021-08-02",
    "2021-08-03",
    "2021-08-30",
    "2021-09-01",
    "2021-09-02",
    "2021-10-01",
    "2021-10-05",
    "2021-11-01",
    "2021-11-02",
]
SPLIT_DAY = "2021-08-31"
FX = {"2021-08-02": "1150", "2021-09-01": "1160", "2021-10-01": "1190", "2021-11-01": "1200"}


def krx_open(day: str) -> Decimal:
    return Decimal(40000 + 1000 * DAYS.index(day))


def krx_close(day: str) -> Decimal:
    """시가보다 늘 650원 높다 — 잔고가 시가로 평가되면 모든 행이 어긋난다."""
    return krx_open(day) + Decimal("650")


def aapl_open(day: str) -> Decimal:
    base = Decimal("400") if day < SPLIT_DAY else Decimal("100")
    return base + Decimal(DAYS.index(day)) / 4


def aapl_close(day: str) -> Decimal:
    return aapl_open(day) + Decimal("1.5")


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
        krx, aapl = ids["005930.KS"], ids["AAPL"]
        rows = []
        for day in DAYS:
            rows.append(
                {
                    "stock_id": krx,
                    "quote_date": D(day),
                    "open_raw": krx_open(day),
                    "close_raw": krx_close(day),
                    "close_adjusted": krx_close(day),
                    "source": "yahoo:chart",
                }
            )
            rows.append(
                {
                    "stock_id": aapl,
                    "quote_date": D(day),
                    "open_raw": aapl_open(day),
                    "close_raw": aapl_close(day),
                    "close_adjusted": aapl_close(day),
                    "source": "yahoo:chart",
                }
            )
        await upsert(s, StockPrice, rows)
        await upsert(
            s,
            StockDividend,
            [
                {
                    "stock_id": krx,
                    "ex_date": D("2021-09-01"),
                    "amount_per_share": Decimal("300"),
                    "source": "yahoo:chart",
                }
            ],
        )
        await upsert(
            s,
            StockSplit,
            [
                {
                    "stock_id": aapl,
                    "effective_date": D(SPLIT_DAY),
                    "numerator": 4,
                    "denominator": 1,
                    "source": "yahoo:chart",
                }
            ],
        )
        await upsert(
            s,
            StockCoverage,
            [
                {
                    "stock_id": sid,
                    "covered_from": D("2021-08-01"),
                    "covered_through": D("2021-11-30"),
                }
                for sid in (krx, aapl)
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
                    "covered_through": D("2021-11-30"),
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


KRX = {
    "market": "KRX",
    "symbol": "005930.KS",
    "start": "2021-08-01",
    "principal": "86997",
    "principalCurrency": "KRW",
    "reinvest": "true",
    "end": "2021-11-30",
}
AAPL = {**KRX, "market": "NASDAQ", "symbol": "AAPL", "principal": "1000000"}
PRICES = {"005930.KS": (krx_open, krx_close), "AAPL": (aapl_open, aapl_close)}


async def table(client: AsyncClient, params: dict[str, str]) -> dict:  # type: ignore[type-arg]
    response = await client.get("/api/stocks/simulation", params={**params, "limit": "200"})
    assert response.status_code == 200, response.text
    return response.json()  # type: ignore[no-any-return]


@pytest.mark.parametrize("params", [KRX, AAPL], ids=["KRX", "AAPL-원화원금"])
async def test_행의_종가는_그_날_원주가_종가이고_시가는_그대로다(
    client: AsyncClient, params: dict[str, str]
) -> None:
    open_of, close_of = PRICES[params["symbol"]]
    rows = (await table(client, params))["rows"]
    assert rows
    for row in rows:
        assert Decimal(row["closePrice"]) == close_of(row["date"]), row["date"]
        assert Decimal(row["openPrice"]) == open_of(row["date"]), row["date"]


@pytest.mark.parametrize("params", [KRX, AAPL], ids=["KRX", "AAPL-원화원금"])
async def test_잔고는_보유_주식_곱하기_종가다(client: AsyncClient, params: dict[str, str]) -> None:
    for row in (await table(client, params))["rows"]:
        assert Decimal(row["balance"]) == row["heldShares"] * Decimal(row["closePrice"]), row[
            "date"
        ]


async def test_원화_원금_해외_종목의_원화_잔고는_종가_평가_잔고의_환산이다(
    client: AsyncClient,
) -> None:
    for row in (await table(client, AAPL))["rows"]:
        krw = to_principal(
            row["heldShares"] * Decimal(row["closePrice"]), Decimal(row["fxRate"]), "KRW"
        )
        assert Decimal(row["balanceKrw"]) == krw, row["date"]


@pytest.mark.parametrize("params", [KRX, AAPL], ids=["KRX", "AAPL-원화원금"])
async def test_시계열의_잔고는_표의_잔고와_같다(
    client: AsyncClient, params: dict[str, str]
) -> None:
    rows = (await table(client, params))["rows"]
    series = await client.get("/api/stocks/simulation/series", params=params)
    assert series.status_code == 200, series.text
    # 같은 날 행이 여럿이면(배당락 + 달 첫 행) 점은 그 날의 마지막 상태 하나다 — 그 날 행들의
    # 잔고 중 하나여야 한다(시가 평가면 어느 것과도 다르다)
    by_date: dict[str, set[Decimal]] = {}
    for row in rows:
        by_date.setdefault(row["date"], set()).add(Decimal(row.get("balanceKrw", row["balance"])))
    for point in series.json()["points"]:
        assert Decimal(point["balance"]) in by_date[point["date"]], point["date"]
