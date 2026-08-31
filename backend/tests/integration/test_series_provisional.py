"""시계열 응답의 잠정 구분 (T035).

FR-017a: 오늘 잠정값은 차트에도 표시하되 확정 구간과 구분되어야 한다. 요약과 차트의
마지막 시점이 어긋나면 같은 화면이 서로 다른 때를 가리킨다(SC-007a).
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

CONFIRMED = dt.date(2026, 8, 29)
TODAY = dt.date(2026, 8, 30)


@pytest.fixture
async def client(session_factory):
    async with session_factory() as s:
        await upsert(s, FxRate, [
            {"currency_code": "USD", "quote_date": CONFIRMED,
             "base_rate": Decimal("1356.10"), "quote_unit": 1,
             "source": "ECOS:731Y001", "is_provisional": False},
            {"currency_code": "USD", "quote_date": TODAY,
             "base_rate": Decimal("1354.20"), "quote_unit": 1,
             "source": "ECOS:731Y001", "is_provisional": True},
        ])
        await upsert(s, FxCoverage, [
            {"currency_code": "USD", "covered_from": dt.date(2026, 8, 1),
             "covered_through": CONFIRMED}], preserve=())
        await s.commit()

    app = create_app()

    async def _override():
        async with session_factory() as s:
            yield s

    app.dependency_overrides[get_session] = _override
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


async def _series(client: AsyncClient) -> dict:
    return (await client.get("/api/fx/series", params={
        "currency": "USD", "from": "2026-08-01", "to": TODAY.isoformat()})).json()


async def test_잠정_포인트에_표시가_붙는다(client: AsyncClient) -> None:
    points = (await _series(client))["points"]
    by_date = {p["date"]: p for p in points}
    assert by_date[TODAY.isoformat()]["isProvisional"] is True


async def test_확정_포인트에는_표시가_없다(client: AsyncClient) -> None:
    """`true`일 때만 포함한다 — 대부분의 점에 붙지 않아 응답이 커지지 않는다."""
    points = (await _series(client))["points"]
    by_date = {p["date"]: p for p in points}
    assert "isProvisional" not in by_date[CONFIRMED.isoformat()]


async def test_잠정_포인트가_차트에_포함된다(client: AsyncClient) -> None:
    """FR-017a — 빼면 요약(오늘)과 차트(어제)의 끝점이 어긋난다."""
    dates = [p["date"] for p in (await _series(client))["points"]]
    assert TODAY.isoformat() in dates
