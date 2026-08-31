"""`GET /api/fx/daily` 테스트 (T021, T022).

FR-020~026: 일자별 상세 표. 파생 환율 4종을 **서버가 산출해** 문자열로 내려준다.
브라우저에는 `Decimal`이 없어 클라이언트 계산은 곧 원칙 VI 위반이다 (research R2-5).

FR-021: 고시가 없는 날은 행을 만들지 않는다. 날짜가 연속하지 않는 것이 정상이다.
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

# 2026-08-15(토)·16(일)은 고시 없음 — 행이 생기면 안 된다
DAYS = ["2026-08-12", "2026-08-13", "2026-08-14", "2026-08-17", "2026-08-18"]


@pytest.fixture
async def client(session_factory):
    async with session_factory() as s:
        await upsert(s, FxRate, [
            {"currency_code": "USD", "quote_date": dt.date.fromisoformat(d),
             "base_rate": Decimal("1300.00") + Decimal(i), "quote_unit": 1,
             "source": "ECOS:731Y001", "is_provisional": False}
            for i, d in enumerate(DAYS)
        ])
        await upsert(s, FxCoverage, [
            {"currency_code": "USD", "covered_from": dt.date(2026, 8, 1),
             "covered_through": dt.date(2026, 8, 18)},
        ], preserve=())
        await s.commit()

    app = create_app()

    async def _override():
        async with session_factory() as s:
            yield s

    app.dependency_overrides[get_session] = _override
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


async def test_최신순으로_나열한다(client: AsyncClient) -> None:
    body = (await client.get("/api/fx/daily", params={"currency": "USD"})).json()
    dates = [r["date"] for r in body["rows"]]
    assert dates == sorted(dates, reverse=True)
    assert dates[0] == "2026-08-18"


async def test_고시_없는_날은_행을_만들지_않는다(client: AsyncClient) -> None:
    """FR-021 — 날짜가 연속하지 않는 것이 정상이다."""
    body = (await client.get("/api/fx/daily", params={"currency": "USD"})).json()
    dates = {r["date"] for r in body["rows"]}
    assert "2026-08-15" not in dates
    assert "2026-08-16" not in dates
    assert dates == set(DAYS)


async def test_파생_4종이_문자열로_반환된다(client: AsyncClient) -> None:
    """헌법 원칙 VI — 정밀도는 API 경계에서 지켜져야 한다."""
    body = (await client.get("/api/fx/daily", params={"currency": "USD"})).json()
    derived = body["rows"][0]["derived"]
    assert set(derived) == {"cashBuy", "cashSell", "remitSend", "remitReceive"}
    for value in derived.values():
        assert isinstance(value, str)
    assert isinstance(body["rows"][0]["baseRate"], str)


async def test_적용된_스프레드와_기준을_함께_내려준다(client: AsyncClient) -> None:
    """FR-024 — 파생값이 '현재 스프레드를 과거에 적용한 가정'임을 화면이 밝혀야 한다."""
    body = (await client.get("/api/fx/daily", params={"currency": "USD"})).json()
    assert body["spreadBasis"] == "current"
    assert set(body["appliedSpread"]) == {"cashBuy", "cashSell", "remitSend", "remitReceive"}


async def test_매입은_가산_매도는_차감된다(client: AsyncClient) -> None:
    body = (await client.get("/api/fx/daily", params={"currency": "USD"})).json()
    row = body["rows"][0]
    base = Decimal(row["baseRate"])
    assert Decimal(row["derived"]["cashBuy"]) > base
    assert Decimal(row["derived"]["cashSell"]) < base
    assert Decimal(row["derived"]["remitSend"]) > base
    assert Decimal(row["derived"]["remitReceive"]) < base


async def test_limit으로_행_수를_제한한다(client: AsyncClient) -> None:
    body = (await client.get("/api/fx/daily", params={"currency": "USD", "limit": 2})).json()
    assert len(body["rows"]) == 2
    assert body["hasMore"] is True
    assert body["oldestReturned"] == "2026-08-17"


async def test_before로_더_과거를_이어_받는다(client: AsyncClient) -> None:
    """FR-026."""
    first = (await client.get(
        "/api/fx/daily", params={"currency": "USD", "limit": 2})).json()
    more = (await client.get("/api/fx/daily", params={
        "currency": "USD", "limit": 2, "before": first["oldestReturned"]})).json()
    assert [r["date"] for r in more["rows"]] == ["2026-08-14", "2026-08-13"]


async def test_마지막_페이지는_hasMore가_거짓이다(client: AsyncClient) -> None:
    body = (await client.get(
        "/api/fx/daily", params={"currency": "USD", "limit": 50})).json()
    assert body["hasMore"] is False


async def test_잠정_행이_구분된다(session_factory) -> None:
    """FR-025."""
    async with session_factory() as s:
        await upsert(s, FxRate, [
            {"currency_code": "USD", "quote_date": dt.date(2026, 8, 30),
             "base_rate": Decimal("1354.20"), "quote_unit": 1,
             "source": "ECOS:731Y001", "is_provisional": True}])
        await s.commit()

    app = create_app()

    async def _override():
        async with session_factory() as s:
            yield s

    app.dependency_overrides[get_session] = _override
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        body = (await ac.get("/api/fx/daily", params={"currency": "USD"})).json()
    assert body["rows"][0]["isProvisional"] is True
