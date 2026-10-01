"""재투자 켬/끔의 차이 (T055) — 005 SC-011.

사용자가 **보유 주식 수로** 차이를 확인할 수 있어야 한다. 배당 재투자의 복리 효과는
표의 한 열을 보는 것으로는 알 수 없고, 켰다 껐다 해봐야 안다.
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
# 10년간 분기 배당. 복리 효과가 드러나려면 반복이 필요하다.
MONTHS = [f"{y}-{m:02d}-01" for y in range(2015, 2025) for m in (1, 4, 7, 10)]


@pytest.fixture
async def client(session_factory):
    async with session_factory() as s:
        await upsert(s, Stock, [{
            "market": "KRX", "symbol": "005930.KS", "name": "삼성전자",
            "currency": "KRW", "first_available_date": D("1975-06-11")}])
        await s.commit()
        stock_id = int((await s.execute(select(Stock))).scalar_one().id)
        await upsert(s, StockPrice, [{
            "stock_id": stock_id, "quote_date": D(d),
            "open_raw": Decimal("10000"), "close_raw": Decimal("10000"),
            "close_adjusted": Decimal("10000"), "source": "yahoo:chart"}
            for d in MONTHS])
        await upsert(s, StockDividend, [{
            "stock_id": stock_id, "ex_date": D(d),
            "amount_per_share": Decimal("500"), "source": "yahoo:chart"}
            for d in MONTHS])
        # 픽스처는 "이미 수집을 마친 상태"를 흉내낸다. 커버리지를 적지 않으면
        # 요청 구간이 미수집으로 판정돼 202가 돌아간다 (FR-047).
        await upsert(s, StockCoverage, [{
            "stock_id": stock_id, "covered_from": D("2015-01-01"),
            "covered_through": D("2024-12-31")}], preserve=())
        await s.commit()

    app = create_app()

    async def _override():
        async with session_factory() as s:
            yield s

    app.dependency_overrides[get_session] = _override
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


BASE = {"market": "KRX", "symbol": "005930.KS", "start": "2015-01-01",
        "principal": "1000000", "principalCurrency": "KRW",
        "end": "2024-12-31", "limit": "1"}


async def latest(client: AsyncClient, reinvest: str) -> dict:
    body = (await client.get("/api/stocks/simulation",
                             params={**BASE, "reinvest": reinvest})).json()
    return body["rows"][0]


async def test_재투자를_켜면_보유_주식이_더_많다(client) -> None:
    """SC-011 — 사용자가 보유 주식 수로 차이를 확인한다."""
    on = await latest(client, "true")
    off = await latest(client, "false")
    assert on["heldShares"] > off["heldShares"]


async def test_재투자를_끄면_예수금이_더_많다(client) -> None:
    on = await latest(client, "true")
    off = await latest(client, "false")
    assert Decimal(off["cash"]) > Decimal(on["cash"])


async def test_배당이_반복되면_재투자가_복리로_불어난다(client) -> None:
    """이 기능의 존재 이유다.

    배당이 한 번뿐이면 총자산이 같다 — 현금이 주식으로 바뀔 뿐이다. 하지만 배당은
    **주당** 지급되므로, 재투자로 늘어난 주식이 다음 배당을 더 받는다. 10년 분기
    배당이면 그 차이가 눈에 띄게 벌어진다.
    """
    on = await latest(client, "true")
    off = await latest(client, "false")
    on_total = Decimal(on["balance"]) + Decimal(on["cash"])
    off_total = Decimal(off["balance"]) + Decimal(off["cash"])
    assert on_total > off_total
