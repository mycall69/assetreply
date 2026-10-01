"""외화 종목의 환전·환산 (T070) — 005 FR-021, FR-041a, SC-009, SC-020.

**초기 환율 하나로 전 구간을 환산하지 않는다.** 그러면 그 뒤의 환율 변동이 통째로
사라져, 주가는 올랐는데 환율이 내려 실제로는 손실인 구간이 이익으로 보인다.
"""
from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest
from httpx2 import ASGITransport, AsyncClient
from sqlalchemy import select

from src.api.main import create_app
from src.db.dialect import upsert
from src.db.models import FxRate, Stock, StockPrice
from src.db.session import get_session

D = dt.date.fromisoformat
DAYS = ["2021-08-02", "2021-09-01", "2021-10-01"]
# 환율이 크게 움직인다 — 환산이 기준일마다 일어나는지 드러나려면 변동이 필요하다.
FX = {"2021-08-02": "1150", "2021-09-01": "1160", "2021-10-01": "1190"}


@pytest.fixture
async def client(session_factory):
    async with session_factory() as s:
        await upsert(s, Stock, [{
            "market": "NASDAQ", "symbol": "AAPL", "name": "Apple Inc.",
            "currency": "USD", "first_available_date": D("1980-12-12")}])
        await s.commit()
        stock_id = int((await s.execute(select(Stock))).scalar_one().id)
        # 주가는 고정. 변하는 것은 환율뿐이라 환산 여부가 드러난다.
        await upsert(s, StockPrice, [{
            "stock_id": stock_id, "quote_date": D(d),
            "open_raw": Decimal("100"), "close_raw": Decimal("100"),
            "close_adjusted": Decimal("100"), "source": "yahoo:chart"}
            for d in DAYS])
        await upsert(s, FxRate, [{
            "currency_code": "USD", "quote_date": D(d),
            "base_rate": Decimal(v), "quote_unit": 1,
            "source": "ECOS:731Y001", "is_provisional": False}
            for d, v in FX.items()])
        await s.commit()

    app = create_app()

    async def _override():
        async with session_factory() as s:
            yield s

    app.dependency_overrides[get_session] = _override
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


PARAMS = {"market": "NASDAQ", "symbol": "AAPL", "start": "2021-08-01",
          "principal": "1000000", "principalCurrency": "KRW",
          "reinvest": "true", "end": "2021-10-31", "limit": "50"}


async def fetch(client: AsyncClient) -> dict:
    res = await client.get("/api/stocks/simulation", params=PARAMS)
    assert res.status_code == 200, res.text
    return res.json()


class Test초기_환전:
    async def test_환전_정보가_실린다(self, client) -> None:
        """FR-021, SC-009 — 적용된 환율과 그 날짜가 드러나야 한다."""
        body = await fetch(client)
        assert "exchange" in body
        assert body["exchange"]["kind"] == "cash_buy_discounted"
        assert body["exchange"]["spreadDiscount"] == "0.9"

    async def test_시작일에_고시가_없으면_쓴_날짜가_드러난다(self, client) -> None:
        """FR-022 — 2021-08-01은 일요일이라 그날 환율이 없다."""
        body = await fetch(client)
        assert body["exchange"]["rateDate"] != "2021-08-01"

    async def test_환전_환율이_매매기준율보다_크다(self, client) -> None:
        """현금을 **사는** 것이므로 가산이다. 작으면 방향이 뒤집힌 것이다."""
        body = await fetch(client)
        assert Decimal(body["exchange"]["rate"]) > Decimal("1150")


class Test기준일별_환산:
    async def test_행마다_환율과_날짜가_실린다(self, client) -> None:
        body = await fetch(client)
        for row in body["rows"]:
            assert "fxRate" in row
            assert "fxRateDate" in row

    async def test_행마다_환율이_다르다(self, client) -> None:
        """SC-020 — 초기 환율 하나로 전 구간을 환산하면 여기서 걸린다."""
        body = await fetch(client)
        rates = {r["fxRate"] for r in body["rows"]}
        assert len(rates) > 1, f"환율이 하나뿐이다: {rates}"

    async def test_평가에는_매매기준율을_쓴다(self, client) -> None:
        """SC-021 — 현금 살 때 환율이나 우대가 섞이면 잔고가 크게 나온다."""
        body = await fetch(client)
        row = next(r for r in body["rows"] if r["date"] == "2021-10-01")
        assert Decimal(row["fxRate"]) == Decimal("1190.000000")

    async def test_주가가_그대로여도_환율이_오르면_잔고가_는다(self, client) -> None:
        """환율 변동이 수익에 반영되지 않으면 이 테스트가 깨진다."""
        body = await fetch(client)
        august = next(r for r in body["rows"] if r["date"] == "2021-08-02")
        october = next(r for r in body["rows"] if r["date"] == "2021-10-01")
        assert Decimal(october["balance"]) > Decimal(august["balance"])


class Test원금_통화_기준:
    async def test_투자금이_원금_통화_그대로다(self, client) -> None:
        """환전된 달러 금액이 아니라 사용자가 낸 원화다."""
        body = await fetch(client)
        assert all(r["principal"] == "1000000" for r in body["rows"])
        assert body["summary"]["principal"] == "1000000"

    async def test_수익률이_원금_통화_기준이다(self, client) -> None:
        """FR-041 — 사용자가 답을 원하는 질문은 "내가 낸 돈이 얼마가 됐나"다."""
        body = await fetch(client)
        row = body["rows"][0]
        expected = (Decimal(row["balance"]) + Decimal(row["cash"])
                    - Decimal(row["principal"]))
        assert Decimal(row["profit"]) == expected
