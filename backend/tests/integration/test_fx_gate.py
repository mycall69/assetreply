"""시뮬레이션의 환율 판정 (T047) — 006 FR-043, FR-043a, FR-044, FR-045, FR-046, FR-047, SC-010,
research R6-10, contracts/rest-api 5·6절.

**필요한 구간 전체를 본다**(FR-044). 시작일 환율만 보면 외환 수집이 멈춘 뒤의 행들이 마지막으로 받은
환율로 평가되는데, 보드의 요약은 낡은 환율로 계산된 값이다.

**수집 요청은 고쳐진 `ensure_background_job`을 거친다**(T092, analyze A1). 판정이 큐를 직접 부르거나
작업·점유를 만들면 외환 화면과 시뮬레이션이 같은 상황을 다르게 말한다.
"""
from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest
from httpx2 import ASGITransport, AsyncClient
from sqlalchemy import func, select, update

from src.api.main import create_app
from src.db.dialect import upsert
from src.db.models import (
    Currency,
    FxCollectionJob,
    FxCollectionLock,
    FxCoverage,
    FxRate,
    JobStatus,
    Stock,
    StockCollectionJob,
    StockCoverage,
    StockPrice,
)
from src.db.session import get_session
from src.worker.queue import get_queue

D = dt.date.fromisoformat
DAYS = ["2021-08-02", "2021-09-01", "2021-10-01"]
SIM = {"market": "NASDAQ", "symbol": "AAPL", "start": "2021-08-01", "end": "2021-10-31",
       "principal": "1000000", "principalCurrency": "KRW", "reinvest": "true"}


async def count(session_factory, model) -> int:  # type: ignore[no-untyped-def]
    async with session_factory() as s:
        return int((await s.execute(select(func.count()).select_from(model))).scalar_one())


@pytest.fixture
async def stock_id(session_factory) -> int:  # type: ignore[no-untyped-def]
    """주식 시세는 다 받아 둔 상태. 환율만 다르게 둔다."""
    async with session_factory() as s:
        # 1962년부터 시세가 있는 종목 — 오래된 시작일의 판정 순서를 상장 이전 판정에 가리지 않는다.
        await upsert(s, Stock, [{
            "market": "NASDAQ", "symbol": "AAPL", "name": "Apple Inc.",
            "currency": "USD", "first_available_date": D("1962-01-02")}])
        await s.commit()
        sid = int((await s.execute(select(Stock.id))).scalar_one())
        await upsert(s, StockPrice, [{
            "stock_id": sid, "quote_date": D(d), "open_raw": Decimal("100"),
            "close_raw": Decimal("100"), "close_adjusted": Decimal("100"),
            "source": "yahoo:chart"} for d in DAYS])
        await upsert(s, StockCoverage, [{
            "stock_id": sid, "covered_from": D("1962-01-01"),
            "covered_through": D("2021-10-31")}], preserve=())
        await s.commit()
        return sid


async def fx_rows(session_factory, through: str = "2021-10-31") -> None:  # type: ignore[no-untyped-def]
    async with session_factory() as s:
        await upsert(s, FxRate, [{
            "currency_code": "USD", "quote_date": D(d), "base_rate": Decimal("1150"),
            "quote_unit": 1, "source": "ECOS:731Y001", "is_provisional": False}
            for d in ["2021-07-30", *DAYS] if d <= through])
        await upsert(s, FxCoverage, [{
            "currency_code": "USD", "covered_from": D("2000-01-01"),
            "covered_through": D(through)}], preserve=())
        await s.commit()


@pytest.fixture
async def client(session_factory, stock_id, monkeypatch):  # type: ignore[no-untyped-def]
    # 탐색 시작일을 고정한다 — 저장소 `.env`의 값에 기대면 판정 경계가 환경마다 달라진다.
    monkeypatch.setenv("ECOS_PROBE_START_USD", "2000-01-01")
    app = create_app()

    async def _override():  # type: ignore[no-untyped-def]
        async with session_factory() as s:
            yield s

    app.dependency_overrides[get_session] = _override
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


