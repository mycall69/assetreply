"""가상자산 적립식 시계열 (011 T035) — `GET /api/crypto/recurring-simulation/series`. FR-019,
contracts/rest-api §2.

- 점은 **일봉마다**다(표는 납입 행 + 그 달 첫 일봉 행). 첫 점은 첫 납입일이다 — 그 앞에는 넣은
  돈이 없다
- `balance`는 원화 총자산(잔고 + 매수 대기금), `principal`은 그날까지의 원화 총 납입 원금이다
  - 표와 같은 계산을 거친다. 표의 행과 같은 날짜의 점은 같은 값이다(005 SC-032와 같은 이유)
- `price`는 그 일봉의 시가(시세 통화 — 007 일시금과 같다)
- 커버리지 안의 빈 날은 출처 결측이다 — 점이 없고 `gaps`의 `source_missing`이다(일시금과 같은 판정)
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest
from httpx2 import ASGITransport, AsyncClient

from src.api.main import create_app
from src.db.session import get_session
from tests.integration.crypto_support import add_coin, seed_daily, seed_usd

D = dt.date.fromisoformat
P = Decimal
TABLE = "/api/crypto/recurring-simulation"
SERIES = TABLE + "/series"


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
    await seed_daily(session_factory, coin_id, "btc_2020_2021.json",
                     covered=(D("2020-01-01"), D("2021-12-31")), drop=drop)
    await seed_usd(session_factory, D("2019-12-01"), D("2022-12-31"))
    return coin_id


def params(coin_id: int, **over: str) -> dict[str, str]:
    return {"coinId": str(coin_id), "start": "2021-01-01", "amount": "10000",
            "principalCurrency": "KRW", "frequency": "weekly", "end": "2021-03-31", **over}


async def both(http: AsyncClient, coin_id: int, **over: str) -> tuple[dict, dict]:  # type: ignore[type-arg]
    table = await http.get(TABLE, params={**params(coin_id, **over), "limit": "200"})
    series = await http.get(SERIES, params={**params(coin_id, **over), "maxPoints": "5000"})
    assert table.status_code == series.status_code == 200, (table.text, series.text)
    return table.json(), series.json()


async def test_점은_첫_납입일부터_일봉마다다(session_factory, client) -> None:  # type: ignore[no-untyped-def]
    _, series = await both(client, await coin(session_factory))
    dates = [p["date"] for p in series["points"]]
    assert (len(dates), dates[0], dates[-1]) == (90, "2021-01-01", "2021-03-31")
    assert (series["principalCurrency"], series["basisCurrency"]) == ("KRW", "KRW")
    assert (series["priceKind"], series["priceCurrency"]) == ("crypto_open", "USD")
    assert series["downsampled"] is False and series["sourcePointCount"] == 90
    assert series["gaps"] == []


async def test_표의_행과_같은_날짜는_같은_값이다(session_factory, client) -> None:  # type: ignore[no-untyped-def]
    table, series = await both(client, await coin(session_factory))
    points = {p["date"]: p for p in series["points"]}
    for row in table["rows"]:
        point = points[row["date"]]
        assert P(point["principal"]) == P(row["contributedKrw"])
        assert P(point["balance"]) == P(row["profit"]) + P(row["contributedKrw"])
        assert P(point["returnRate"]) == P(row["returnRate"])
        assert P(point["price"]) == P(row["openPrice"])
    # 끝점은 보드(마지막 일봉의 평가)와 같다
    assert P(points["2021-03-31"]["balance"]) == P(table["summary"]["totalKrw"])


async def test_누적_납입_원금은_납입일에만_오른다(session_factory, client) -> None:  # type: ignore[no-untyped-def]
    _, series = await both(client, await coin(session_factory))
    steps = [p["date"] for prev, p in zip(series["points"], series["points"][1:], strict=False)
             if P(p["principal"]) != P(prev["principal"])]
    # 2021-01-01(금)에 맞춘 매주 — 첫 점 다음부터 금요일마다 오른다
    assert steps == [(D("2021-01-08") + dt.timedelta(weeks=i)).isoformat() for i in range(12)]
    assert P(series["points"][-1]["principal"]) == P("130000")


async def test_출처_결측은_점이_없고_끊는다(session_factory, client) -> None:  # type: ignore[no-untyped-def]
    missing = (D("2021-02-10"), D("2021-02-11"))
    _, series = await both(client, await coin(session_factory, drop=missing))
    dates = {p["date"] for p in series["points"]}
    assert not dates & {d.isoformat() for d in missing}
    assert series["gaps"] == [{"from": "2021-02-10", "to": "2021-02-11",
                               "reason": "source_missing"}]


async def test_줄여도_점의_값이_같다(session_factory, client) -> None:  # type: ignore[no-untyped-def]
    coin_id = await coin(session_factory)
    _, full = await both(client, coin_id)
    reduced = (await client.get(SERIES, params={**params(coin_id), "maxPoints": "10"})).json()
    by_date = {p["date"]: p for p in full["points"]}
    assert reduced["downsampled"] is True and len(reduced["points"]) == 10
    assert all(p == by_date[p["date"]] for p in reduced["points"])
