"""정기 적금 시계열 (011 T044) — FR-032, contracts/rest-api §3 `…/series`.

- 008 시계열과 같은 모양이다. 점은 표의 행 날짜에 계산 끝(보드의 기준일)을 더한 것이고, 같은 날의
  행이 여럿이면 그 날의 마지막 상태다
- `principal` = 그날까지의 총 납입 원금, `balance` = 평가(적금 쪽 + 정기예금 쪽)
- `price` = 그 달 **발표된** 적금 금리(`priceKind "installment_rate"`)
  - 마지막 발표 달 뒤면 `null` + `unpublished`다. 계산이 대신 쓴 금리(잠정)를 그 달 금리로 내지
    않는다(헌법 원칙 V)
- `depositRate` = 그 달 발표된 정기예금 금리 — 없으면 키가 없다(상자가 그 줄을 비운다)
- 수집 판정은 표와 같다(같은 202 본문)
"""
from __future__ import annotations

import datetime as dt

import pytest
from httpx2 import ASGITransport, AsyncClient

from src.api.main import create_app
from src.db.session import get_session
from tests.integration.deposit_support import TODAY, rate_of, seed_rates

D = dt.date.fromisoformat
TABLE = "/api/deposit/installment-simulation"
SERIES = TABLE + "/series"
BASE = {"institution": "commercial_bank", "start": "2015-01-15", "amount": "1000000"}


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


async def seeded(session_factory) -> None:  # type: ignore[no-untyped-def]
    await seed_rates(session_factory, "commercial_bank_isav")
    await seed_rates(session_factory, "commercial_bank")


async def test_점은_표의_날짜와_기준일이고_그_날의_마지막_상태다(client, session_factory) -> None:  # type: ignore[no-untyped-def]
    await seeded(session_factory)
    table = (await client.get(TABLE, params=BASE)).json()
    series = (await client.get(SERIES, params={**BASE, "maxPoints": "5000"})).json()
    last_of_day: dict[str, dict] = {}  # type: ignore[type-arg]
    for row in table["rows"]:  # 최신순 — 같은 날의 첫 행이 그 날의 마지막 상태
        last_of_day.setdefault(row["date"], row)
    dates = [p["date"] for p in series["points"]]
    assert dates == sorted({*last_of_day, table["summary"]["asOf"]})
    for point in series["points"]:
        row = last_of_day.get(point["date"])
        if row is None:
            assert point["balance"] == table["summary"]["balance"]
            continue
        assert (point["balance"], point["principal"], point["returnRate"]) == (
            row["balance"], row["contributed"], row["returnRate"])
    assert (series["priceKind"], series["priceCurrency"], series["gaps"]) == (
        "installment_rate", None, [])
    assert (series["from"], series["to"], series["provisionalFrom"]) == (
        "2015-01-15", TODAY.isoformat(), None)


async def test_가격은_그_달_발표_적금_금리이고_정기예금_금리가_곁에_있다(  # type: ignore[no-untyped-def]
        client, session_factory) -> None:
    await seeded(session_factory)
    points = {p["date"]: p for p in (await client.get(
        SERIES, params={**BASE, "maxPoints": "5000"})).json()["points"]}
    first = points["2015-01-15"]
    assert first["price"] == str(rate_of("commercial_bank_isav", "2015-01"))
    # 정기예금 통계는 2012-01부터다 — 2015-01에도 발표 값이 있다
    assert first["depositRate"] == str(rate_of("commercial_bank", "2015-01"))
    assert "priceMissing" not in first
    # 마지막 발표 달(2026-08) 뒤는 미발표다 — 잠정 금리를 그 달 금리로 내지 않는다
    september = points["2026-09-01"]
    assert (september["price"], september["priceMissing"]) == (None, "unpublished")
    assert "depositRate" not in september


async def test_수집_판정은_표와_같다(client) -> None:  # type: ignore[no-untyped-def]
    table = await client.get(TABLE, params=BASE)
    series = await client.get(SERIES, params=BASE)
    assert table.status_code == series.status_code == 202
    assert table.json() == series.json()
