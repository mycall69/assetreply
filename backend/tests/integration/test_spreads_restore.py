"""`POST /api/fx/spreads/restore` (T046, T047).

FR-031: 기본값으로 되돌릴 수 있어야 한다.
FR-031a: 전 통화 복원 중 일부가 실패해도 **성공한 복원을 되돌리지 않는다.**
"""
from __future__ import annotations

from decimal import Decimal

import pytest
from httpx2 import ASGITransport, AsyncClient

from src.api.main import create_app
from src.db.session import get_session
from src.db.spread_defaults import DEFAULT_SPREADS
from src.repository.spread import update_spread

CHANGED = {
    "cash_buy": Decimal("0.0025"), "cash_sell": Decimal("0.0025"),
    "remit_send": Decimal("0.0009"), "remit_receive": Decimal("0.0009"),
}


@pytest.fixture
async def client(session_factory):
    async with session_factory() as s:
        for code in ("USD", "JPY", "EUR"):
            await update_spread(s, code, dict(CHANGED))
        await s.commit()

    app = create_app()

    async def _override():
        async with session_factory() as s:
            yield s

    app.dependency_overrides[get_session] = _override
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


async def test_통화_하나만_복원한다(client: AsyncClient) -> None:
    body = (await client.post("/api/fx/spreads/restore", json={"currency": "USD"})).json()
    assert body["restored"] == ["USD"]
    assert body["failed"] == []

    spreads = {r["currency"]: r for r in body["spreads"]}
    assert spreads["USD"]["isDefault"] is True
    assert spreads["JPY"]["isDefault"] is False


async def test_통화를_생략하면_전체를_복원한다(client: AsyncClient) -> None:
    body = (await client.post("/api/fx/spreads/restore", json={})).json()
    assert body["restored"] == ["USD", "JPY", "EUR"]
    assert all(r["isDefault"] for r in body["spreads"])


async def test_복원값이_단일_출처의_기본값과_일치한다(client: AsyncClient) -> None:
    """T047 — 시드와 복원이 값을 따로 들고 있으면 언젠가 어긋난다."""
    body = (await client.post("/api/fx/spreads/restore", json={"currency": "USD"})).json()
    usd = next(r for r in body["spreads"] if r["currency"] == "USD")
    expected = DEFAULT_SPREADS["USD"]
    assert Decimal(usd["cashBuy"]) == expected["cash_buy"]
    assert Decimal(usd["cashSell"]) == expected["cash_sell"]
    assert Decimal(usd["remitSend"]) == expected["remit_send"]
    assert Decimal(usd["remitReceive"]) == expected["remit_receive"]


async def test_지원하지_않는_통화는_404(client: AsyncClient) -> None:
    res = await client.post("/api/fx/spreads/restore", json={"currency": "KRW"})
    assert res.status_code == 404


async def test_실패_목록_필드가_항상_존재한다(client: AsyncClient) -> None:
    """FR-031a — 호출자가 `failed`의 길이로 판정한다."""
    body = (await client.post("/api/fx/spreads/restore", json={})).json()
    assert "failed" in body and isinstance(body["failed"], list)
