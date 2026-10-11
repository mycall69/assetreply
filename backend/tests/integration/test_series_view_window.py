"""시계열 경로의 보기 구간 질의 (014 반복 2026-10-11c T192) — spec FR-038, SC-023,
contracts/rest-api.md A13, data-model 16, research R14-31.

주식·가상자산 시계열 경로 여덟(메뉴 넷·비교 넷)이 `viewFrom`·`viewTo`를 받으면 계산은 그대로 두고 그
구간 ∩ 계산 구간의 **시세일마다 점 하나**를 낸다. 주식은 일자별 표 "일" 행과 같은 규칙(사건·월 행이
있는 날은 그날의 마지막 행 — 원래 점과 같은 값, 그 밖은 그날 상태), 가상자산은 일봉 그대로(줄이기
전). 결측은 그 구간에서 다시 판정하고, 구간 점이 `maxPoints`보다 많으면 그 안에서 줄인다. 비교
경로는 같은 점으로 `valueLine`을 낸다. 질의가 없으면 응답은 지금과 같다. 하나만 보내거나 차례가
거꾸로면 400 `invalid_query`다.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest

from tests.integration.comparison_support import AAPL_KRW, KRX, http, seed_stocks
from tests.integration.crypto_support import add_coin, seed_daily, seed_usd
from tests.integration.stock_recurring_support import AAPL_WEEKLY, DAYS_2026, KRX_MONTHLY
from tests.integration.stock_recurring_support import seed as seed_recurring

P = Decimal
D = dt.date.fromisoformat
#: comparison_support의 시세일 — 2021-09-01 배당락, 09-03 재투자, 09-02는 사건이 없는 날이다.
LUMP_DAYS = ["2021-08-02", "2021-09-01", "2021-09-02", "2021-09-03", "2021-10-01"]
WINDOW = {"viewFrom": "2021-08-01", "viewTo": "2021-10-31"}


def dates(body: dict) -> list[str]:  # type: ignore[type-arg]
    return [p["date"] for p in body["points"]]


async def get(client, path: str, params: dict[str, str]) -> dict:  # type: ignore[no-untyped-def, type-arg]
    response = await client.get(path, params=params)
    assert response.status_code == 200, response.text
    return response.json()  # type: ignore[no-any-return]


def day_rows(table: dict) -> dict[str, dict]:  # type: ignore[type-arg]
    """표 `period=daily`의 날짜 → 그날의 행(사건이 없는 날은 행이 하나다)."""
    out: dict[str, list[dict]] = {}  # type: ignore[type-arg]
    for row in table["rows"]:
        out.setdefault(row["date"], []).append(row)
    return {day: rows[0] for day, rows in out.items() if len(rows) == 1}


class Test주식_일시금:
    async def test_구간의_시세일마다_점이고_원래_점과_같은_값이다(self, session_factory) -> None:
        await seed_stocks(session_factory)
        async with http(session_factory) as client:
            base = await get(client, "/api/stocks/simulation/series", KRX)
            window = await get(client, "/api/stocks/simulation/series", {**KRX, **WINDOW})
        # 원래 점은 월·사건 행뿐이다 — 09-02(사건 없는 날)가 없다.
        assert "2021-09-02" not in dates(base)
        assert dates(window) == LUMP_DAYS
        by_date = {p["date"]: p for p in window["points"]}
        for point in base["points"]:
            assert by_date[point["date"]] == point
        assert window["downsampled"] is False and window["sourcePointCount"] == len(LUMP_DAYS)

    async def test_사건_없는_날은_일자별_표의_일_행과_같다(self, session_factory) -> None:
        await seed_stocks(session_factory)
        async with http(session_factory) as client:
            window = await get(client, "/api/stocks/simulation/series", {**KRX, **WINDOW})
            table = await get(client, "/api/stocks/simulation", {**KRX, "period": "daily"})
        row = day_rows(table)["2021-09-02"]
        point = next(p for p in window["points"] if p["date"] == "2021-09-02")
        assert P(point["balance"]) == P(row["balance"])
        assert P(point["returnRate"]) == P(row["returnRate"])

    async def test_해외_종목은_원화_평가다(self, session_factory) -> None:
        await seed_stocks(session_factory)
        async with http(session_factory) as client:
            window = await get(client, "/api/stocks/simulation/series", {**AAPL_KRW, **WINDOW})
            table = await get(client, "/api/stocks/simulation", {**AAPL_KRW, "period": "daily"})
        row = day_rows(table)["2021-09-02"]
        point = next(p for p in window["points"] if p["date"] == "2021-09-02")
        assert P(point["balance"]) == P(row["balanceKrw"])
        assert P(point["returnRate"]) == P(row["returnRate"])

    async def test_좁은_구간은_그_안의_시세일뿐이다(self, session_factory) -> None:
        await seed_stocks(session_factory)
        async with http(session_factory) as client:
            window = await get(client, "/api/stocks/simulation/series",
                               {**KRX, "viewFrom": "2021-09-01", "viewTo": "2021-09-03"})
        assert dates(window) == ["2021-09-01", "2021-09-02", "2021-09-03"]
        assert all(D(g["from"]) >= D("2021-09-01") and D(g["to"]) <= D("2021-09-03")
                   for g in window["gaps"])

    async def test_계산_구간_밖이면_점이_없다(self, session_factory) -> None:
        await seed_stocks(session_factory)
        async with http(session_factory) as client:
            window = await get(client, "/api/stocks/simulation/series",
                               {**KRX, "viewFrom": "2019-01-01", "viewTo": "2019-12-31"})
        assert window["points"] == [] and window["gaps"] == []


class Test주식_적립식:
    @pytest.mark.parametrize("params", [KRX_MONTHLY, AAPL_WEEKLY], ids=["국내 매달", "해외 매주"])
    async def test_구간의_시세일마다_점이고_원래_점과_같은_값이다(self, session_factory,
                                                params: dict[str, str]) -> None:
        await seed_recurring(session_factory)
        view = {"viewFrom": "2026-01-01", "viewTo": "2026-03-31"}
        async with http(session_factory) as client:
            base = await get(client, "/api/stocks/recurring-simulation/series", params)
            window = await get(client, "/api/stocks/recurring-simulation/series",
                               {**params, **view})
            table = await get(client, "/api/stocks/recurring-simulation",
                              {**params, "period": "daily"})
        assert dates(window) == DAYS_2026
        by_date = {p["date"]: p for p in window["points"]}
        for point in base["points"]:
            assert by_date[point["date"]] == point
        rows = day_rows(table)
        for day in set(DAYS_2026) - set(dates(base)):
            if day in rows:
                assert P(by_date[day]["returnRate"]) == P(rows[day]["returnRate"])
        assert all("principal" in p for p in window["points"])


@pytest.fixture
async def btc(session_factory) -> int:  # type: ignore[no-untyped-def]
    coin_id = await add_coin(session_factory)
    await seed_daily(session_factory, coin_id, "btc_2020_2021.json",
                     covered=(D("2020-01-01"), D("2021-12-31")))
    await seed_usd(session_factory, D("2019-12-01"), D("2022-12-31"))
    return coin_id


class Test가상자산:
    @pytest.mark.parametrize("path,extra", [
        ("/api/crypto/simulation/series", {"principal": "10000000"}),
        ("/api/crypto/recurring-simulation/series", {"amount": "100000", "frequency": "monthly"}),
    ], ids=["일시금", "적립식"])
    async def test_줄이지_않은_일봉_그대로다(self, session_factory, btc: int, path: str,
                                   extra: dict[str, str]) -> None:
        params = {"coinId": str(btc), "start": "2020-01-15", "principalCurrency": "KRW",
                  "end": "2021-12-31", **extra}
        view = {"viewFrom": "2021-01-01", "viewTo": "2021-03-31"}
        async with http(session_factory) as client:
            reduced = await get(client, path, {**params, "maxPoints": "100"})
            full = await get(client, path, {**params, "maxPoints": "5000"})
            window = await get(client, path, {**params, **view, "maxPoints": "100"})
        assert reduced["downsampled"] is True
        expected = [p for p in full["points"] if "2021-01-01" <= p["date"] <= "2021-03-31"]
        assert window["points"] == expected
        assert window["downsampled"] is False

    async def test_구간_점이_maxPoints보다_많으면_그_안에서_줄인다(self, session_factory,
                                                    btc: int) -> None:
        params = {"coinId": str(btc), "start": "2020-01-15", "principal": "10000000",
                  "principalCurrency": "KRW", "end": "2021-12-31",
                  "viewFrom": "2020-02-01", "viewTo": "2021-12-31", "maxPoints": "50"}
        async with http(session_factory) as client:
            window = await get(client, "/api/crypto/simulation/series", params)
        assert window["downsampled"] is True and len(window["points"]) == 50
        assert window["sourcePointCount"] > 50


class Test비교_경로:
    async def test_주식_비교는_메뉴_구간_시계열과_같고_현재_가치도_구간이다(
            self, session_factory) -> None:
        await seed_stocks(session_factory)
        params = {**KRX, **WINDOW, "maxPoints": "5000"}
        async with http(session_factory) as client:
            menu = await get(client, "/api/stocks/simulation/series", params)
            compare = await get(client, "/api/comparison/stocks/simulation", params)
        assert compare["series"] == menu
        line = compare["comparison"]["valueLine"]
        assert [v["date"] for v in line["points"]] == LUMP_DAYS
        basis = P(compare["summary"]["principal"])
        for value, point in zip(line["points"], menu["points"], strict=True):
            expected = basis * (1 + P(point["returnRate"]))
            assert abs(P(value["value"]) - expected) <= basis * P("0.000001")

    @pytest.mark.parametrize("path", ["/api/comparison/stocks/recurring-simulation"])
    async def test_적립식_비교도_구간이다(self, session_factory, path: str) -> None:
        await seed_recurring(session_factory)
        params = {**KRX_MONTHLY, "viewFrom": "2026-01-01", "viewTo": "2026-03-31",
                  "maxPoints": "5000"}
        async with http(session_factory) as client:
            menu = await get(client, "/api/stocks/recurring-simulation/series", params)
            compare = await get(client, path, params)
        assert compare["series"] == menu
        assert [v["date"] for v in compare["comparison"]["valueLine"]["points"]] == DAYS_2026

    async def test_가상자산_비교도_구간이다(self, session_factory, btc: int) -> None:
        params = {"coinId": str(btc), "start": "2020-01-15", "principal": "10000000",
                  "principalCurrency": "KRW", "end": "2021-12-31",
                  "viewFrom": "2021-01-01", "viewTo": "2021-01-31", "maxPoints": "5000"}
        async with http(session_factory) as client:
            menu = await get(client, "/api/crypto/simulation/series", params)
            compare = await get(client, "/api/comparison/crypto/simulation", params)
        assert compare["series"] == menu
        assert len(menu["points"]) == 31
        assert [v["date"] for v in compare["comparison"]["valueLine"]["points"]] == dates(menu)

    async def test_질의가_없으면_비교의_시계열은_지금과_같다(self, session_factory) -> None:
        await seed_stocks(session_factory)
        async with http(session_factory) as client:
            menu = await get(client, "/api/stocks/simulation/series", {**KRX, "maxPoints": "1000"})
            compare = await get(client, "/api/comparison/stocks/simulation", KRX)
        assert compare["series"] == menu
        assert "2021-09-02" not in dates(menu)


class Test잘못된_질의:
    @pytest.mark.parametrize("path", [
        "/api/stocks/simulation/series", "/api/comparison/stocks/simulation",
        "/api/stocks/recurring-simulation/series", "/api/comparison/stocks/recurring-simulation",
        "/api/crypto/simulation/series", "/api/comparison/crypto/simulation",
        "/api/crypto/recurring-simulation/series", "/api/comparison/crypto/recurring-simulation",
    ])
    @pytest.mark.parametrize("view", [{"viewFrom": "2021-08-01"}, {"viewTo": "2021-10-31"},
                                      {"viewFrom": "2021-10-31", "viewTo": "2021-08-01"}],
                             ids=["시작만", "끝만", "거꾸로"])
    async def test_400이다(self, session_factory, path: str, view: dict[str, str]) -> None:
        params = {**KRX, "amount": "1000000", "frequency": "monthly", "coinId": "1", **view}
        async with http(session_factory) as client:
            response = await client.get(path, params=params)
        assert response.status_code == 400, response.text
        assert response.json()["status"] == "invalid_query"
