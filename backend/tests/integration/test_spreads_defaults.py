"""`GET /api/fx/spreads` 확장 (T045).

FR-027: 통화를 USD → JPY → EUR 순서로 제시한다. 이 순서는 고정이다.
FR-033: 현재 값이 기본값과 다른지 사용자가 알 수 있어야 한다.
"""
from __future__ import annotations

from decimal import Decimal

import pytest
from httpx2 import ASGITransport, AsyncClient

from src.api.main import create_app
from src.db.session import get_session
from src.repository.spread import update_spread


@pytest.fixture
async def client(session_factory):
    app = create_app()

    async def _override():
        async with session_factory() as s:
            yield s

    app.dependency_overrides[get_session] = _override
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


async def test_통화_순서가_고정된다(client: AsyncClient) -> None:
    body = (await client.get("/api/fx/spreads")).json()
    assert [r["currency"] for r in body["spreads"]] == ["USD", "JPY", "EUR"]


async def test_기본값을_함께_내려준다(client: AsyncClient) -> None:
    """FR-033 — 화면이 별도 조회 없이 차이를 표시할 수 있어야 한다."""
    body = (await client.get("/api/fx/spreads")).json()
    assert [r["currency"] for r in body["defaults"]] == ["USD", "JPY", "EUR"]
    usd = next(r for r in body["defaults"] if r["currency"] == "USD")
    assert usd["cashBuy"] == "0.001800"


async def test_초기에는_모두_기본값이다(client: AsyncClient) -> None:
    body = (await client.get("/api/fx/spreads")).json()
    assert all(r["isDefault"] for r in body["spreads"])


async def test_값을_바꾸면_기본값과_다름이_드러난다(
    client: AsyncClient, session_factory
) -> None:
    async with session_factory() as s:
        await update_spread(s, "USD", {
            "cash_buy": Decimal("0.0025"), "cash_sell": Decimal("0.0018"),
            "remit_send": Decimal("0.0005"), "remit_receive": Decimal("0.0005")})
        await s.commit()

    body = (await client.get("/api/fx/spreads")).json()
    usd = next(r for r in body["spreads"] if r["currency"] == "USD")
    jpy = next(r for r in body["spreads"] if r["currency"] == "JPY")
    assert usd["isDefault"] is False
    assert jpy["isDefault"] is True


async def test_비율이_문자열로_직렬화된다(client: AsyncClient) -> None:
    body = (await client.get("/api/fx/spreads")).json()
    assert isinstance(body["spreads"][0]["cashBuy"], str)
