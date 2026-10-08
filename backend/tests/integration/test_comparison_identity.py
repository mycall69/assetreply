"""비교 경로 넷 ↔ 메뉴 경로 (013 T010) — FR-005, FR-008, FR-009, FR-011, FR-020, SC-001,
SC-002, SC-007, contracts/rest-api.md 1.

비교 경로는 메뉴 경로와 **같은 함수를 같은 차례로** 부른다(research R13-1). 그래서 같은 질의면
`summary`·`condition`이 같고, `series`는 같은 `maxPoints`의 메뉴 `/series`와 같으며, 202·거절 본문도
같다. 비교 경로는 이력을 쓰지 않는다. 표가 없으므로 `rows`·`terms`가 없다.
"""

from __future__ import annotations

import datetime as dt

import pytest

from src.api.services import realestate_lists
from src.db.session import get_session
from tests.integration.apt_support import FakePortal
from tests.integration.comparison_support import (
    AAPL_KRW,
    AAPL_USD,
    EMPTY,
    KRX,
    NEWCO,
    both,
    history_rows,
    http,
    seed_stocks,
)
from tests.integration.crypto_support import add_coin, seed_daily, seed_usd
from tests.integration.deposit_support import TODAY, seed_rates
from tests.integration.test_realestate_simulation_api import Api

D = dt.date.fromisoformat
COMPARE_KEYS = {"basisCurrency", "target", "condition", "exchange", "summary", "series",
                "comparison"}


def assert_same(table, series, compare) -> dict:  # type: ignore[no-untyped-def]
    assert table.status_code == 200, table.text
    assert series.status_code == 200, series.text
    assert compare.status_code == 200, compare.text
    body = compare.json()
    menu = table.json()
    assert set(body) == COMPARE_KEYS
    assert body["summary"] == menu["summary"]
    assert body["condition"] == menu["condition"]
    assert body["exchange"] == menu.get("exchange")
    assert body["series"] == series.json()
    assert body["basisCurrency"] == "KRW"
    assert "rows" not in body and "terms" not in body
    return body  # type: ignore[no-any-return]


class Test주식_일시금:
    async def test_국내_종목은_메뉴와_같다(self, session_factory) -> None:
        await seed_stocks(session_factory)
        async with http(session_factory) as client:
            body = assert_same(*await both(client, "/api/stocks/simulation", KRX))
        assert body["target"] == {"market": "KRX", "symbol": "005930.KS", "name": "삼성전자",
                                  "currency": "KRW"}

    @pytest.mark.parametrize("params", [AAPL_USD, AAPL_KRW], ids=["USD", "KRW"])
    async def test_해외_종목은_메뉴와_같다(self, session_factory,
                                   params: dict[str, str]) -> None:
        await seed_stocks(session_factory)
        async with http(session_factory) as client:
            body = assert_same(*await both(client, "/api/stocks/simulation", params))
        assert body["target"]["currency"] == "USD"

    async def test_시계열은_처음_값이_1000점이다(self, session_factory) -> None:
        await seed_stocks(session_factory)
        async with http(session_factory) as client:
            compare = await client.get("/api/comparison/stocks/simulation", params=KRX)
            menu = await client.get("/api/stocks/simulation/series",
                                    params={**KRX, "maxPoints": "1000"})
        assert compare.json()["series"] == menu.json()

    async def test_받지_않은_종목은_같은_202다(self, session_factory) -> None:
        await seed_stocks(session_factory)
        async with http(session_factory) as client:
            menu = await client.get("/api/stocks/simulation", params=EMPTY)
            compare = await client.get("/api/comparison/stocks/simulation", params=EMPTY)
        assert (menu.status_code, compare.status_code) == (202, 202)
        assert compare.json() == menu.json()

    async def test_시세_시작_전은_같은_거절이다(self, session_factory) -> None:
        await seed_stocks(session_factory)
        async with http(session_factory) as client:
            menu = await client.get("/api/stocks/simulation", params=NEWCO)
            compare = await client.get("/api/comparison/stocks/simulation", params=NEWCO)
        assert (menu.status_code, compare.status_code) == (400, 400)
        assert compare.json() == menu.json()
        assert compare.json()["status"] == "before_listing"

    async def test_이력을_쓰지_않는다(self, session_factory) -> None:
        await seed_stocks(session_factory)
        before = await history_rows(session_factory)
        async with http(session_factory) as client:
            await client.get("/api/comparison/stocks/simulation", params=KRX)
        assert await history_rows(session_factory) == before == 0


