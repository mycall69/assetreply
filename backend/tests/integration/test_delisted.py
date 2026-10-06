"""시세 단절 (T096) — 005 FR-014a, FR-014b, SC-026, 헌법 원칙 V.

**마지막 시세를 오늘까지 이어 그리지 않는다.** 없는 값을 만들어내는 것이라 원칙 V
위반이며, 상장폐지는 대개 큰 손실인데 알리지 않으면 화면에는 **폐지 직전 수익률**이
최종 성과처럼 남는다.
"""
from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest
from httpx2 import ASGITransport, AsyncClient
from sqlalchemy import select

from src.api.main import create_app
from src.db.dialect import upsert
from src.db.models import Stock, StockCoverage, StockPrice
from src.db.session import get_session

D = dt.date.fromisoformat

#: 시세가 2021-09-02에서 끊긴다. 그 뒤로는 거래가 없었다 — 받지 못한 것이 아니다.
TRADED = ["2021-08-02", "2021-08-03", "2021-09-01", "2021-09-02"]
LAST_TRADED = "2021-09-02"
#: 수집은 11월 말까지 **시도했다.** 커버리지는 "받으러 갔다"는 기록이다.
COVERED_THROUGH = "2021-11-30"


@pytest.fixture
async def client(session_factory):
    async with session_factory() as s:
        await upsert(s, Stock, [{
            "market": "KRX", "symbol": "111111.KS", "name": "상장폐지종목",
            "currency": "KRW", "first_available_date": D("2010-01-04")}])
        await s.commit()
        stock_id = int((await s.execute(select(Stock))).scalar_one().id)
        price = Decimal("40000")
        rows = []
        for day in TRADED:
            rows.append({
                "stock_id": stock_id, "quote_date": D(day),
                "open_raw": price, "close_raw": price,
                "close_adjusted": price, "source": "yahoo:chart"})
            # 폐지 직전으로 갈수록 떨어진다 — 마지막 값을 이어 그리면 손실이 가려진다.
            price -= Decimal("5000")
        await upsert(s, StockPrice, rows)
        await upsert(s, StockCoverage, [{
            "stock_id": stock_id, "covered_from": D("2021-08-01"),
            "covered_through": D(COVERED_THROUGH)}], preserve=())
        await s.commit()

    app = create_app()

    async def _override():
        async with session_factory() as s:
            yield s

    app.dependency_overrides[get_session] = _override
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


PARAMS = {"market": "KRX", "symbol": "111111.KS", "start": "2021-08-01",
          "principal": "86997", "principalCurrency": "KRW", "reinvest": "true",
          "end": COVERED_THROUGH, "limit": "50"}


async def fetch(client: AsyncClient) -> dict:
    res = await client.get("/api/stocks/simulation", params=PARAMS)
    assert res.status_code == 200, res.text
    return res.json()


class Test계산_범위:
    async def test_마지막_시세일까지만_계산한다(self, client) -> None:
        """FR-014a — 이어 그리면 없는 값을 만들어내는 것이다 (원칙 V)."""
        body = await fetch(client)
        assert body["summary"]["asOf"] == LAST_TRADED

    async def test_기준일이_요청_끝이_아니다(self, client) -> None:
        body = await fetch(client)
        assert body["summary"]["asOf"] != COVERED_THROUGH

    async def test_마지막_시세일_이후의_행이_없다(self, client) -> None:
        """행은 월 첫 거래일·배당락일뿐이라 마지막 행이 마지막 시세일은 아니다.

        여기서 막아야 하는 것은 **그 뒤로 행이 생기는 것**이다 — 10월·11월 행이
        생기면 거래가 없던 날의 값을 지어낸 것이다.
        """
        body = await fetch(client)
        assert max(r["date"] for r in body["rows"]) <= LAST_TRADED

    async def test_끊긴_뒤의_달에_행을_만들지_않는다(self, client) -> None:
        """10월·11월은 거래가 없었다. 행을 만들면 값을 지어내게 된다."""
        body = await fetch(client)
        months = {r["date"][:7] for r in body["rows"]}
        assert "2021-10" not in months
        assert "2021-11" not in months


class Test단절_표시:
    async def test_최종이_아님을_밝힌다(self, client) -> None:
        """FR-014b, SC-026 — 알리지 않으면 폐지 직전 수익률이 최종 성과로 남는다."""
        body = await fetch(client)
        assert body["summary"]["isFinal"] is False

    async def test_끝까지_있으면_최종이다(self, client) -> None:
        """"확인했고 아니다"와 "확인하지 않았다"가 구별되어야 한다."""
        res = await client.get("/api/stocks/simulation",
                               params={**PARAMS, "end": LAST_TRADED})
        assert res.status_code == 200, res.text
        assert res.json()["summary"]["isFinal"] is True

    async def test_차트가_표와_같은_곳에서_끝난다(self, client) -> None:
        """SC-032 — 표는 9월에서 끝나는데 차트만 이어지면 둘이 어긋난다."""
        res = await client.get("/api/stocks/simulation/series", params=PARAMS)
        assert res.status_code == 200, res.text
        body = await fetch(client)
        # 012 승인 2026-10-06 — 일 단위 표의 맨 위는 마지막 시세일이고, 차트는 그대로(월 첫
        # 거래일·사건 날)라 그보다 늦지 않다. 둘 다 끊긴 날
        # 뒤로 이어지지 않는다.
        top = max(r["date"] for r in body["rows"])
        assert top == LAST_TRADED
        assert res.json()["points"][-1]["date"] <= top

    async def test_요약이_마지막_시세일_기준이다(self, client) -> None:
        """FR-014b — "09-02 기준"이라 적고 09-01 수치를 보이면 보드가 거짓말한다."""
        body = await fetch(client)
        assert body["summary"]["asOf"] == LAST_TRADED
