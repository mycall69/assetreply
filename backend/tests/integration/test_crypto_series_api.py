"""가상자산 차트 시계열 (T039) — 007 FR-023, FR-043, FR-044, SC-005, SC-007, contracts/rest-api `GET
/api/crypto/simulation/series`.

**점은 일봉마다**다(표는 월 행). 잔고는 KRW(표의 `balanceKrw`), 수익률은 KRW 기준 — 표와 **같은
함수를 같은 입력으로** 부르므로 표의 행과 같은 날짜의 점은 같은 값이다(005 SC-032와 같은 이유).

가상자산은 휴장이 없다 — 커버리지 안의 빈 날은 **출처 결측**(`source_missing`)이고 차트가 끊는다.
주식·외환의 `no_quote`(휴장 — 잇는다)는 가상자산에 없다(FR-023, research R7-9).
"""
from __future__ import annotations

import datetime as dt

import pytest
from httpx2 import ASGITransport, AsyncClient

from src.api.main import create_app
from src.db.session import get_session
from tests.integration.crypto_support import add_coin, seed_daily, seed_usd

D = dt.date.fromisoformat


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
    base = {"coinId": str(coin_id), "start": "2020-01-15", "principal": "10000",
            "principalCurrency": "USD", "end": "2021-12-31", "maxPoints": "5000"}
    base.update(over)
    return base


async def series(client: AsyncClient, coin_id: int, status: int = 200, **over: str) -> dict:
    response = await client.get("/api/crypto/simulation/series", params=params(coin_id, **over))
    assert response.status_code == status, response.text
    return response.json()


class Test점:
    async def test_점은_일봉마다이고_KRW_기준이다(self, session_factory, client) -> None:
        coin_id = await coin(session_factory)
        body = await series(client, coin_id)
        assert (body["principalCurrency"], body["basisCurrency"]) == ("USD", "KRW")
        dates = [p["date"] for p in body["points"]]
        assert (len(dates), dates[0], dates[-1]) == (731, "2020-01-01", "2021-12-31")
        assert body["downsampled"] is False and body["sourcePointCount"] == 731

    async def test_표의_행과_같은_날짜는_같은_값이다(self, session_factory, client) -> None:
        """SC-032 — 표의 잔고 KRW·수익률과 차트의 점이 어긋나면 양쪽 다 그럴듯해 알아챌 신호가
        없다."""
        coin_id = await coin(session_factory)
        table = (await client.get("/api/crypto/simulation", params={
            k: v for k, v in params(coin_id, limit="50").items() if k != "maxPoints"})).json()
        points = {p["date"]: p for p in (await series(client, coin_id))["points"]}
        for row in table["rows"]:
            point = points[row["date"]]
            assert (point["balance"], point["returnRate"]) == (row["balanceKrw"], row["returnRate"])
        # 끝점은 보드(마지막 일봉의 평가)와 같다
        assert points["2021-12-31"]["returnRate"] == table["summary"]["returnRate"]

    async def test_많으면_줄여서_보낸다(self, session_factory, client) -> None:
        coin_id = await coin(session_factory)
        body = await series(client, coin_id, maxPoints="100")
        assert body["downsampled"] is True
        assert len(body["points"]) == 100 and body["sourcePointCount"] == 731
        assert body["algorithm"] == "lttb"


class Test결측:
    async def test_커버리지_안_빈_날은_출처_결측이다(self, session_factory, client) -> None:
        coin_id = await coin(session_factory, drop=(D("2021-03-01"), D("2021-03-02")))
        body = await series(client, coin_id)
        missing = {"from": "2021-03-01", "to": "2021-03-02", "reason": "source_missing"}
        assert missing in body["gaps"]
        assert all(g["reason"] != "no_quote" for g in body["gaps"])
        assert "2021-03-01" not in [p["date"] for p in body["points"]]

    async def test_빈_날이_없으면_결측도_없다(self, session_factory, client) -> None:
        coin_id = await coin(session_factory)
        assert (await series(client, coin_id))["gaps"] == []


class Test게이트와_오류:
    async def test_받지_않은_구간이면_표와_같은_202다(self, session_factory, client) -> None:
        coin_id = await add_coin(session_factory)
        await seed_usd(session_factory, D("2019-12-01"), D("2022-12-31"))
        body = await series(client, coin_id, 202)
        assert body["status"] == "collecting" and "jobId" in body
        assert "points" not in body

    async def test_모르는_코인은_표와_같은_404다(self, client) -> None:
        body = await series(client, 99999999, 404)
        assert body["status"] == "unknown_coin"

    async def test_원금_통화_조합은_표와_같이_막는다(self, session_factory, client) -> None:
        coin_id = await coin(session_factory)
        body = await series(client, coin_id, 400, principalCurrency="EUR")
        assert body["status"] == "currency_pair_not_allowed"
