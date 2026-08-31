"""`GET /api/fx/latest` 테스트 (T019, T020).

FR-011: 요약은 오늘 잠정값이 있으면 그것을, 없으면 마지막 확정값을 제시한다.
FR-013: 변화량을 절대값과 백분율로 함께 제시하고 방향을 값으로 내려준다 — 색에만
의존하면 색각 이상 사용자가 구분할 수 없다.
FR-014: 잠정인지 확정인지 구별할 수 있어야 한다.
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

CONFIRMED_1 = dt.date(2026, 8, 28)
CONFIRMED_2 = dt.date(2026, 8, 29)
TODAY = dt.date(2026, 8, 30)


async def _make_client(session_factory, rows, coverage=True):
    async with session_factory() as s:
        if rows:
            await upsert(s, FxRate, rows)
        if coverage:
            await upsert(s, FxCoverage, [
                {"currency_code": "USD", "covered_from": dt.date(2026, 8, 1),
                 "covered_through": CONFIRMED_2},
            ], preserve=())
        await s.commit()

    app = create_app()

    async def _override():
        async with session_factory() as s:
            yield s

    app.dependency_overrides[get_session] = _override
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def _row(day: dt.date, rate: str, *, provisional: bool = False) -> dict[str, object]:
    return {"currency_code": "USD", "quote_date": day, "base_rate": Decimal(rate),
            "quote_unit": 1, "source": "ECOS:731Y001", "is_provisional": provisional}


@pytest.fixture
async def client_confirmed(session_factory):
    ac = await _make_client(session_factory, [
        _row(CONFIRMED_1, "1360.00"), _row(CONFIRMED_2, "1356.10")])
    async with ac:
        yield ac


@pytest.fixture
async def client_provisional(session_factory):
    ac = await _make_client(session_factory, [
        _row(CONFIRMED_1, "1360.00"),
        _row(CONFIRMED_2, "1356.10"),
        _row(TODAY, "1354.20", provisional=True)])
    async with ac:
        yield ac


async def test_마지막_확정값을_제시한다(client_confirmed: AsyncClient) -> None:
    body = (await client_confirmed.get("/api/fx/latest", params={"currency": "USD"})).json()
    assert body["date"] == CONFIRMED_2.isoformat()
    assert body["baseRate"] == "1356.100000"
    assert body["isProvisional"] is False
    assert body["quotePair"] == "USD/KRW"
    assert body["quoteUnit"] == 1


async def test_금액이_문자열로_직렬화된다(client_confirmed: AsyncClient) -> None:
    """헌법 원칙 VI: JSON number는 배정밀도라 Decimal 정밀도가 손실된다."""
    body = (await client_confirmed.get("/api/fx/latest", params={"currency": "USD"})).json()
    assert isinstance(body["baseRate"], str)
    assert isinstance(body["change"]["absolute"], str)
    assert isinstance(body["change"]["percent"], str)


async def test_직전_고시일_대비_변화량(client_confirmed: AsyncClient) -> None:
    body = (await client_confirmed.get("/api/fx/latest", params={"currency": "USD"})).json()
    change = body["change"]
    assert change["comparedTo"] == CONFIRMED_1.isoformat()
    assert Decimal(change["absolute"]) == Decimal("-3.90")
    assert change["direction"] == "down"


async def test_방향을_값으로_내려준다(client_confirmed: AsyncClient) -> None:
    """FR-013: 색에만 의존하지 않도록 방향이 데이터에 있어야 한다."""
    body = (await client_confirmed.get("/api/fx/latest", params={"currency": "USD"})).json()
    assert body["change"]["direction"] in ("up", "down", "flat")


async def test_오늘_잠정값이_있으면_그것을_제시한다(client_provisional: AsyncClient) -> None:
    """FR-011 + FR-014."""
    body = (await client_provisional.get("/api/fx/latest", params={"currency": "USD"})).json()
    assert body["date"] == TODAY.isoformat()
    assert body["isProvisional"] is True
    assert body["fetchedAt"] is not None


async def test_잠정값의_비교_대상은_직전_확정값이다(client_provisional: AsyncClient) -> None:
    """FR-013 — 잠정끼리 비교하면 의미가 없다."""
    body = (await client_provisional.get("/api/fx/latest", params={"currency": "USD"})).json()
    assert body["change"]["comparedTo"] == CONFIRMED_2.isoformat()


async def test_데이터가_없으면_no_data(session_factory) -> None:
    """T020."""
    ac = await _make_client(session_factory, [], coverage=False)
    async with ac:
        body = (await ac.get("/api/fx/latest", params={"currency": "USD"})).json()
    assert body["status"] == "no_data"


async def test_지원하지_않는_통화는_404(client_confirmed: AsyncClient) -> None:
    """001이 `unknown_currency`를 404로 매핑한다. 신설 엔드포인트도 같은 규약을 따른다."""
    res = await client_confirmed.get("/api/fx/latest", params={"currency": "KRW"})
    assert res.status_code == 404
    assert res.json()["status"] == "unknown_currency"
