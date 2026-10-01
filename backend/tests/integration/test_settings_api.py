"""수수료·세율 설정 API (T056) — 005 FR-015, FR-016, contracts/rest-api."""
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
        assert body["dividendTaxRate"] == "0.154000"  # 15.4%
        assert body["isDefault"] is True

    async def test_값이_문자열이다(self, client) -> None:
        """헌법 원칙 VI — JSON number는 경계에서 정밀도를 잃는다."""
        body = (await client.get("/api/stocks/settings")).json()
        assert isinstance(body["tradeFeeRate"], str)
        assert isinstance(body["dividendTaxRate"], str)


class Test변경:
    async def test_저장하고_다시_읽는다(self, client) -> None:
        res = await client.put("/api/stocks/settings", json={
            "tradeFeeRate": "0.000300", "dividendTaxRate": "0.220000"})
        assert res.status_code == 200
        body = (await client.get("/api/stocks/settings")).json()
        assert body["tradeFeeRate"] == "0.000300"
        assert body["dividendTaxRate"] == "0.220000"

    async def test_기본값과_다르면_isDefault가_거짓이다(self, client) -> None:
        """002 FR-033과 같은 규약 — 사용자가 기본값에서 벗어났음을 알아야 한다."""
        await client.put("/api/stocks/settings", json={
            "tradeFeeRate": "0.000300", "dividendTaxRate": "0.154000"})
        assert (await client.get("/api/stocks/settings")).json()["isDefault"] is False

    async def test_기본값으로_되돌리면_isDefault가_참이다(self, client) -> None:
        await client.put("/api/stocks/settings", json={
            "tradeFeeRate": "0.000300", "dividendTaxRate": "0.220000"})
        await client.put("/api/stocks/settings", json={
            "tradeFeeRate": "0.000150", "dividendTaxRate": "0.154000"})
        assert (await client.get("/api/stocks/settings")).json()["isDefault"] is True


class Test검증:
    @pytest.mark.parametrize("fee", ["-0.1", "1", "1.5"])
    async def test_범위_밖_수수료는_422다(self, client, fee: str) -> None:
        res = await client.put("/api/stocks/settings", json={
            "tradeFeeRate": fee, "dividendTaxRate": "0.154000"})
        assert res.status_code == 422
        assert res.json()["status"] == "invalid_setting"

    @pytest.mark.parametrize("tax", ["-0.1", "1", "2"])
    async def test_범위_밖_세율은_422다(self, client, tax: str) -> None:
        res = await client.put("/api/stocks/settings", json={
            "tradeFeeRate": "0.000150", "dividendTaxRate": tax})
        assert res.status_code == 422

    async def test_숫자가_아니면_422다(self, client) -> None:
        """조용히 0으로 떨어지면 수수료·세금이 사라지는데 오류가 없다."""
        res = await client.put("/api/stocks/settings", json={
            "tradeFeeRate": "공짜", "dividendTaxRate": "0.154000"})
        assert res.status_code == 422

    async def test_0은_허용한다(self, client) -> None:
        """수수료 0%는 현실적인 설정이고, 참조 구현과 대조할 때도 쓴다."""
        res = await client.put("/api/stocks/settings", json={
            "tradeFeeRate": "0", "dividendTaxRate": "0"})
        assert res.status_code == 200
