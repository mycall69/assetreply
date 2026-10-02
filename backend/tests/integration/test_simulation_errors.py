"""시뮬레이션 오류 (T030) — 005 FR-004, FR-005, SC-016.

**빈 표를 보여주지 않는다.** 사용자는 그 종목의 성과가 0이라고 읽는다.
**조용히 첫 거래일로 옮기지 않는다.** 옮기면 자신이 고른 날짜부터 계산됐다고 믿는다.
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


@pytest.fixture
async def client(session_factory):
    async with session_factory() as s:
        await upsert(s, Stock, [
            {"market": "KRX", "symbol": "005930.KS", "name": "삼성전자",
             "currency": "KRW"},
            # 받으러 간 적이 **없는** 종목. "시세가 없다"는 결론은 이르다.
            {"market": "KRX", "symbol": "999999.KS", "name": "신규상장",
             "currency": "KRW"},
            # 받으러 갔는데 **한 건도 없었던** 종목. 여기서는 사유를 말해야 한다.
            {"market": "KRX", "symbol": "888888.KS", "name": "거래없음",
             "currency": "KRW"}])
        await s.commit()
        stock_id = int((await s.execute(
            select(Stock).where(Stock.symbol == "005930.KS"))).scalar_one().id)
        await upsert(s, StockPrice, [{
            "stock_id": stock_id, "quote_date": D("2021-08-02"),
            "open_raw": Decimal("40000"), "close_raw": Decimal("40000"),
            "close_adjusted": Decimal("40000"), "source": "yahoo:chart"}])
        empty_id = int((await s.execute(
            select(Stock).where(Stock.symbol == "888888.KS"))).scalar_one().id)
        await upsert(s, StockCoverage, [
            {"stock_id": stock_id, "covered_from": D("2021-08-01"),
             "covered_through": D("2021-08-31")},
            # 수집을 마쳤는데 시세가 한 건도 없다 — 커버리지는 "받으러 갔다"는 기록이지
            # "값이 있다"는 기록이 아니다.
            {"stock_id": empty_id, "covered_from": D("2021-08-01"),
             "covered_through": D("2021-08-31")},
        ], preserve=())
        await s.commit()

    app = create_app()

    async def _override():
        async with session_factory() as s:
            yield s

    app.dependency_overrides[get_session] = _override
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


BASE = {"principal": "86997", "principalCurrency": "KRW", "reinvest": "true"}


class Test상장_이전:
    async def test_상장_이전_시작일은_400이다(self, client) -> None:
        """FR-005 — 조용히 첫 거래일로 옮기지 않는다."""
        res = await client.get("/api/stocks/simulation", params={
            **BASE, "market": "KRX", "symbol": "005930.KS",
            "start": "1960-01-01", "end": "2021-08-31"})
        assert res.status_code == 400
        assert res.json()["status"] == "before_listing"

    async def test_이유에_실제_시작_가능일이_드러난다(self, client) -> None:
        res = await client.get("/api/stocks/simulation", params={
            **BASE, "market": "KRX", "symbol": "005930.KS",
            "start": "1960-01-01", "end": "2021-08-31"})
        assert "2021-08-02" in res.json()["message"]


class Test시세_없음:
    async def test_받아_보고도_없으면_빈_표가_아니라_사유다(self, client) -> None:
        """FR-004, SC-016 — 빈 표를 보여주면 성과가 0이라고 읽는다."""
        res = await client.get("/api/stocks/simulation", params={
            **BASE, "market": "KRX", "symbol": "888888.KS",
            "start": "2021-08-01", "end": "2021-08-31"})
        assert res.status_code != 200
        body = res.json()
        assert "rows" not in body
        assert body["status"] == "no_price_data"

    async def test_받아_본_적이_없으면_수집부터_한다(self, client) -> None:
        """FR-047 — 받으러 간 적이 없는데 "시세가 없다"고 말하면 틀린 결론이다.

        커버리지는 **받으러 갔다**는 기록이지 **값이 있다**는 기록이 아니다. 둘을
        섞으면 처음 고른 종목이 전부 "시세 없음"으로 보인다.
        """
        res = await client.get("/api/stocks/simulation", params={
            **BASE, "market": "KRX", "symbol": "999999.KS",
            "start": "2021-08-01", "end": "2021-08-31"})
        assert res.status_code == 202
        assert res.json()["status"] == "collecting"
        assert "rows" not in res.json()

    async def test_알_수_없는_종목은_404다(self, client) -> None:
        res = await client.get("/api/stocks/simulation", params={
            **BASE, "market": "KRX", "symbol": "000000.KS",
            "start": "2021-08-01", "end": "2021-08-31"})
        assert res.status_code == 404
        assert res.json()["status"] == "unknown_stock"


class Test질의_검증:
    async def test_지원하지_않는_원금_통화는_400이다(self, client) -> None:
        res = await client.get("/api/stocks/simulation", params={
            "market": "KRX", "symbol": "005930.KS", "start": "2021-08-01",
            "principal": "1000", "principalCurrency": "GBP", "reinvest": "true"})
        assert res.status_code == 400
        assert res.json()["status"] == "invalid_query"

    async def test_원금이_0_이하면_400이다(self, client) -> None:
        for amount in ("0", "-1"):
            res = await client.get("/api/stocks/simulation", params={
                **BASE, "market": "KRX", "symbol": "005930.KS",
                "start": "2021-08-01", "principal": amount})
            assert res.status_code == 400, amount

    async def test_원금이_숫자가_아니면_400이다(self, client) -> None:
        """문자열로 받으므로 검증이 필요하다. 조용히 0으로 떨어지면 안 된다."""
        res = await client.get("/api/stocks/simulation", params={
            **BASE, "market": "KRX", "symbol": "005930.KS",
            "start": "2021-08-01", "principal": "일억"})
        assert res.status_code == 400


class Test시세_출처가_모르는_종목:
    """006 T025 — FR-032. **"시세가 없다"와 "시세 출처에서 찾지 못했다"를 구별한다.**

    둘을 섞으면 식별자 변환 결함이 "데이터 없는 종목"으로 위장돼 고쳐지지 않는다. 005는 앞의
    경우도 `unknown_stock`으로 냈고, 수집이 그 사유로 실패해도 다음 요청이 수집을 다시 시작해
    화면은 "받고 있습니다"를 되풀이했다.
    """

    class _UnknownSymbolSource:
        async def fetch_chart(self, symbol, date_from, date_to):  # type: ignore[no-untyped-def]
            from src.ingestion.yahoo.errors import StockSymbolNotFound

            raise StockSymbolNotFound("시세 출처가 그 종목을 알지 못합니다.")

        async def delay_between_chunks(self) -> None:
            return None

    async def _collect_once(self, client, session_factory) -> None:  # type: ignore[no-untyped-def]
        import asyncio

        from src.worker.stock_queue import get_stock_queue
        from src.worker.stock_worker import run_stock_job

        first = await client.get("/api/stocks/simulation", params={
            **BASE, "market": "KRX", "symbol": "999999.KS",
            "start": "2021-08-02", "end": "2021-08-31"})
        assert first.status_code == 202
        work = await asyncio.wait_for(get_stock_queue().pop(), timeout=1)
        await run_stock_job(session_factory, self._UnknownSymbolSource(), work)
        get_stock_queue().done(work.stock_id)

    async def test_출처가_모르면_price_symbol_unknown이다(self, client, session_factory) -> None:
        await self._collect_once(client, session_factory)
        res = await client.get("/api/stocks/simulation", params={
            **BASE, "market": "KRX", "symbol": "999999.KS",
            "start": "2021-08-02", "end": "2021-08-31"})
        assert res.status_code == 404
        assert res.json()["status"] == "price_symbol_unknown"
        assert "rows" not in res.json()

    async def test_수집을_되풀이하지_않는다(self, client, session_factory) -> None:
        from sqlalchemy import func

        from src.db.models import StockCollectionJob

        await self._collect_once(client, session_factory)
        for _ in range(2):
            await client.get("/api/stocks/simulation", params={
                **BASE, "market": "KRX", "symbol": "999999.KS",
                "start": "2021-08-02", "end": "2021-08-31"})
        async with session_factory() as s:
            jobs = (await s.execute(
                select(func.count()).select_from(StockCollectionJob))).scalar()
        assert jobs == 1

    async def test_받았는데_시세가_없으면_no_price_data다(self, client) -> None:
        """구별의 다른 쪽 — 005 그대로."""
        res = await client.get("/api/stocks/simulation", params={
            **BASE, "market": "KRX", "symbol": "888888.KS",
            "start": "2021-08-01", "end": "2021-08-31"})
        assert res.json()["status"] == "no_price_data"

    async def test_우리_DB에_없는_종목은_unknown_stock과_다시_고르기다(self, client) -> None:
        res = await client.get("/api/stocks/simulation", params={
            **BASE, "market": "KRX", "symbol": "000000.KS",
            "start": "2021-08-01", "end": "2021-08-31"})
        assert res.status_code == 404
        assert res.json()["status"] == "unknown_stock"
        assert res.json()["action"] == "reselect"

    async def test_진행_스트림이_사유를_구별해_알린다(self, client, session_factory) -> None:
        from src.api.routes.stock_progress import stream_body
        from src.db.models import StockCollectionJob

        await self._collect_once(client, session_factory)
        async with session_factory() as s:
            job_id = int((await s.execute(select(StockCollectionJob.id))).scalar_one())
            frames = [f async for f in stream_body(s, job_id, max_frames=1)]
        failed = next(f for f in frames if f.startswith("event: failed"))
        assert "price_symbol_unknown" in failed
        assert "시세 출처가 그 종목을 알지 못합니다" in failed
