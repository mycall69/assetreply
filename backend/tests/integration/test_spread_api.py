"""스프레드 설정 API 테스트 (T063).

FR-021: 통화별 4종 스프레드를 설정할 수 있다.
FR-024: 설정하지 않은 통화에 기본 스프레드를 적용한다.
FR-025: 허용 범위를 벗어난 값은 거부하고 기존 값을 유지한다.
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


VALID = {"cashBuy": "0.0025", "cashSell": "0.0025",
         "remitSend": "0.0008", "remitReceive": "0.0008"}


async def test_기본_스프레드가_시드되어_있다(client: AsyncClient) -> None:
    body = (await client.get("/api/fx/spreads")).json()
    by_code = {s["currency"]: s for s in body["spreads"]}
    assert by_code["USD"]["cashBuy"] == "0.001800"
    assert by_code["USD"]["remitSend"] == "0.000500"
    assert by_code["JPY"]["cashBuy"] == "0.002000"


async def test_비율이_문자열로_직렬화된다(client: AsyncClient) -> None:
    body = (await client.get("/api/fx/spreads")).json()
    assert all(isinstance(s["cashBuy"], str) for s in body["spreads"])


async def test_스프레드를_변경한다(client: AsyncClient) -> None:
    res = await client.put("/api/fx/spreads/USD", json=VALID)
    assert res.status_code == 200
    body = (await client.get("/api/fx/spreads")).json()
    usd = next(s for s in body["spreads"] if s["currency"] == "USD")
    assert usd["cashBuy"] == "0.002500"


@pytest.mark.parametrize("bad", ["-0.1", "1", "1.5", "-0.0001"])
async def test_허용_범위를_벗어나면_422(client: AsyncClient, bad: str) -> None:
    res = await client.put("/api/fx/spreads/USD", json={**VALID, "cashBuy": bad})
    assert res.status_code == 422
    assert res.json()["status"] == "invalid_spread"


async def test_거부되면_기존_값이_유지된다(client: AsyncClient) -> None:
    before = (await client.get("/api/fx/spreads")).json()
    await client.put("/api/fx/spreads/USD", json={**VALID, "cashBuy": "-0.1"})
    after = (await client.get("/api/fx/spreads")).json()
    assert before == after


async def test_0은_허용된다(client: AsyncClient) -> None:
    """스프레드 0은 유효한 경계값이다."""
    res = await client.put("/api/fx/spreads/USD", json={k: "0" for k in VALID})
    assert res.status_code == 200


async def test_지원하지_않는_통화는_404(client: AsyncClient) -> None:
    res = await client.put("/api/fx/spreads/GBP", json=VALID)
    assert res.status_code == 404