async def simulate(client: AsyncClient, **over: str):  # type: ignore[no-untyped-def]
    return await client.get("/api/stocks/simulation", params={**SIM, **over})


class Test수집_요청:
    async def test_커버리지가_없으면_202와_queued(self, client, session_factory) -> None:
        """FR-043 — "환율 없음"으로 끝내면 원화로 시뮬레이션할 수 없다고 읽힌다."""
        res = await simulate(client)
        assert res.status_code == 202, res.text
        body = res.json()
        assert body["status"] == "collecting"
        assert body["fx"] == {"currency": "USD", "state": "queued", "busyWith": None,
                              "missingFrom": "2021-08-01", "missingThrough": "2021-10-31"}
        # 주식 시세는 다 있으므로 주식 수집 필드가 없다 (contracts 5절)
        assert "jobId" not in body and "progressUrl" not in body
        assert "rows" not in body

    async def test_큐로_넘기고_작업과_점유를_직접_만들지_않는다(
            self, client, session_factory) -> None:
        """T092 — 작업과 점유는 워커의 run_once만 만든다. 미리 만들면 실행되지 않는 작업이 된다."""
        await simulate(client)
        assert get_queue().in_progress == "USD"
        assert await count(session_factory, FxCollectionJob) == 0
        assert await count(session_factory, FxCollectionLock) == 0

    async def test_같은_통화가_진행_중이면_따라간다(self, client, session_factory) -> None:
        """FR-046 — 새로 시작하지 않는다."""
        async with session_factory() as s:
            job = FxCollectionJob(currency_code="USD", range_start=D("2000-01-01"),
                                  range_end=D("2021-10-31"), status=JobStatus.RUNNING,
                                  chunks_total=10, chunks_done=3)
            s.add(job)
            await s.flush()
            s.add(FxCollectionLock(scope="collection", currency_code="USD", job_id=job.id))
            await s.commit()
        body = (await simulate(client)).json()
        assert body["fx"]["state"] == "collecting"
        assert get_queue().size == 0                     # 큐에 또 넣지 않는다
        assert await count(session_factory, FxCollectionJob) == 1

    async def test_다른_통화가_진행_중이면_waiting과_그_통화(self, client, session_factory) -> None:
        """FR-046 — 거절을 삼키면 시뮬레이션은 영원히 "수집 중"이다."""
        assert await get_queue().request("JPY")
        body = (await simulate(client)).json()
        assert body["fx"]["state"] == "waiting"
        assert body["fx"]["busyWith"] == "JPY"
        assert get_queue().in_progress == "JPY"
        assert await count(session_factory, FxCollectionJob) == 0

    async def test_이미_큐에_있으면_queued(self, client) -> None:
        await simulate(client)
        body = (await simulate(client)).json()
        assert body["fx"]["state"] == "queued"
        assert get_queue().size == 1

    async def test_외환_화면과_같은_상황을_같게_말한다(self, client) -> None:
        """analyze A1 — 외환 화면이 먼저 띄운 수집을 시뮬레이션이 따라간다."""
        fx_screen = await client.get("/api/fx/series", params={
            "currency": "USD", "from": "2000-01-01", "to": "2021-10-31"})
        assert fx_screen.status_code == 202
        assert fx_screen.json()["state"] == "queued"
        body = (await simulate(client)).json()
        assert body["fx"]["state"] == fx_screen.json()["state"]
        assert get_queue().size == 1