@pytest.fixture
async def btc(session_factory) -> int:  # type: ignore[no-untyped-def]
    coin_id = await add_coin(session_factory)
    await seed_daily(session_factory, coin_id, "btc_2020_2021.json",
                     covered=(D("2020-01-01"), D("2021-12-31")))
    await seed_usd(session_factory, D("2019-12-01"), D("2022-12-31"))
    return coin_id


def coin(coin_id: int, **over: str) -> dict[str, str]:
    base = {"coinId": str(coin_id), "start": "2020-01-15", "principal": "10000000",
            "principalCurrency": "KRW", "end": "2021-12-31"}
    base.update(over)
    return base


class Test가상자산_일시금:
    @pytest.mark.parametrize("currency", ["KRW", "USD"])
    async def test_메뉴와_같다(self, session_factory, btc: int, currency: str) -> None:
        async with http(session_factory) as client:
            params = coin(btc, principalCurrency=currency,
                          principal="10000000" if currency == "KRW" else "10000")
            body = assert_same(*await both(client, "/api/crypto/simulation", params))
        assert body["target"]["coinId"] == btc

    async def test_받지_않은_코인은_같은_202다(self, session_factory) -> None:
        coin_id = await add_coin(session_factory)
        await seed_usd(session_factory, D("2019-12-01"), D("2022-12-31"))
        async with http(session_factory) as client:
            menu = await client.get("/api/crypto/simulation", params=coin(coin_id))
            compare = await client.get("/api/comparison/crypto/simulation", params=coin(coin_id))
        assert (menu.status_code, compare.status_code) == (202, 202)
        assert compare.json() == menu.json()

    @pytest.mark.parametrize(("first", "coin_id", "status", "code"), [
        (D("2020-06-01"), None, 400, "before_listing"),
        (None, 987654, 404, "unknown_coin"),
    ], ids=["before_listing", "unknown_coin"])
    async def test_같은_거절이다(self, session_factory, first: dt.date | None,
                           coin_id: int | None, status: int, code: str) -> None:
        added = await add_coin(session_factory, first_available=first)
        target = coin_id or added
        async with http(session_factory) as client:
            menu = await client.get("/api/crypto/simulation", params=coin(target))
            compare = await client.get("/api/comparison/crypto/simulation", params=coin(target))
        assert (menu.status_code, compare.status_code) == (status, status)
        assert compare.json() == menu.json()
        assert compare.json()["status"] == code


DEPOSIT = {"institution": "commercial_bank", "start": "2020-01-15", "principal": "10000000"}


