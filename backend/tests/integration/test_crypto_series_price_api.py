"""가상자산 시계열의 시세 (010 T008) — FR-001~FR-003, FR-007, SC-001, SC-002, contracts/rest-api
`GET /api/crypto/simulation/series`.

- `priceKind "crypto_open"`, `priceCurrency` = 코인의 **시세 통화**(원화 원금이어도 USD —
  Clarifications)
- 점은 일봉마다다(표는 달마다). 표에 있는 날의 점은 `price` = 표의 그 날 `openPrice`(문자열 그대로),
  나머지 날은 받아 둔 그 날 일봉의 시가다
- 출처 결측 날은 지금처럼 점이 없고 `gaps`(`source_missing`)다 — 가격을 지어내지 않는다(헌법 원칙 V)
"""
from __future__ import annotations

import datetime as dt
import json
from decimal import Decimal

import pytest
from httpx2 import ASGITransport, AsyncClient

from src.api.main import create_app
from src.db.session import get_session
from src.ingestion.investing.parse import parse_daily
from tests.integration.crypto_support import _rows, add_coin, seed_daily, seed_usd

D = dt.date.fromisoformat
FIXTURE = "btc_2020_2021.json"
DROP = (D("2021-03-01"), D("2021-03-02"))


@pytest.fixture
async def client(session_factory):  # type: ignore[no-untyped-def]
    app = create_app()

    async def _session():  # type: ignore[no-untyped-def]
        async with session_factory() as s:
            yield s

    app.dependency_overrides[get_session] = _session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


async def coin(session_factory, *, drop: tuple[dt.date, ...] = ()) -> int:  # type: ignore[no-untyped-def]
    coin_id = await add_coin(session_factory)
    await seed_daily(session_factory, coin_id, FIXTURE, covered=(D("2020-01-01"), D("2021-12-31")),
                     drop=drop)
    await seed_usd(session_factory, D("2019-12-01"), D("2022-12-31"))
    return coin_id


def opens() -> dict[str, Decimal]:
    body = json.dumps({"data": _rows(FIXTURE), "summary": {}})
    return {b.day.isoformat(): b.open for b in parse_daily(body, last_day=dt.date(2100, 1, 1))}


def params(coin_id: int, **over: str) -> dict[str, str]:
    return {"coinId": str(coin_id), "start": "2020-01-15", "principal": "10000000",
            "principalCurrency": "KRW", "end": "2021-12-31", **over}


async def series(client: AsyncClient, coin_id: int, **over: str) -> dict:  # type: ignore[type-arg]
    response = await client.get("/api/crypto/simulation/series",
                                params={**params(coin_id), "maxPoints": "5000", **over})
    assert response.status_code == 200, response.text
    return response.json()


async def test_가격의_종류와_통화는_코인의_시세_통화다(  # type: ignore[no-untyped-def]
        session_factory, client: AsyncClient) -> None:
    body = await series(client, await coin(session_factory))
    assert (body["priceKind"], body["priceCurrency"]) == ("crypto_open", "USD")
    assert (body["principalCurrency"], body["basisCurrency"]) == ("KRW", "KRW")


async def test_표에_있는_날은_표의_시가와_같고_나머지_날은_그_날_일봉의_시가다(  # type: ignore[no-untyped-def]
        session_factory, client: AsyncClient) -> None:
    coin_id = await coin(session_factory)
    table = (await client.get("/api/crypto/simulation", params=params(coin_id, limit="200"))).json()
    points = {p["date"]: p for p in (await series(client, coin_id))["points"]}
    assert table["rows"], table
    for row in table["rows"]:
        assert points[row["date"]]["price"] == row["openPrice"], row["date"]
    bars = opens()
    for day, point in points.items():
        assert Decimal(point["price"]) == bars[day], day
        assert "priceMissing" not in point


async def test_출처_결측_날은_점이_없고_gaps는_그대로다(  # type: ignore[no-untyped-def]
        session_factory, client: AsyncClient) -> None:
    body = await series(client, await coin(session_factory, drop=DROP))
    assert {"from": "2021-03-01", "to": "2021-03-02", "reason": "source_missing"} in body["gaps"]
    dates = [p["date"] for p in body["points"]]
    assert "2021-03-01" not in dates and "2021-03-02" not in dates
    assert all(p["price"] is not None for p in body["points"])


async def test_줄인_점의_가격은_그_날짜의_원래_값이다(session_factory, client: AsyncClient) -> None:  # type: ignore[no-untyped-def]
    coin_id = await coin(session_factory)
    full = {p["date"]: p for p in (await series(client, coin_id))["points"]}
    small = await series(client, coin_id, maxPoints="100")
    assert small["downsampled"] is True and len(small["points"]) == 100
    for point in small["points"]:
        assert point == full[point["date"]]