class Test필요한_구간:
    async def test_커버리지가_중간에_멈췄으면_뒤를_받는다(self, client, session_factory) -> None:
        """FR-044 — 시작일은 덮지만 끝은 못 덮는다."""
        await fx_rows(session_factory, through="2021-09-15")
        body = (await simulate(client)).json()
        assert body["fx"]["missingFrom"] == "2021-09-16"
        assert body["fx"]["missingThrough"] == "2021-10-31"

    async def test_전부_덮으면_결과를_낸다(self, client, session_factory) -> None:
        await fx_rows(session_factory)
        res = await simulate(client)
        assert res.status_code == 200, res.text
        assert "fx" not in res.json()

    async def test_주식과_환율이_둘_다_비면_둘_다_싣고_결과가_없다(
            self, client, session_factory, stock_id) -> None:
        """FR-045 — 주식만 끝난 시점의 결과는 환율이 빠진 계산이다."""
        async with session_factory() as s:
            await s.execute(update(StockCoverage).where(StockCoverage.stock_id == stock_id)
                            .values(covered_through=D("2021-08-31")))
            await s.commit()
        body = (await simulate(client)).json()
        assert body["status"] == "collecting"
        assert isinstance(body["jobId"], int)
        assert body["missingFrom"] == "2021-09-01"
        assert body["fx"]["state"] == "queued"
        assert "rows" not in body

    async def test_원금과_종목_통화가_같으면_환율을_보지_않는다(self, client) -> None:
        res = await simulate(client, principalCurrency="USD", principal="1000")
        assert res.status_code == 200, res.text
        assert get_queue().size == 0

    async def test_수집이_끝났는데_값이_없으면_메우지_않는다(self, client, session_factory) -> None:
        """FR-047, 헌법 원칙 V — 다른 통화나 고정 환율로 메우지 않는다."""
        async with session_factory() as s:
            await upsert(s, FxCoverage, [{
                "currency_code": "USD", "covered_from": D("2000-01-01"),
                "covered_through": D("2021-10-31")}], preserve=())
            await s.commit()
        res = await simulate(client)
        assert res.status_code == 409
        assert res.json()["status"] == "fx_unavailable"
        assert "rows" not in res.json()


class Test수집으로_채울_수_없는_구간:
    """FR-043a — 두 사유를 섞지 않는다. 수집하지 않는다."""

    async def _first_quote(self, session_factory, day: str) -> None:  # type: ignore[no-untyped-def]
        async with session_factory() as s:
            await s.execute(update(Currency).where(Currency.code == "USD")
                            .values(first_available_date=D(day)))
            await s.commit()

    async def test_탐색_시작일_이전(self, client, session_factory) -> None:
        res = await simulate(client, start="1995-03-02")
        assert res.status_code == 409
        body = res.json()
        assert body["status"] == "fx_not_available_before"
        assert body["reason"] == "before_probe_start"
        assert body["currency"] == "USD"
        assert body["availableFrom"] == "2000-01-01"
        assert "설정" in body["message"]
        assert "출처에 없습니다" not in body["message"]

    async def test_최초_고시일_이전(self, client, session_factory) -> None:
        await self._first_quote(session_factory, "2005-01-03")
        res = await simulate(client, start="2003-06-02")
        body = res.json()
        assert res.status_code == 409
        assert body["reason"] == "before_first_quote"
        assert body["availableFrom"] == "2005-01-03"
        assert "출처에 없습니다" in body["message"]
        assert "설정" not in body["message"]

    async def test_탐색_시작일_판정이_먼저다(self, client, session_factory) -> None:
        """analyze N2 — 기록된 최초일은 수집한 범위 안의 첫 날이라 탐색 시작일보다 앞은 모른다."""
        await self._first_quote(session_factory, "2000-01-04")
        body = (await simulate(client, start="1980-01-02")).json()
        assert body["reason"] == "before_probe_start"

    async def test_수집하지_않고_되풀이하지도_않는다(self, client, session_factory) -> None:
        for _ in range(2):
            res = await simulate(client, start="1995-03-02")
            assert res.status_code == 409
        assert get_queue().size == 0 and get_queue().in_progress is None
        assert await count(session_factory, FxCollectionJob) == 0
        # 환율로 막힐 요청이면 주식 수집도 시작하지 않는다 — 받아도 결과를 낼 수 없다.
        assert await count(session_factory, StockCollectionJob) == 0
