"""주식 매도 세금 설정 경로 (011 T051) — FR-035~FR-038, SC-007, contracts/rest-api §5.

- `GET /api/stocks/settings/sale-tax` — 세 값·`isDefault`·`defaults`. 기본값의 문자열은 010 반복 4의
  표 값과 같다
  (`"0.0020"`·`"0.22"`·`"2500000"`) — 기본 설정의 보드 응답이 바뀌지 않는다
- `PUT` — 세 키를 **모두** 받는다. 빠진 키를 기본값으로 채우지 않는다. 잘못된 값은 422
  `invalid_setting`이고 값이 그대로다
- 반영 — 일시금·적립식 보드의 `saleCost`가 그 값을 쓴다. 표·보유 중 `profit`은 그대로다(FR-038)
- 기본값을 보내면 응답이 처음과 같다(SC-007)
- 기존 `GET/PUT /api/stocks/settings`(수수료·배당 세율)는 그대로다
"""

from __future__ import annotations

from decimal import ROUND_FLOOR, Decimal

import pytest
from httpx2 import AsyncClient, Response

from tests.integration.stock_recurring_support import KRX_MONTHLY, app_for, client_for, seed

PATH = "/api/stocks/settings/sale-tax"
DEFAULTS = {"saleTaxRateDomestic": "0.0020", "capitalGainsRateForeign": "0.22",
            "capitalGainsDeductionForeign": "2500000"}
KRX_LUMP = {"market": "KRX", "symbol": "005930.KS", "start": "2026-01-01", "principal": "10000000",
            "principalCurrency": "KRW", "reinvest": "true", "end": "2026-03-03", "limit": "200"}
AAPL_LUMP = {**KRX_LUMP, "market": "NASDAQ", "symbol": "AAPL"}


def floor(x: Decimal) -> Decimal:
    return x.quantize(Decimal("1"), rounding=ROUND_FLOOR)


@pytest.fixture
async def client(session_factory):  # type: ignore[no-untyped-def]
    await seed(session_factory)
    async with client_for(app_for(session_factory)) as http:
        yield http


async def lump(client: AsyncClient, params: dict[str, str]) -> dict:  # type: ignore[type-arg]
    response = await client.get("/api/stocks/simulation", params=params)
    assert response.status_code == 200, response.text
    return response.json()  # type: ignore[no-any-return]


async def put(client: AsyncClient, **over: object) -> Response:
    return await client.put(PATH, json={**DEFAULTS, **over})


async def test_기본값은_010의_표_값과_같은_문자열이다(client: AsyncClient) -> None:
    body = (await client.get(PATH)).json()
    assert body == {**DEFAULTS, "isDefault": True, "defaults": DEFAULTS}


@pytest.mark.parametrize("missing", list(DEFAULTS))
async def test_세_키를_모두_받는다(client: AsyncClient, missing: str) -> None:
    payload = {k: v for k, v in DEFAULTS.items() if k != missing}
    response = await client.put(PATH, json=payload)
    assert (response.status_code, response.json()["status"]) == (422, "invalid_setting")
    assert (await client.get(PATH)).json()["isDefault"] is True


@pytest.mark.parametrize(("key", "value"), [
    ("saleTaxRateDomestic", "-0.1"), ("saleTaxRateDomestic", "1"), ("saleTaxRateDomestic", "abc"),
    ("saleTaxRateDomestic", None), ("capitalGainsRateForeign", "0.1234567"),
    ("capitalGainsRateForeign", "NaN"), ("capitalGainsDeductionForeign", "100.5"),
    ("capitalGainsDeductionForeign", "-1"), ("capitalGainsDeductionForeign", "1234567890123456"),
    ("capitalGainsDeductionForeign", None),
])
async def test_잘못된_값은_422이고_값이_그대로다(client: AsyncClient, key: str,
                                       value: object) -> None:
    response = await put(client, **{key: value})
    assert (response.status_code, response.json()["status"]) == (422, "invalid_setting")
    assert (await client.get(PATH)).json() == {**DEFAULTS, "isDefault": True, "defaults": DEFAULTS}


async def test_저장하면_DB_자릿수로_돌아오고_기본값이_아니다(client: AsyncClient) -> None:
    response = await put(client, saleTaxRateDomestic="0.0015", capitalGainsRateForeign="0.2",
                         capitalGainsDeductionForeign="0")
    assert response.status_code == 200
    expected = {"saleTaxRateDomestic": "0.001500", "capitalGainsRateForeign": "0.200000",
                "capitalGainsDeductionForeign": "0", "isDefault": False, "defaults": DEFAULTS}
    assert response.json() == expected
    assert (await client.get(PATH)).json() == expected


async def test_국내_매도_세율이_일시금_보드에_반영되고_보유_중_값은_그대로다(
        client: AsyncClient) -> None:
    before = await lump(client, KRX_LUMP)
    await put(client, saleTaxRateDomestic="0.0015")
    after = await lump(client, KRX_LUMP)
    sale = Decimal(after["rows"][0]["balance"])
    cost = after["summary"]["saleCost"]
    assert (cost["taxRate"], Decimal(cost["tax"])) == ("0.001500", floor(sale * Decimal("0.0015")))
    assert after["summary"]["profit"] == before["summary"]["profit"]
    assert after["rows"] == before["rows"]


async def test_국내_매도_세율이_적립식_보드에도_반영된다(client: AsyncClient) -> None:
    await put(client, saleTaxRateDomestic="0.0015")
    response = await client.get("/api/stocks/recurring-simulation",
                                params={**KRX_MONTHLY, "limit": "200"})
    assert response.status_code == 200, response.text
    summary = response.json()["summary"]
    assert summary["saleCost"]["taxRate"] == "0.001500"
    latest = next(r for r in response.json()["rows"] if r["date"] == summary["asOf"])
    expected = floor(Decimal(latest["balance"]) * Decimal("0.0015"))
    assert Decimal(summary["saleCost"]["tax"]) == expected


async def test_해외_공제를_0으로_하면_세금은_차익_곱하기_세율이다(client: AsyncClient) -> None:
    await put(client, capitalGainsDeductionForeign="0")
    cost = (await lump(client, AAPL_LUMP))["summary"]["saleCost"]
    assert cost["deduction"] == "0"
    assert Decimal(cost["tax"]) == floor(Decimal(cost["gain"]) * Decimal("0.22"))


async def test_기본값으로_되돌리면_응답이_처음과_같다(client: AsyncClient) -> None:
    before = (await lump(client, KRX_LUMP), await lump(client, AAPL_LUMP))
    await put(client, saleTaxRateDomestic="0.0015", capitalGainsRateForeign="0.3",
              capitalGainsDeductionForeign="0")
    await put(client)
    assert (await client.get(PATH)).json()["isDefault"] is True
    assert (await lump(client, KRX_LUMP), await lump(client, AAPL_LUMP)) == before


async def test_수수료·배당_세율_설정은_그대로다(client: AsyncClient) -> None:
    before = (await client.get("/api/stocks/settings")).json()
    await put(client, saleTaxRateDomestic="0.0015")
    after = (await client.get("/api/stocks/settings")).json()
    assert after == before
    assert set(after) == {"tradeFeeRate", "dividendTaxRateDomestic", "dividendTaxRateForeign",
                          "isDefault"}
