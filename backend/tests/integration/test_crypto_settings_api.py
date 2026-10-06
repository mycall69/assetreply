"""가상자산 거래 수수료율 (T026) — 007 FR-032, FR-033, SC-008, contracts/rest-api `GET`·`PUT
/api/crypto/settings`.

**주식 설정과 따로다**(FR-032) — 가상자산 거래소 수수료는 주식 증권사 수수료와 자릿수가 다르다.
기본값 0.1%. 바꾼 수수료는 다음 시뮬레이션에 쓰이고 조건에 보인다 — 결과를 저장하지 않으므로
무효화할 캐시가 없다(005 R5-9).
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


async def test_기본은_0_1퍼센트다(client) -> None:
    response = await client.get("/api/crypto/settings")
    assert response.status_code == 200
    assert response.json() == {"tradeFeeRate": "0.001000", "isDefault": True}


async def test_저장하면_기본값이_아니다(client) -> None:
    response = await client.put("/api/crypto/settings", json={"tradeFeeRate": "0.002"})
    assert response.status_code == 200
    assert response.json() == {"tradeFeeRate": "0.002000", "isDefault": False}
    assert (await client.get("/api/crypto/settings")).json()["tradeFeeRate"] == "0.002000"


async def test_기본값으로_되돌리면_기본이다(client) -> None:
    await client.put("/api/crypto/settings", json={"tradeFeeRate": "0.002"})
    response = await client.put("/api/crypto/settings", json={"tradeFeeRate": "0.001"})
    assert response.json() == {"tradeFeeRate": "0.001000", "isDefault": True}


@pytest.mark.parametrize("body", [
    {"tradeFeeRate": "-0.1"}, {"tradeFeeRate": "1"}, {"tradeFeeRate": "1.5"},
    {"tradeFeeRate": "abc"}, {}])
async def test_범위_밖이나_숫자가_아니면_422다(client, body: dict) -> None:
    response = await client.put("/api/crypto/settings", json=body)
    assert response.status_code == 422
    assert response.json()["status"] == "invalid_setting"
    assert (await client.get("/api/crypto/settings")).json()["isDefault"] is True


async def test_주식_설정과_따로다(client) -> None:
    before = (await client.get("/api/stocks/settings")).json()
    await client.put("/api/crypto/settings", json={"tradeFeeRate": "0.005"})
    assert (await client.get("/api/stocks/settings")).json() == before


async def test_바꾼_수수료가_다음_시뮬레이션에_쓰인다(session_factory, client) -> None:
    coin_id = await add_coin(session_factory)
    await seed_daily(session_factory, coin_id, "btc_2020_2021.json",
                     covered=(D("2020-01-01"), D("2021-12-31")))
    await seed_usd(session_factory, D("2019-12-01"), D("2022-12-31"))
    # 012 승인 2026-10-06 — 기본 단위가 일이라 첫 쪽에 매수 행이 없다. 월 단위로 받아 매수
    # 행(`buy`)을 찾는다.
    params = {"coinId": str(coin_id), "start": "2020-01-15", "principal": "10000",
              "principalCurrency": "USD", "end": "2021-12-31", "period": "monthly"}
    before = (await client.get("/api/crypto/simulation", params=params)).json()
    await client.put("/api/crypto/settings", json={"tradeFeeRate": "0.002"})
    after = (await client.get("/api/crypto/simulation", params=params)).json()
    assert (before["condition"]["tradeFeeRate"], after["condition"]["tradeFeeRate"]) == (
        "0.001000", "0.002000")
    [buy_before] = [r for r in before["rows"] if r["kind"] == "buy"]
    [buy_after] = [r for r in after["rows"] if r["kind"] == "buy"]
    assert buy_before["tradeFee"] != buy_after["tradeFee"]
    # 10,000 ÷ (7,196.39111328125 × 1.002) = 1.38681… → 1.38681… 8자리 버림 — 수수료가 크면 덜 산다
    assert buy_after["boughtQuantity"] < buy_before["boughtQuantity"]
