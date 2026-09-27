"""`GET /api/fx/daily`의 기간 단위 계약 (T019) — 004 FR-006, FR-007, SC-005.

**매개변수를 생략하면 002와 완전히 같은 응답이 나와야 한다.** 기존 호출자가 깨지지
않는 것이 `period` 기본값 `daily`의 계약상 의미다.

알 수 없는 값을 **조용히 `daily`로 떨어뜨리지 않는다.** 화면이 잘못된 값을 보냈는데
정상 응답이 오면 그 버그가 드러나지 않는다.
"""
from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest
from httpx2 import ASGITransport, AsyncClient

from src.api.main import create_app
from src.api.services.collection_gate import CollectionDecision
from src.db.dialect import upsert
from src.db.models import FxCoverage, FxRate
from src.db.session import get_session

DAYS = ["2026-07-13", "2026-07-16", "2026-07-24", "2026-07-31", "2026-08-14"]


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
            {"currency_code": "USD", "covered_from": dt.date(2026, 7, 1),
             "covered_through": dt.date(2026, 8, 14)},
        ], preserve=())
        await s.commit()

    app = create_app()

    async def _override():
        async with session_factory() as s:
            yield s

    app.dependency_overrides[get_session] = _override
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


async def test_생략하면_일_단위다(client: AsyncClient) -> None:
    """FR-007, SC-005 — 기존 호출자가 깨지지 않는다."""
    body = (await client.get("/api/fx/daily", params={"currency": "USD"})).json()
    assert body["period"] == "daily"
    assert [r["date"] for r in body["rows"]] == sorted(DAYS, reverse=True)


async def test_생략한_응답이_명시한_응답과_같다(client: AsyncClient) -> None:
    omitted = (await client.get("/api/fx/daily", params={"currency": "USD"})).json()
    explicit = (await client.get(
        "/api/fx/daily", params={"currency": "USD", "period": "daily"})).json()
    assert omitted == explicit


@pytest.mark.parametrize("unit", ["daily", "weekly", "monthly"])
async def test_세_단위를_모두_받는다(client: AsyncClient, unit: str) -> None:
    res = await client.get("/api/fx/daily", params={"currency": "USD", "period": unit})
    assert res.status_code == 200
    assert res.json()["period"] == unit


@pytest.mark.parametrize("bad", ["yearly", "DAILY", "week", "", "1"])
async def test_알_수_없는_단위는_400이다(client: AsyncClient, bad: str) -> None:
    """조용히 `daily`로 떨어지면 화면의 버그가 드러나지 않는다."""
    res = await client.get("/api/fx/daily", params={"currency": "USD", "period": bad})
    assert res.status_code == 400
    assert res.json()["status"] == "invalid_query"


async def test_수집_중_응답은_기간_단위와_무관하게_같다(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """contracts/rest-api 수집 중 응답 — 001·002가 정한 형태를 그대로 유지한다.

    `period`를 더하면서 이 이른 반환 경로가 함께 바뀌기 쉽다. 바뀌어도 200 응답은
    멀쩡해 보이므로 화면만 보아서는 드러나지 않는다.
    """
    import src.api.routes.daily as route

    monkeypatch.setattr(
        route, "decide_collection", lambda **_: CollectionDecision.BACKGROUND)

    for unit in ("daily", "weekly", "monthly"):
        res = await client.get(
            "/api/fx/daily", params={"currency": "USD", "period": unit})
        assert res.status_code == 202
        body = res.json()
        assert body["status"] == "collecting"
        assert body["currency"] == "USD"
        assert set(body) == {
            "status", "currency", "jobId", "missingDays", "progressUrl"}


async def test_지원하지_않는_통화는_404다(client: AsyncClient) -> None:
    res = await client.get("/api/fx/daily", params={"currency": "XXX", "period": "weekly"})
    assert res.status_code == 404
    assert res.json()["status"] == "unknown_currency"
