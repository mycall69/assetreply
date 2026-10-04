"""예금 이자 소득세율 (T023) — 008 FR-030, FR-031, SC-008, contracts/rest-api `GET`·`PUT
/api/deposit/settings`.

**주식·가상자산 설정과 따로다**(FR-030) — 기본값은 배당 소득세율과 같은 15.4%지만 한쪽을 바꿀 때
다른 쪽이 따라 바뀌면 안 된다. 바꾼 세율은 다음 시뮬레이션에 쓰이고 조건에 보인다 — 결과를 저장하지
않으므로 무효화할 캐시가 없다(005 R5-9).
"""
from __future__ import annotations

import pytest
from httpx2 import ASGITransport, AsyncClient

from src.api.main import create_app
from src.db.session import get_session
from tests.integration.deposit_support import TODAY, seed_rates

PARAMS = {"institution": "commercial_bank", "start": "2020-01-15", "principal": "10000000"}


@pytest.fixture
async def client(session_factory, monkeypatch):  # type: ignore[no-untyped-def]
    monkeypatch.setattr("src.api.services.deposit_simulation.kst_today", lambda: TODAY)
    app = create_app()

    async def _session():  # type: ignore[no-untyped-def]
        async with session_factory() as s:
            yield s

    app.dependency_overrides[get_session] = _session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        yield c


async def test_기본은_15_4퍼센트다(client) -> None:  # type: ignore[no-untyped-def]
    response = await client.get("/api/deposit/settings")
    assert response.status_code == 200
    assert response.json() == {"interestTaxRate": "0.154000", "isDefault": True}


async def test_저장하면_기본값이_아니고_되돌리면_기본이다(client) -> None:  # type: ignore[no-untyped-def]
    response = await client.put("/api/deposit/settings", json={"interestTaxRate": "0.095"})
    assert response.status_code == 200
    assert response.json() == {"interestTaxRate": "0.095000", "isDefault": False}
    assert (await client.get("/api/deposit/settings")).json()["interestTaxRate"] == "0.095000"
    back = await client.put("/api/deposit/settings", json={"interestTaxRate": "0.154"})
    assert back.json() == {"interestTaxRate": "0.154000", "isDefault": True}


@pytest.mark.parametrize("body", [
    {"interestTaxRate": "-0.01"}, {"interestTaxRate": "1"}, {"interestTaxRate": "1.5"},
    {"interestTaxRate": "abc"}, {"interestTaxRate": "NaN"}, {"interestTaxRate": 0.1}, {}])
async def test_범위_밖이나_숫자_문자열이_아니면_422다(client, body: dict) -> None:  # type: ignore[no-untyped-def,type-arg]
    response = await client.put("/api/deposit/settings", json=body)
    assert response.status_code == 422
    assert response.json()["status"] == "invalid_setting"
    assert (await client.get("/api/deposit/settings")).json()["isDefault"] is True


async def test_소수_6자리를_넘는_세율은_422다(client) -> None:  # type: ignore[no-untyped-def]
    """저장 자릿수(비율 소수 6자리)를 넘으면 조용히 반올림되어 넣은 세율과 달라진다(FR-030, 반복
    #2)."""
    response = await client.put("/api/deposit/settings", json={"interestTaxRate": "0.1234567"})
    assert response.status_code == 422
    assert response.json()["status"] == "invalid_setting"
    assert (await client.get("/api/deposit/settings")).json()["isDefault"] is True
    saved = await client.put("/api/deposit/settings", json={"interestTaxRate": "0.123456"})
    assert saved.json() == {"interestTaxRate": "0.123456", "isDefault": False}


async def test_주식·가상자산_설정과_따로다(client) -> None:  # type: ignore[no-untyped-def]
    stocks = (await client.get("/api/stocks/settings")).json()
    crypto = (await client.get("/api/crypto/settings")).json()
    await client.put("/api/deposit/settings", json={"interestTaxRate": "0.05"})
    assert (await client.get("/api/stocks/settings")).json() == stocks
    assert (await client.get("/api/crypto/settings")).json() == crypto


async def test_바꾼_세율이_다음_시뮬레이션에_쓰인다(client, session_factory) -> None:  # type: ignore[no-untyped-def]
    """회차 1 이자 162,000 — 15.4%면 세금 24,948, 9.5%면 15,390(0 쪽 절사)."""
    await seed_rates(session_factory)
    before = (await client.get("/api/deposit/simulation", params=PARAMS)).json()
    await client.put("/api/deposit/settings", json={"interestTaxRate": "0.095"})
    after = (await client.get("/api/deposit/simulation", params=PARAMS)).json()
    assert (before["condition"]["interestTaxRate"], after["condition"]["interestTaxRate"]) == (
        "0.154000", "0.095000")
    assert (before["terms"][0]["tax"], after["terms"][0]["tax"]) == ("24948", "15390")
    assert int(after["summary"]["profit"]) > int(before["summary"]["profit"])


async def test_세율_0이면_세금_열이_모두_0이다(client, session_factory) -> None:  # type: ignore[no-untyped-def]
    """SC-008 — 세후 이자 = 이자. 되돌리면 처음 결과와 같다."""
    await seed_rates(session_factory)
    first = (await client.get("/api/deposit/simulation", params=PARAMS)).json()
    await client.put("/api/deposit/settings", json={"interestTaxRate": "0"})
    zero = (await client.get("/api/deposit/simulation", params=PARAMS)).json()
    assert all(r["tax"] == "0" and r["afterTax"] == r["interest"] for r in zero["rows"])
    await client.put("/api/deposit/settings", json={"interestTaxRate": "0.154"})
    assert (await client.get("/api/deposit/simulation", params=PARAMS)).json() == first
