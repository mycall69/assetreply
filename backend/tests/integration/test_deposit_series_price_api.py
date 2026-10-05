"""예금 시계열의 그 달 금리 (010 T009) — FR-001~FR-003, FR-011, SC-001, SC-002, contracts/rest-api
`GET /api/deposit/simulation/series`.

- `priceKind "deposit_rate"`, `priceCurrency null`(단위 연 %)
- 가입·재예치 점의 `price` = 표의 그 행 `rate`(잠정이 아닌 행 — 시뮬레이션이 그 달에 읽은 금리,
  FR-002). 서식도 표와 같다(`rate_text`)
- 마지막 발표 달(2026-08) 뒤의 점 → `price null` + `priceMissing "unpublished"`
- 발표 기간 안의 빈 달(만기 사이 — 2020-06) → `price null` + `priceMissing "missing"`이고 계산은
  멈추지 않는다
- `gaps == []`·`provisionalFrom`은 그대로다 — 가격만 없는 점을 `gaps`에 넣지 않는다(research R10-2)
"""
from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest
from httpx2 import ASGITransport, AsyncClient

from src.api.main import create_app
from src.db.session import get_session
from tests.integration.deposit_support import LATEST, TODAY, rate_of, seed_rates

BASE = {"institution": "commercial_bank", "start": "2020-01-15", "principal": "10000000"}
D = dt.date.fromisoformat


@pytest.fixture
async def client(session_factory, monkeypatch):  # type: ignore[no-untyped-def]
    monkeypatch.setattr("src.api.services.deposit_simulation.kst_today", lambda: TODAY)
    app = create_app()

    async def _session():  # type: ignore[no-untyped-def]
        async with session_factory() as s:
            yield s

    app.dependency_overrides[get_session] = _session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        yield c


async def both(client: AsyncClient) -> tuple[dict, dict]:  # type: ignore[type-arg]
    table = await client.get("/api/deposit/simulation", params=BASE)
    series = await client.get("/api/deposit/simulation/series", params=BASE)
    assert (table.status_code, series.status_code) == (200, 200), (table.text, series.text)
    return table.json(), series.json()


async def test_가격의_종류와_단위(client: AsyncClient, session_factory) -> None:  # type: ignore[no-untyped-def]
    await seed_rates(session_factory)
    _, series = await both(client)
    assert (series["priceKind"], series["priceCurrency"]) == ("deposit_rate", None)
    assert series["gaps"] == [] and series["provisionalFrom"] is None


async def test_가입_재예치_점은_표의_적용_금리와_같다(client: AsyncClient, session_factory) -> None:  # type: ignore[no-untyped-def]
    await seed_rates(session_factory)
    table, series = await both(client)
    by_date = {p["date"]: p for p in series["points"]}
    starts = [r for r in table["rows"]
              if r["kind"] in ("join", "reinvest") and not r["provisional"]]
    assert len(starts) >= 6
    for row in starts:
        assert by_date[row["date"]]["price"] == row["rate"], row["date"]


async def test_발표된_달의_점은_그_달_금리다(client: AsyncClient, session_factory) -> None:  # type: ignore[no-untyped-def]
    await seed_rates(session_factory)
    _, series = await both(client)
    for point in series["points"]:
        month = point["date"][:7]
        if D(month + "-01") <= LATEST:
            assert Decimal(point["price"]) == rate_of("commercial_bank", month), point["date"]
            assert "priceMissing" not in point


async def test_마지막_발표_달_뒤는_비고_미발표다(client: AsyncClient, session_factory) -> None:  # type: ignore[no-untyped-def]
    await seed_rates(session_factory)
    _, series = await both(client)
    later = [p for p in series["points"] if D(p["date"][:7] + "-01") > LATEST]
    assert [p["date"] for p in later] == ["2026-09-01", "2026-10-01", "2026-10-04"]
    assert all((p["price"], p["priceMissing"]) == (None, "unpublished") for p in later)


async def test_발표_기간_안의_빈_달은_비고_결측이며_계산은_이어진다(  # type: ignore[no-untyped-def]
        client: AsyncClient, session_factory) -> None:
    await seed_rates(session_factory, drop=("2020-06",))
    table, series = await both(client)
    assert table["summary"]["stopped"] is None
    by_date = {p["date"]: p for p in series["points"]}
    hole = by_date["2020-06-01"]
    assert (hole["price"], hole["priceMissing"]) == (None, "missing")
    assert by_date["2020-07-01"]["price"] is not None
    assert series["gaps"] == []
