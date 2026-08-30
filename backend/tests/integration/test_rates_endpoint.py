"""`GET /api/fx/rates` · `/api/fx/coverage` 엔드포인트 테스트 (T053, T054).

contracts/rest-api.md 응답 규약 — 금액은 **문자열**로 직렬화한다.
"""
from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest
from httpx2 import ASGITransport, AsyncClient

from src.api.main import create_app
from src.db.dialect import upsert
from src.db.models import FxCoverage, FxRate
from src.db.session import get_session


@pytest.fixture
async def client(session_factory):
    async with session_factory() as s:
        await upsert(s, FxRate, [
            {"currency_code": "USD", "quote_date": dt.date(2005, 3, 15),
             "base_rate": Decimal("1012.30"), "quote_unit": 1, "source": "ECOS:731Y001"},
            {"currency_code": "USD", "quote_date": dt.date(2005, 3, 18),
             "base_rate": Decimal("1010.90"), "quote_unit": 1, "source": "ECOS:731Y001"},
            {"currency_code": "JPY", "quote_date": dt.date(2020, 6, 15),
             "base_rate": Decimal("1102.45"), "quote_unit": 100, "source": "ECOS:731Y001"},
        ])
        await upsert(s, FxCoverage, [
            {"currency_code": "USD", "covered_from": dt.date(2005, 3, 1),
             "covered_through": dt.date(2005, 3, 31)},
            {"currency_code": "JPY", "covered_from": dt.date(2020, 6, 1),
             "covered_through": dt.date(2020, 6, 30)},
        ], preserve=())
        await s.commit()

    app = create_app()

    async def _override():
        async with session_factory() as s:
            yield s

    app.dependency_overrides[get_session] = _override
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def test_고시_있는_날_응답(client: AsyncClient) -> None:
    body = (await client.get("/api/fx/rates/USD", params={"date": "2005-03-15"})).json()
    assert body["status"] == "quoted"
    assert body["baseRate"] == "1012.300000"
    assert body["quoteUnit"] == 1
    assert body["source"] == "ECOS:731Y001"


async def test_금액이_문자열로_직렬화된다(client: AsyncClient) -> None:
    """JSON number는 배정밀도라 Decimal 정밀도가 손실된다 (헌법 원칙 VI)."""
    body = (await client.get("/api/fx/rates/USD", params={"date": "2005-03-15"})).json()
    assert isinstance(body["baseRate"], str)


async def test_고시_없는_날_응답(client: AsyncClient) -> None:
    """FR-018a: 최상위에 baseRate가 없고 참고는 reference 안에만 있다."""
    body = (await client.get("/api/fx/rates/USD", params={"date": "2005-03-19"})).json()
    assert body["status"] == "no_quote"
    assert "baseRate" not in body
    assert body["reference"]["date"] == "2005-03-18"
    assert "2005-03-19" in body["reference"]["note"]


async def test_JPY_단위가_100이다(client: AsyncClient) -> None:
    body = (await client.get("/api/fx/rates/JPY", params={"date": "2020-06-15"})).json()
    assert body["quoteUnit"] == 100


async def test_지원하지_않는_통화는_404(client: AsyncClient) -> None:
    res = await client.get("/api/fx/rates/GBP", params={"date": "2005-03-15"})
    assert res.status_code == 404
    assert res.json()["status"] == "unknown_currency"


async def test_범위_밖은_400(client: AsyncClient) -> None:
    res = await client.get("/api/fx/rates/USD", params={"date": "2004-01-01"})
    assert res.status_code == 400
    assert res.json()["status"] == "out_of_range"


async def test_소문자_통화도_받는다(client: AsyncClient) -> None:
    res = await client.get("/api/fx/rates/usd", params={"date": "2005-03-15"})
    assert res.status_code == 200


async def test_커버리지_조회(client: AsyncClient) -> None:
    body = (await client.get("/api/fx/coverage")).json()
    codes = {c["currency"] for c in body["coverage"]}
    assert {"USD", "JPY"} <= codes
    usd = next(c for c in body["coverage"] if c["currency"] == "USD")
    assert usd["coveredFrom"] == "2005-03-01"
    assert usd["coveredThrough"] == "2005-03-31"


class Test파생_환율:
    """FR-022·FR-026a — 조회 결과에 파생 환율과 적용된 스프레드가 함께 담긴다."""

    async def test_파생_환율_4종이_포함된다(self, client: AsyncClient) -> None:
        body = (await client.get("/api/fx/rates/USD", params={"date": "2005-03-15"})).json()
        assert set(body["derived"]) == {"cashBuy", "cashSell", "remitSend", "remitReceive"}

    async def test_참조값과_일치한다(self, client: AsyncClient) -> None:
        """기본 스프레드(USD 현금 0.0018 / 송금 0.0005) 기준 손계산값."""
        body = (await client.get("/api/fx/rates/USD", params={"date": "2005-03-15"})).json()
        assert body["derived"]["cashBuy"] == "1014.12"
        assert body["derived"]["cashSell"] == "1010.48"
        assert body["derived"]["remitSend"] == "1012.81"
        assert body["derived"]["remitReceive"] == "1011.79"

    async def test_적용된_스프레드가_함께_온다(self, client: AsyncClient) -> None:
        """FR-026a: 어떤 가정 위의 결과인지 드러나야 한다."""
        body = (await client.get("/api/fx/rates/USD", params={"date": "2005-03-15"})).json()
        assert body["appliedSpread"]["cashBuy"] == "0.001800"

    async def test_현재_스프레드_기준임을_밝힌다(self, client: AsyncClient) -> None:
        """FR-026: 시점별 이력이 아니라 현재 설정값을 과거에 적용한 가정 비교."""
        body = (await client.get("/api/fx/rates/USD", params={"date": "2005-03-15"})).json()
        assert body["spreadBasis"] == "current"

    async def test_고시_없는_날에는_파생_환율이_없다(self, client: AsyncClient) -> None:
        """FR-018a: 참고 영역에 파생 환율 4종을 표시하지 않는다."""
        body = (await client.get("/api/fx/rates/USD", params={"date": "2005-03-19"})).json()
        assert "derived" not in body
        assert "derived" not in (body.get("reference") or {})

    async def test_스프레드_변경이_조회_결과에_반영된다(self, client: AsyncClient) -> None:
        await client.put("/api/fx/spreads/USD", json={
            "cashBuy": "0.005", "cashSell": "0.005",
            "remitSend": "0.001", "remitReceive": "0.001"})
        body = (await client.get("/api/fx/rates/USD", params={"date": "2005-03-15"})).json()
        # 1012.30 × 1.005 = 1017.3615 → 1017.36
        assert body["derived"]["cashBuy"] == "1017.36"
        assert body["baseRate"] == "1012.300000", "매매기준율은 변하지 않아야 한다"
