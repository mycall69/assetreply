"""재현성 (T049) — 005 FR-014, SC-002.

**원주가는 바뀌지 않지만 수정주가는 바뀐다.** 나중에 배당·분할이 생기면 과거의 수정주가가
소급해 달라진다. 재현성이 원주가에 기대는 근거이며(research R5-3), 수정주가를 보관하되
계산에 쓰지 않는 이유이기도 하다.
"""
from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest
from httpx2 import ASGITransport, AsyncClient
from sqlalchemy import select

from src.api.main import create_app
from src.db.dialect import upsert
from src.db.models import Stock, StockCoverage, StockDividend, StockPrice
from src.db.session import get_session

D = dt.date.fromisoformat
DAYS = ["2021-08-02", "2021-09-01", "2021-10-01", "2021-11-01"]


@pytest.fixture
async def setup(session_factory):
    async with session_factory() as s:
        await upsert(s, Stock, [{
            "market": "KRX", "symbol": "005930.KS", "name": "삼성전자",
            "currency": "KRW", "first_available_date": D("1975-06-11")}])
        await s.commit()
        stock_id = int((await s.execute(select(Stock))).scalar_one().id)
        await upsert(s, StockPrice, [{
            "stock_id": stock_id, "quote_date": D(d),
            "open_raw": Decimal("40000") + Decimal(i * 1000),
            "close_raw": Decimal("40000") + Decimal(i * 1000),
            "close_adjusted": Decimal("39000") + Decimal(i * 1000),
            "source": "yahoo:chart"} for i, d in enumerate(DAYS)])
        await upsert(s, StockDividend, [{
            "stock_id": stock_id, "ex_date": D("2021-09-01"),
            "amount_per_share": Decimal("300"), "source": "yahoo:chart"}])
        # 픽스처는 "이미 수집을 마친 상태"를 흉내낸다. 커버리지를 적지 않으면
        # 요청 구간이 미수집으로 판정돼 202가 돌아간다 (FR-047).
        await upsert(s, StockCoverage, [{
            "stock_id": stock_id, "covered_from": D("2021-08-01"),
            "covered_through": D("2021-11-30")}], preserve=())
        await s.commit()
    return session_factory, stock_id


@pytest.fixture
async def client(setup):
    session_factory, _ = setup
    app = create_app()

    async def _override():
        async with session_factory() as s:
            yield s

    app.dependency_overrides[get_session] = _override
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


PARAMS = {
    "market": "KRX", "symbol": "005930.KS", "start": "2021-08-01",
    "principal": "86997", "principalCurrency": "KRW", "reinvest": "true",
    "end": "2021-11-30", "limit": "50",
}


async def test_같은_입력은_같은_결과다(client) -> None:
    """SC-002 — 재현되지 않으면 사용자가 본 수치를 신뢰할 수 없다."""
    first = (await client.get("/api/stocks/simulation", params=PARAMS)).json()
    second = (await client.get("/api/stocks/simulation", params=PARAMS)).json()
    assert first == second


async def test_수정주가가_바뀌어도_결과가_같다(setup, client) -> None:
    """FR-011의 귀결 — 수정주가로 계산했다면 여기서 결과가 달라진다.

    출처가 나중에 배당·분할을 반영해 수정종가를 통째로 바꾸는 일이 실제로 일어난다.
    """
    before = (await client.get("/api/stocks/simulation", params=PARAMS)).json()

    session_factory, stock_id = setup
    async with session_factory() as s:
        await upsert(s, StockPrice, [{
            "stock_id": stock_id, "quote_date": D(d),
            "open_raw": Decimal("40000") + Decimal(i * 1000),
            "close_raw": Decimal("40000") + Decimal(i * 1000),
            # 수정종가만 통째로 바꾼다. 원주가는 그대로다.
            "close_adjusted": Decimal("1"),
            "source": "yahoo:chart"} for i, d in enumerate(DAYS)])
        await s.commit()

    after = (await client.get("/api/stocks/simulation", params=PARAMS)).json()
    assert after["rows"] == before["rows"], "수정주가 변경이 결과를 바꿨다"
    assert after["summary"] == before["summary"]


async def test_재투자_여부가_결과를_가른다(client) -> None:
    """재현성은 "항상 같다"가 아니라 "같은 입력에 같다"이다."""
    on = (await client.get("/api/stocks/simulation", params=PARAMS)).json()
    off = (await client.get(
        "/api/stocks/simulation", params={**PARAMS, "reinvest": "false"})).json()
    assert on["condition"]["reinvest"] is True
    assert off["condition"]["reinvest"] is False
