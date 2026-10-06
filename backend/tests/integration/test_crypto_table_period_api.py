"""가상자산 일시금 표의 기간 단위·결측 구간 행 (012 T016) — FR-004, FR-004b, FR-008, SC-002,
contracts/rest-api.md 1.

일봉(BTC 실제 응답 픽스처 — 2021-03은 3-01이 월요일)에서 3-01·3-05(금)·3-08~3-12(월~금)를 뺀다(출처
결측). 시작 3-01이라 첫 매수는 시작 월의
첫 일봉 3-02다(007). 계산 끝 3-21(일).

- 일 단위: 연속된 결측 구간마다 값 없는 행 하나(`kind: "missing"`, `date`·`dateTo`만) — 수는
  시계열의 `source_missing` 끊김 수와 같다. 매수일보다
  앞의 결측(3-01)도 표 맨 아래 행이다 — 지금의 ◇가 알리던 사실이 남는다
- 주 단위: 금요일 결측이면 금요일 이하의 마지막 일봉(목), 월~금이 모두 없으면 그 주의 마지막
  일봉(일)이다(명확화 2). 결측 행이 없다
- 표 행에 `firstDayMissing`(◇)이 없다(FR-008)
"""

from __future__ import annotations

import datetime as dt

import pytest
from httpx2 import ASGITransport, AsyncClient

from src.api.main import create_app
from src.db.session import get_session
from tests.integration.crypto_support import add_coin, seed_daily, seed_usd

D = dt.date.fromisoformat
DROPPED = [D("2021-03-01"), D("2021-03-05"), *(D(f"2021-03-{d:02d}") for d in range(8, 13))]


@pytest.fixture
async def client(session_factory):  # type: ignore[no-untyped-def]
    app = create_app()

    async def _session():  # type: ignore[no-untyped-def]
        async with session_factory() as s:
            yield s

    app.dependency_overrides[get_session] = _session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def btc(session_factory) -> int:  # type: ignore[no-untyped-def]
    coin_id = await add_coin(session_factory)
    await seed_daily(
        session_factory,
        coin_id,
        "btc_2020_2021.json",
        covered=(D("2020-01-01"), D("2021-12-31")),
        drop=DROPPED,
    )
    await seed_usd(session_factory, D("2019-12-01"), D("2022-12-31"))
    return coin_id


def params(coin_id: int, **over: str) -> dict[str, str]:
    base = {
        "coinId": str(coin_id),
        "start": "2021-03-01",
        "principal": "10000",
        "principalCurrency": "USD",
        "end": "2021-03-21",
        "limit": "200",
    }
    base.update(over)
    return base


async def table(client: AsyncClient, coin_id: int, **over: str) -> dict:
    res = await client.get("/api/crypto/simulation", params=params(coin_id, **over))
    assert res.status_code == 200, res.text
    return res.json()


def shape(rows: list[dict]) -> list[tuple[str, str, str | None, bool]]:
    return [(r["date"], r["kind"], r.get("shiftedFrom"), r.get("isOngoing", False)) for r in rows]


class Test결측_구간_행:
    async def test_일_단위는_결측_구간마다_값_없는_행_하나다(self, client, btc: int) -> None:
        rows = (await table(client, btc))["rows"]
        missing = [r for r in rows if r["kind"] == "missing"]
        assert [(r["date"], r["dateTo"]) for r in missing] == [
            ("2021-03-08", "2021-03-12"),
            ("2021-03-05", "2021-03-05"),
            ("2021-03-01", "2021-03-01"),
        ]
        assert all(
            set(r) == {"date", "dateTo", "kind"} for r in missing
        )  # 값 키가 없다 — 메우지 않는다
        order = [r["date"] for r in rows]
        assert order.index("2021-03-13") < order.index("2021-03-08") < order.index("2021-03-07")
        assert (
            rows[-1]["kind"] == "missing" and rows[-1]["date"] == "2021-03-01"
        )  # 매수일 앞의 결측 — 맨 아래
        assert rows[-2]["kind"] == "buy" and rows[-2]["date"] == "2021-03-02"

    async def test_결측_행_수는_시계열의_출처_결측_끊김_수와_같다(self, client, btc: int) -> None:
        rows = (await table(client, btc))["rows"]
        res = await client.get("/api/crypto/simulation/series", params=params(btc))
        assert res.status_code == 200, res.text
        gaps = [g for g in res.json()["gaps"] if g["reason"] == "source_missing"]
        assert len([r for r in rows if r["kind"] == "missing"]) == len(gaps) == 3
        assert sorted((r["date"], r["dateTo"]) for r in rows if r["kind"] == "missing") == sorted(
            (g["from"], g["to"]) for g in gaps
        )

    async def test_주_월에는_결측_행이_없다(self, client, btc: int) -> None:
        for unit in ("weekly", "monthly"):
            assert all(
                r["kind"] != "missing" for r in (await table(client, btc, period=unit))["rows"]
            ), unit


class Test주_월_대표일:
    async def test_주_단위(self, client, btc: int) -> None:
        rows = (await table(client, btc, period="weekly"))["rows"]
        assert shape(rows) == [
            (
                "2021-03-19",
                "period",
                None,
                False,
            ),  # 금요일 일봉 — 토·일 일봉이 있어도 금요일. 구간 끝(일) = 계산 끝 — 끝난 주
            ("2021-03-14", "period", "2021-03-12", False),  # 월~금 결측 — 그 주의 마지막 일봉(일)
            (
                "2021-03-04",
                "period",
                "2021-03-05",
                False,
            ),  # 금요일 결측 — 금요일 이하의 마지막 일봉(목)
            ("2021-03-02", "buy", None, False),
        ]

    async def test_월_단위(self, client, btc: int) -> None:
        rows = (await table(client, btc, period="monthly"))["rows"]
        assert shape(rows) == [
            ("2021-03-21", "period", "2021-03-31", True),
            ("2021-03-02", "buy", None, False),
        ]


class Test행:
    async def test_매수_행과_1일_결측_표시(self, client, btc: int) -> None:
        for unit in ("daily", "weekly", "monthly"):
            rows = (await table(client, btc, period=unit))["rows"]
            [buy] = [r for r in rows if r["kind"] == "buy"]
            assert "tradeFee" in buy and buy["boughtQuantity"] != "0.00000000"
            assert all("firstDayMissing" not in r for r in rows), unit
            assert {r["kind"] for r in rows} <= {"buy", "period", "missing"}

    async def test_요약은_세_단위에서_같다(self, client, btc: int) -> None:
        bodies = [await table(client, btc, period=unit) for unit in ("daily", "weekly", "monthly")]
        assert bodies[0]["summary"] == bodies[1]["summary"] == bodies[2]["summary"]
        assert bodies[0]["condition"] == bodies[1]["condition"] == bodies[2]["condition"]
        assert [b["period"] for b in bodies] == ["daily", "weekly", "monthly"]

    async def test_틀린_단위는_400이다(self, client, btc: int) -> None:
        res = await client.get("/api/crypto/simulation", params=params(btc, period="yearly"))
        assert res.status_code == 400 and res.json()["status"] == "invalid_query"
