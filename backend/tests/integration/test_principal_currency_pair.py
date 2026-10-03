"""원금 통화 제한 (T076) — 006 FR-050, FR-050a, FR-050d, FR-051, FR-052, SC-011, research R6-11.

**원금 통화는 원화 또는 종목 통화만이다.** 005는 원금과 종목 통화가 다르면 원화를 경유하지 않고 종목
통화의 원화 환율로 바로 나눴다 — 원금 1,000 EUR이 약 1,080 USD가 아니라 0.77 USD가 되고, 오류 없이
그럴듯한 수익률이 나왔다. **어느 경로로 들어온 요청이든** 같은 판정을 거친다 — 화면만 막으면 이력의
재실행과 직접 요청이 조용히 계산된다.
"""
from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest
from httpx2 import ASGITransport, AsyncClient
from sqlalchemy import func, select

from src.api.main import create_app
from src.db.dialect import upsert
from src.db.models import (
    FxCollectionJob,
    FxCoverage,
    FxRate,
    Stock,
    StockCollectionJob,
    StockCoverage,
    StockPrice,
)
from src.db.session import get_session
from src.worker.queue import get_queue

D = dt.date.fromisoformat
BASE = {"start": "2021-08-02", "end": "2021-08-31", "principal": "1000", "reinvest": "true"}


@pytest.fixture
async def client(session_factory):  # type: ignore[no-untyped-def]
    async with session_factory() as s:
        await upsert(s, Stock, [
            {"market": "KRX", "symbol": "005930.KS", "name": "삼성전자", "currency": "KRW"},
            {"market": "NASDAQ", "symbol": "AAPL", "name": "애플", "currency": "USD"},
            # 시세를 받은 적 없는 종목 — 막히지 않으면 수집이 시작된다.
            {"market": "NYSE", "symbol": "IBM", "name": "IBM", "currency": "USD"},
        ])
        await s.commit()
        aapl = int((await s.execute(select(Stock.id).where(Stock.symbol == "AAPL"))).scalar_one())
        await upsert(s, StockPrice, [{
            "stock_id": aapl, "quote_date": D("2021-08-02"), "open_raw": Decimal("100"),
            "close_raw": Decimal("100"), "close_adjusted": Decimal("100"),
            "source": "yahoo:chart"}])
        await upsert(s, StockCoverage, [{
            "stock_id": aapl, "covered_from": D("2021-08-01"),
            "covered_through": D("2021-08-31")}], preserve=())
        await s.commit()
    app = create_app()

    async def _override():  # type: ignore[no-untyped-def]
        async with session_factory() as s:
            yield s

    app.dependency_overrides[get_session] = _override
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


async def count(session_factory, model) -> int:  # type: ignore[no-untyped-def]
    async with session_factory() as s:
        return int((await s.execute(select(func.count()).select_from(model))).scalar_one())


PATHS = ["/api/stocks/simulation", "/api/stocks/simulation/series"]


class Test막힌_조합:
    @pytest.mark.parametrize("path", PATHS)
    @pytest.mark.parametrize(("market", "symbol", "currency", "allowed"), [
        ("KRX", "005930.KS", "USD", ["KRW"]),          # 국내 종목 + USD
        ("NASDAQ", "AAPL", "EUR", ["KRW", "USD"]),     # 미국 종목 + EUR (contracts 예시)
        ("NASDAQ", "AAPL", "JPY", ["KRW", "USD"]),     # 미국 종목 + JPY
    ])
    async def test_표와_차트가_같이_거절한다(self, client, path: str, market: str,
                                               symbol: str, currency: str,
                                               allowed: list[str]) -> None:
        """FR-050, FR-050a — 한쪽만 막으면 같은 조건이 한 화면에서 거절되고 다른 화면에서
        통과한다."""
        res = await client.get(path, params={**BASE, "market": market, "symbol": symbol,
                                             "principalCurrency": currency})
        assert res.status_code == 400, res.text
        body = res.json()
        assert body["status"] == "currency_pair_not_allowed"
        assert body["allowed"] == allowed
        assert currency in body["message"]
        assert "rows" not in body and "points" not in body

    async def test_어떤_계산도_수집도_일어나지_않는다(self, client, session_factory) -> None:
        """FR-051 — 막힌 조합이 시세 수집이나 환율 수집을 시작하면 결과를 낼 수 없는 일에
        한도를 쓴다."""
        res = await client.get("/api/stocks/simulation", params={
            **BASE, "market": "NYSE", "symbol": "IBM", "principalCurrency": "EUR"})
        assert res.status_code == 400
        assert await count(session_factory, StockCollectionJob) == 0
        assert await count(session_factory, FxCollectionJob) == 0
        assert get_queue().in_progress is None

    async def test_EUR은_원금_통화로_받지_않는다(self, client) -> None:
        """FR-050d — 유로로 거래되는 지원 시장이 없다. 어느 종목과도 조합이 되지 않는다."""
        for market, symbol in (("KRX", "005930.KS"), ("NASDAQ", "AAPL")):
            res = await client.get("/api/stocks/simulation", params={
                **BASE, "market": market, "symbol": symbol, "principalCurrency": "EUR"})
            assert res.json()["status"] == "currency_pair_not_allowed"

    async def test_모르는_통화는_여전히_invalid_query다(self, client) -> None:
        res = await client.get("/api/stocks/simulation", params={
            **BASE, "market": "NASDAQ", "symbol": "AAPL", "principalCurrency": "GBP"})
        assert res.status_code == 400
        assert res.json()["status"] == "invalid_query"


class Test허용된_조합:
    async def test_종목_통화와_같으면_환전_없이_계산한다(self, client, session_factory) -> None:
        """FR-052.

        006 FR-068(반복 2026-10-03 #4, T137) — 환전은 없어도 투자 수익을 KRW로 평가하므로 USD 환율을
        받아 둔 상태여야 한다. 받아 두지 않으면 202(환율 수집)다(`test_fx_gate.py`).
        """
        async with session_factory() as s:
            await upsert(s, FxRate, [{
                "currency_code": "USD", "quote_date": D("2021-08-02"),
                "base_rate": Decimal("1150"), "quote_unit": 1, "source": "ECOS:731Y001",
                "is_provisional": False}])
            await upsert(s, FxCoverage, [{
                "currency_code": "USD", "covered_from": D("2021-07-01"),
                "covered_through": D("2021-08-31")}], preserve=())
            await s.commit()
        res = await client.get("/api/stocks/simulation", params={
            **BASE, "market": "NASDAQ", "symbol": "AAPL", "principalCurrency": "USD"})
        assert res.status_code == 200, res.text
        assert "exchange" not in res.json()

    async def test_원화_원금은_외화_종목에_허용된다(self, client) -> None:
        res = await client.get("/api/stocks/simulation", params={
            **BASE, "market": "NASDAQ", "symbol": "AAPL", "principalCurrency": "KRW",
            "principal": "1000000"})
        assert res.json().get("status") != "currency_pair_not_allowed"
