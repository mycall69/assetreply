"""잠정 잔존 노출 (T089) — FR-043a.

오늘이 지났는데도 잠정으로 남은 레코드는 확정 전환이 일어나지 않았다는 뜻이다(FR-037a).
쓰기 시점 불변식(FR-037c)이 잘못된 쓰기를 막으므로 **원인은 하나뿐**이고, 그래서 이 신호가
의미를 갖는다. 운영자는 해당 통화의 증분 수집을 실행하면 해소할 수 있다.
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

TODAY = dt.date.today()
STALE = TODAY - dt.timedelta(days=4)


def _row(day: dt.date, *, provisional: bool, code: str = "USD") -> dict[str, object]:
    return {"currency_code": code, "quote_date": day, "base_rate": Decimal("1300.00"),
            "quote_unit": 1, "source": "ECOS:731Y001", "is_provisional": provisional}


async def _client(session_factory, rows):
    async with session_factory() as s:
        if rows:
            await upsert(s, FxRate, rows)
        await upsert(s, FxCoverage, [{
            "currency_code": "USD", "covered_from": dt.date(2026, 1, 1),
            "covered_through": TODAY - dt.timedelta(days=1)}], preserve=())
        await s.commit()

    app = create_app()

    async def _override():
        async with session_factory() as s:
            yield s

    app.dependency_overrides[get_session] = _override
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.fixture
async def clean(session_factory):
    ac = await _client(session_factory, [_row(STALE, provisional=False)])
    async with ac:
        yield ac


@pytest.fixture
async def stale(session_factory):
    ac = await _client(session_factory, [_row(STALE, provisional=True)])
    async with ac:
        yield ac


@pytest.fixture
async def today_only(session_factory):
    ac = await _client(session_factory, [_row(TODAY, provisional=True)])
    async with ac:
        yield ac


async def _usd(client: AsyncClient) -> dict:
    body = (await client.get("/api/fx/coverage")).json()
    return next(r for r in body["coverage"] if r["currency"] == "USD")


async def test_잠정_잔존이_없으면_필드가_없다(clean: AsyncClient) -> None:
    assert (await _usd(clean)).get("staleProvisional") is None


async def test_오늘_잠정은_잔존이_아니다(today_only: AsyncClient) -> None:
    """오늘 날짜의 잠정은 정상 상태다. 경고를 띄우면 상시 경고가 된다."""
    assert (await _usd(today_only)).get("staleProvisional") is None


async def test_과거_잠정이_남으면_날짜와_함께_노출된다(stale: AsyncClient) -> None:
    """FR-043a."""
    info = (await _usd(stale))["staleProvisional"]
    assert info["date"] == STALE.isoformat()


async def test_통화별로_따로_판정한다(session_factory) -> None:
    ac = await _client(session_factory, [
        _row(STALE, provisional=True, code="USD"),
        _row(STALE, provisional=False, code="JPY"),
    ])
    async with ac:
        body = (await ac.get("/api/fx/coverage")).json()
    by_code = {r["currency"]: r for r in body["coverage"]}
    assert by_code["USD"]["staleProvisional"] is not None
    # 커버리지 행이 없는 통화는 응답에 나오지 않는다 — 001의 동작 그대로다
    assert "JPY" not in by_code or by_code["JPY"].get("staleProvisional") is None


async def test_잔존이_여러_날_있으면_가장_오래된_것을_알린다(session_factory) -> None:
    older = TODAY - dt.timedelta(days=10)
    ac = await _client(session_factory, [
        _row(older, provisional=True),
        _row(STALE, provisional=True),
    ])
    async with ac:
        info = (await _usd(ac))["staleProvisional"]
    assert info["date"] == older.isoformat(), "가장 오래된 잔존을 알려야 심각도가 드러난다"