@pytest.fixture
def deposit_today(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr("src.api.services.deposit_simulation.kst_today", lambda: TODAY)


class Test정기예금:
    async def test_메뉴와_같다(self, session_factory, deposit_today: None) -> None:
        await seed_rates(session_factory)
        async with http(session_factory) as client:
            body = assert_same(*await both(client, "/api/deposit/simulation", DEPOSIT))
        assert body["target"] == {"key": "commercial_bank", "name": "시중은행"}

    async def test_받지_않았으면_같은_202다(self, session_factory, deposit_today: None) -> None:
        async with http(session_factory) as client:
            menu = await client.get("/api/deposit/simulation", params=DEPOSIT)
            compare = await client.get("/api/comparison/deposit/simulation", params=DEPOSIT)
        assert (menu.status_code, compare.status_code) == (202, 202)
        assert compare.json() == menu.json()

    async def test_금리_시작_전은_같은_거절이다(self, session_factory,
                                      deposit_today: None) -> None:
        await seed_rates(session_factory)
        early = {**DEPOSIT, "start": "2001-01-15"}
        async with http(session_factory) as client:
            menu = await client.get("/api/deposit/simulation", params=early)
            compare = await client.get("/api/comparison/deposit/simulation", params=early)
        assert (menu.status_code, compare.status_code) == (409, 409)
        assert compare.json() == menu.json()
        assert compare.json()["status"] == "before_first_month"


@pytest.fixture
async def apt(session_factory):  # type: ignore[no-untyped-def]
    """부동산 메뉴 테스트와 같은 준비 — 가짜 공공데이터포털, 고정된 지금·설정."""
    from httpx2 import ASGITransport, AsyncClient

    from src.api.main import create_app

    portal = FakePortal()
    app = create_app()

    async def _session():  # type: ignore[no-untyped-def]
        async with session_factory() as s:
            yield s

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        holder = Api(client, portal, session_factory)
        app.dependency_overrides[get_session] = _session
        app.dependency_overrides[realestate_lists.get_realestate_now] = lambda: holder.now
        app.dependency_overrides[realestate_lists.get_realestate_settings] = (
            lambda: holder.settings)
        app.dependency_overrides[realestate_lists.get_realestate_source] = lambda: holder.source
        yield holder


class Test부동산:
    async def test_메뉴와_같다(self, apt: Api) -> None:
        names = await apt.collected()
        params = {"complexId": str(names["헬리오시티아파트"]), "area": "30k",
                  "buyDate": "2021-03-15"}
        body = assert_same(*await both(apt.http, "/api/realestate/simulation", params))
        assert body["target"] == {
            "complex": {"complexId": names["헬리오시티아파트"], "name": "헬리오시티아파트",
                        "umdName": "가락동"},
            "area": {"key": "30k", "label": "30평대(국평)"}}
        assert "acquisition" not in body

    async def test_받지_않은_시군구는_같은_202다(self, apt: Api) -> None:
        await apt.regions()
        items = (await apt.complexes())["items"]
        helio = next(i["complexId"] for i in items  # type: ignore[union-attr]
                     if i["name"] == "헬리오시티아파트")  # type: ignore[index]
        params = {"complexId": str(helio), "area": "30k", "buyDate": "2021-03-15"}
        menu = await apt.simulate(**params)
        compare = await apt.get("/api/comparison/realestate/simulation", **params)
        assert (menu.status_code, compare.status_code) == (202, 202)
        assert compare.json() == menu.json()

    async def test_첫_거래_전은_같은_거절이다(self, apt: Api) -> None:
        names = await apt.collected()
        params = {"complexId": str(names["헬리오시티아파트"]), "area": "30k",
                  "buyDate": "2020-01-15"}
        menu = await apt.simulate(**params)
        compare = await apt.get("/api/comparison/realestate/simulation", **params)
        assert (menu.status_code, compare.status_code) == (409, 409)
        assert compare.json() == menu.json()
        assert compare.json()["status"] == "before_first_trade"

    async def test_매입가를_받지_않는다(self, apt: Api) -> None:
        names = await apt.collected()
        response = await apt.get("/api/comparison/realestate/simulation",
                                 complexId=str(names["헬리오시티아파트"]), area="30k",
                                 buyDate="2021-03-15", buyPrice="1500000000")
        assert response.status_code == 400
        assert response.json()["status"] == "invalid_query"

    async def test_이력을_쓰지_않는다(self, apt: Api) -> None:
        names = await apt.collected()
        await apt.get("/api/comparison/realestate/simulation",
                      complexId=str(names["헬리오시티아파트"]), area="30k", buyDate="2021-03-15")
        assert await history_rows(apt.session_factory) == 0
