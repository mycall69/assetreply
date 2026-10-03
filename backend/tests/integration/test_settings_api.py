"""수수료·세율 설정 API (T056) — 005 FR-015, FR-016, contracts/rest-api.

006 FR-055(반복 2026-10-03 #3, T126) — 배당 소득세가 국내·해외 두 값이 되었다. 이 파일의 국내 세율
검사는 `dividendTaxRate` → `dividendTaxRateDomestic`으로 바뀌었고, 해외 세율은 아래
`Test해외_세율`이 본다.
"""
from __future__ import annotations

import pytest
from httpx2 import ASGITransport, AsyncClient

from src.api.main import create_app
from src.db.session import get_session


@pytest.fixture
async def client(session_factory):
    app = create_app()

    async def _override():
        async with session_factory() as s:
            yield s

    app.dependency_overrides[get_session] = _override
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


class Test기본값:
    async def test_저장한_적이_없으면_기본값이다(self, client) -> None:
        """행이 없을 때 조용히 0으로 떨어지면 수수료·세금이 없는 결과가 나온다."""
        body = (await client.get("/api/stocks/settings")).json()
        assert body["tradeFeeRate"] == "0.000150"  # 0.015%
        assert body["dividendTaxRateDomestic"] == "0.154000"  # 15.4%
        assert body["isDefault"] is True

    async def test_값이_문자열이다(self, client) -> None:
        """헌법 원칙 VI — JSON number는 경계에서 정밀도를 잃는다."""
        body = (await client.get("/api/stocks/settings")).json()
        assert isinstance(body["tradeFeeRate"], str)
        assert isinstance(body["dividendTaxRateDomestic"], str)


class Test변경:
    async def test_저장하고_다시_읽는다(self, client) -> None:
        res = await client.put("/api/stocks/settings", json={
            "tradeFeeRate": "0.000300", "dividendTaxRateDomestic": "0.220000",
            "dividendTaxRateForeign": "0.150000"})
        assert res.status_code == 200
        body = (await client.get("/api/stocks/settings")).json()
        assert body["tradeFeeRate"] == "0.000300"
        assert body["dividendTaxRateDomestic"] == "0.220000"

    async def test_기본값과_다르면_isDefault가_거짓이다(self, client) -> None:
        """002 FR-033과 같은 규약 — 사용자가 기본값에서 벗어났음을 알아야 한다."""
        await client.put("/api/stocks/settings", json={
            "tradeFeeRate": "0.000300", "dividendTaxRateDomestic": "0.154000",
            "dividendTaxRateForeign": "0.150000"})
        assert (await client.get("/api/stocks/settings")).json()["isDefault"] is False

    async def test_기본값으로_되돌리면_isDefault가_참이다(self, client) -> None:
        await client.put("/api/stocks/settings", json={
            "tradeFeeRate": "0.000300", "dividendTaxRateDomestic": "0.220000",
            "dividendTaxRateForeign": "0.150000"})
        await client.put("/api/stocks/settings", json={
            "tradeFeeRate": "0.000150", "dividendTaxRateDomestic": "0.154000",
            "dividendTaxRateForeign": "0.150000"})
        assert (await client.get("/api/stocks/settings")).json()["isDefault"] is True


class Test검증:
    @pytest.mark.parametrize("fee", ["-0.1", "1", "1.5"])
    async def test_범위_밖_수수료는_422다(self, client, fee: str) -> None:
        res = await client.put("/api/stocks/settings", json={
            "tradeFeeRate": fee, "dividendTaxRateDomestic": "0.154000",
            "dividendTaxRateForeign": "0.150000"})
        assert res.status_code == 422
        assert res.json()["status"] == "invalid_setting"

    @pytest.mark.parametrize("tax", ["-0.1", "1", "2"])
    async def test_범위_밖_세율은_422다(self, client, tax: str) -> None:
        res = await client.put("/api/stocks/settings", json={
            "tradeFeeRate": "0.000150", "dividendTaxRateDomestic": tax,
            "dividendTaxRateForeign": "0.150000"})
        assert res.status_code == 422

    async def test_숫자가_아니면_422다(self, client) -> None:
        """조용히 0으로 떨어지면 수수료·세금이 사라지는데 오류가 없다."""
        res = await client.put("/api/stocks/settings", json={
            "tradeFeeRate": "공짜", "dividendTaxRateDomestic": "0.154000",
            "dividendTaxRateForeign": "0.150000"})
        assert res.status_code == 422

    async def test_0은_허용한다(self, client) -> None:
        """수수료 0%는 현실적인 설정이고, 참조 구현과 대조할 때도 쓴다."""
        res = await client.put("/api/stocks/settings", json={
            "tradeFeeRate": "0", "dividendTaxRateDomestic": "0",
            "dividendTaxRateForeign": "0.150000"})
        assert res.status_code == 200


class Test해외_세율:
    """006 FR-055, SC-021 — 국내 15.4%·해외 15%가 기본이다(사용자 결정 2026-10-03)."""

    async def test_기본값이_15퍼센트다(self, client) -> None:
        body = (await client.get("/api/stocks/settings")).json()
        assert body["dividendTaxRateForeign"] == "0.150000"
        assert isinstance(body["dividendTaxRateForeign"], str)

    async def test_따로_저장된다(self, client) -> None:
        await client.put("/api/stocks/settings", json={
            "tradeFeeRate": "0.000150", "dividendTaxRateDomestic": "0.154000",
            "dividendTaxRateForeign": "0.100000"})
        body = (await client.get("/api/stocks/settings")).json()
        assert (body["dividendTaxRateDomestic"], body["dividendTaxRateForeign"]) == (
            "0.154000", "0.100000")
        assert body["isDefault"] is False

    async def test_해외_세율이_없으면_422다(self, client) -> None:
        """조용히 기본값으로 채우면 사용자가 넣지 않은 값으로 계산된다."""
        res = await client.put("/api/stocks/settings", json={
            "tradeFeeRate": "0.000150", "dividendTaxRateDomestic": "0.154000"})
        assert res.status_code == 422

    @pytest.mark.parametrize("tax", ["-0.1", "1"])
    async def test_범위_밖_해외_세율은_422다(self, client, tax: str) -> None:
        res = await client.put("/api/stocks/settings", json={
            "tradeFeeRate": "0.000150", "dividendTaxRateDomestic": "0.154000",
            "dividendTaxRateForeign": tax})
        assert res.status_code == 422

