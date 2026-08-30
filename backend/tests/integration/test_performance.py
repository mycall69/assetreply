"""성능 기준 측정 (T113).

SC-001: 수집된 날짜 조회 3초 이내.
SC-008: 스프레드 변경 후 재산출 2초 이내.
SC-006(차트 조작 1초)은 브라우저 조작이라 quickstart 수동 측정으로 보완한다.
"""
from __future__ import annotations

import datetime as dt
import time
from decimal import Decimal

import pytest
from httpx2 import ASGITransport, AsyncClient

from src.api.main import create_app
from src.db.dialect import upsert
from src.db.models import FxCoverage, FxRate
from src.db.session import get_session

# 30년치에 준하는 규모 — 실제는 통화당 약 8,400건
DAYS = 3000
START = dt.date(2010, 1, 1)


@pytest.fixture
async def client(session_factory):
    rows = []
    for i in range(DAYS):
        day = START + dt.timedelta(days=i)
        if day.weekday() >= 5:  # 주말은 고시 없음
            continue
        rows.append({
            "currency_code": "USD", "quote_date": day,
            "base_rate": Decimal(1000 + (i % 400)), "quote_unit": 1,
            "source": "ECOS:731Y001"})
    async with session_factory() as s:
        for i in range(0, len(rows), 500):
            await upsert(s, FxRate, rows[i:i + 500])
        await upsert(s, FxCoverage, [{
            "currency_code": "USD", "covered_from": START,
            "covered_through": START + dt.timedelta(days=DAYS)}], preserve=())
        await s.commit()

    app = create_app()

    async def _override():
        async with session_factory() as s:
            yield s

    app.dependency_overrides[get_session] = _override
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


async def test_날짜_조회가_3초_이내다(client: AsyncClient) -> None:
    """SC-001."""
    began = time.perf_counter()
    res = await client.get("/api/fx/rates/USD", params={"date": "2015-06-15"})
    elapsed = time.perf_counter() - began
    assert res.status_code == 200
    assert elapsed < 3.0, f"조회에 {elapsed:.2f}초 걸림"


async def test_스프레드_변경_후_재산출이_2초_이내다(client: AsyncClient) -> None:
    """SC-008."""
    await client.put("/api/fx/spreads/USD", json={
        "cashBuy": "0.003", "cashSell": "0.003",
        "remitSend": "0.001", "remitReceive": "0.001"})
    began = time.perf_counter()
    res = await client.get("/api/fx/rates/USD", params={"date": "2015-06-15"})
    elapsed = time.perf_counter() - began
    assert res.status_code == 200
    assert elapsed < 2.0, f"재산출에 {elapsed:.2f}초 걸림"


async def test_전_구간_시계열_응답_시간을_기록한다(client: AsyncClient) -> None:
    """SC-006의 서버 측 몫 — 클라이언트 렌더링은 quickstart에서 측정한다."""
    began = time.perf_counter()
    res = await client.get("/api/fx/series", params={
        "currency": "USD", "from": START.isoformat(),
        "to": (START + dt.timedelta(days=DAYS)).isoformat(), "maxPoints": 2000})
    elapsed = time.perf_counter() - began
    body = res.json()
    print(f"\n  전 구간 시계열: 원본 {body['sourcePointCount']}점 → "
          f"{len(body['points'])}점, {elapsed:.3f}초")
    assert res.status_code == 200
    assert elapsed < 3.0, f"시계열 응답에 {elapsed:.2f}초 걸림"


async def test_다운샘플링이_실제로_줄인다(client: AsyncClient) -> None:
    res = await client.get("/api/fx/series", params={
        "currency": "USD", "from": START.isoformat(),
        "to": (START + dt.timedelta(days=DAYS)).isoformat(), "maxPoints": 500})
    body = res.json()
    assert body["downsampled"] is True
    assert len(body["points"]) <= 500
    assert body["sourcePointCount"] > 2000
