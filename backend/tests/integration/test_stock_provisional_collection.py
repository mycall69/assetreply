"""잠정 봉의 날은 받은 구간이 아니다 (버그 stock-provisional-bar) — 005 FR-044·FR-047~049.

출처가 아직 확정하지 않은 봉(시가 0·장중 값)은 어댑터가 행을 만들지 않고 그 첫 날을 알린다. 수집이
그날을 커버리지에 넣으면 출처가 나중에 바로잡아도 다시 받지 않는다 — 틀린 값(또는 빈 날)이 영영
남는다. 거꾸로 조회가 커버리지만 보면 조회 → 202 → 수집 → 같은 잠정 봉 → 202가 되풀이된다(화면이
"받고 있습니다"에 갇힌다). 방금 끝난 수집이 그 구간을 요청했으면 설정한 시간 동안 다시 받지 않고
받아 둔 날까지로 답한다.

**스텁 소스를 쓰며 네트워크 없이 통과해야 한다**(헌법 원칙 III).
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
    JobStatus,
    Stock,
    StockCollectionJob,
    StockCoverage,
    StockPrice,
)
from src.db.session import get_session
from src.ingestion.yahoo.parse import ChartData, ChartFetch, DailyPrice, RawBody
from src.repository.stock import get_coverage
from src.worker.stock_runner import collect_range

D = dt.date.fromisoformat


class ProvisionalSource:
    """평일마다 확정 봉을 주되, `provisional` 날부터는 행 없이 잠정으로 알린다."""

    def __init__(self, provisional: dt.date) -> None:
        self.provisional = provisional
        self.requests: list[tuple[dt.date, dt.date]] = []

    async def fetch_chart(self, symbol: str, date_from: dt.date, date_to: dt.date) -> ChartFetch:
        self.requests.append((date_from, date_to))
        days, day = [], date_from
        while day <= date_to and day < self.provisional:
            if day.weekday() < 5:
                days.append(day)
            day += dt.timedelta(days=1)
        hit = self.provisional if date_from <= self.provisional <= date_to else None
        return ChartFetch(
            data=ChartData(
                currency="KRW", first_trade_date=None,
                prices=[DailyPrice(d, Decimal("1000"), Decimal("1010"), Decimal("1010"))
                        for d in days],
                provisional_from=hit),
            raws=[RawBody("chart", '{"chunk": true}', 200, date_from, date_to)])

    async def delay_between_chunks(self) -> None:
        return None


@pytest.fixture
async def stock_id(session_factory) -> int:
    async with session_factory() as s:
        await upsert(s, Stock, [{
            "market": "KRX", "symbol": "005930.KS", "name": "삼성전자", "currency": "KRW",
            "first_available_date": D("1975-06-11")}])
        await s.commit()
        return int((await s.execute(select(Stock))).scalar_one().id)


class Test수집:
    async def test_잠정_날은_커버리지에_넣지_않는다(self, session_factory, stock_id) -> None:
        source = ProvisionalSource(D("2026-10-06"))
        async with session_factory() as s:
            await collect_range(s, source, stock_id, "005930.KS", D("2026-09-28"), D("2026-10-06"))
            assert await get_coverage(s, stock_id) == (D("2026-09-28"), D("2026-10-05"))
            days = list((await s.execute(
                select(StockPrice.quote_date).where(StockPrice.stock_id == stock_id))).scalars())
        assert D("2026-10-06") not in days
        assert max(days) == D("2026-10-05")

    async def test_다음_수집이_그날부터_다시_받는다(self, session_factory, stock_id) -> None:
        source = ProvisionalSource(D("2026-10-06"))
        async with session_factory() as s:
            await collect_range(s, source, stock_id, "005930.KS", D("2026-09-28"), D("2026-10-06"))
            source.provisional = D("2026-12-31")  # 출처가 그날을 굳혔다
            await collect_range(s, source, stock_id, "005930.KS", D("2026-09-28"), D("2026-10-06"))
            assert await get_coverage(s, stock_id) == (D("2026-09-28"), D("2026-10-06"))
        assert source.requests == [
            (D("2026-09-28"), D("2026-10-06")), (D("2026-10-06"), D("2026-10-06"))]

    async def test_잠정_날_뒤의_청크는_받지_않는다(self, session_factory, stock_id) -> None:
        """커버리지는 연속 구간 하나다 — 뒤 청크를 기록하면 잠정 날이 함께 덮인다."""
        source = ProvisionalSource(D("2021-12-30"))
        async with session_factory() as s:
            await collect_range(s, source, stock_id, "005930.KS", D("2020-01-01"), D("2023-12-31"))
            assert await get_coverage(s, stock_id) == (D("2020-01-01"), D("2021-12-29"))
        assert source.requests == [(D("2020-01-01"), D("2021-12-30"))]

    async def test_첫날이_잠정이면_커버리지가_생기지_않는다(
        self, session_factory, stock_id
    ) -> None:
        source = ProvisionalSource(D("2026-10-06"))
        async with session_factory() as s:
            await collect_range(s, source, stock_id, "005930.KS", D("2026-10-06"), D("2026-10-06"))
            assert await get_coverage(s, stock_id) is None


#: 받아 둔 구간은 2021-08~09뿐이다(마지막 거래일 09-30). 요청 끝은 10-01 — 출처가 잠정 봉을
#: 준 날이다.
HELD = ["2021-08-02", "2021-08-03", "2021-09-01", "2021-09-30"]
PARAMS = {"market": "KRX", "symbol": "005930.KS", "start": "2021-08-01", "principal": "86997",
          "principalCurrency": "KRW", "reinvest": "true", "end": "2021-10-01"}


@pytest.fixture
async def client(session_factory, stock_id):
    async with session_factory() as s:
        await upsert(s, StockPrice, [{
            "stock_id": stock_id, "quote_date": D(day), "open_raw": Decimal("40000"),
            "close_raw": Decimal("40000"), "close_adjusted": Decimal("40000"),
            "source": "yahoo:chart"}
            for day in HELD])
        await upsert(s, StockCoverage, [{
            "stock_id": stock_id, "covered_from": D("2021-08-01"),
            "covered_through": D("2021-09-30")}], preserve=())
        await s.commit()
    app = create_app()

    async def _override():
        async with session_factory() as s:
            yield s

    app.dependency_overrides[get_session] = _override
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


async def add_job(session_factory, stock_id: int, *, status: JobStatus, minutes_ago: int,
                  range_start: str = "2021-10-01", range_end: str = "2021-10-01") -> None:
    async with session_factory() as s:
        s.add(StockCollectionJob(
            stock_id=stock_id, range_start=D(range_start), range_end=D(range_end), status=status,
            chunks_total=1, chunks_done=1,
            finished_at=dt.datetime.now() - dt.timedelta(minutes=minutes_ago)))
        await s.commit()


async def job_count(session_factory) -> int:
    async with session_factory() as s:
        count = select(func.count()).select_from(StockCollectionJob)
        return int((await s.execute(count)).scalar_one())


class Test되풀이_막기:
    async def test_방금_그_구간을_받았으면_받아_둔_날까지로_답한다(
        self, session_factory, stock_id, client
    ) -> None:
        await add_job(session_factory, stock_id, status=JobStatus.SUCCEEDED, minutes_ago=1)
        res = await client.get("/api/stocks/simulation", params=PARAMS)
        assert res.status_code == 200, res.text
        assert res.json()["summary"]["asOf"] == "2021-09-30"
        assert await job_count(session_factory) == 1

    async def test_차트도_같다(self, session_factory, stock_id, client) -> None:
        await add_job(session_factory, stock_id, status=JobStatus.SUCCEEDED, minutes_ago=1)
        res = await client.get("/api/stocks/simulation/series", params=PARAMS)
        assert res.status_code == 200, res.text

    async def test_시간이_지나면_다시_받는다(self, session_factory, stock_id, client) -> None:
        await add_job(session_factory, stock_id, status=JobStatus.SUCCEEDED, minutes_ago=31)
        res = await client.get("/api/stocks/simulation", params=PARAMS)
        assert res.status_code == 202, res.text
        assert res.json()["missingFrom"] == "2021-10-01"

    async def test_시간은_설정이다(self, session_factory, stock_id, client, monkeypatch) -> None:
        monkeypatch.setenv("STOCK_PROVISIONAL_RETRY_MINUTES", "5")
        await add_job(session_factory, stock_id, status=JobStatus.SUCCEEDED, minutes_ago=10)
        assert (await client.get("/api/stocks/simulation", params=PARAMS)).status_code == 202

    async def test_마지막_작업이_실패였으면_다시_받는다(
        self, session_factory, stock_id, client
    ) -> None:
        await add_job(session_factory, stock_id, status=JobStatus.FAILED, minutes_ago=1)
        assert (await client.get("/api/stocks/simulation", params=PARAMS)).status_code == 202

    async def test_그_구간을_요청하지_않은_작업이면_받는다(
        self, session_factory, stock_id, client
    ) -> None:
        """다른 구간을 받은 작업은 근거가 아니다 — 요청 끝을 늘리면 늘린 만큼 받는다."""
        await add_job(session_factory, stock_id, status=JobStatus.SUCCEEDED, minutes_ago=1,
                      range_start="2021-08-01", range_end="2021-09-30")
        assert (await client.get("/api/stocks/simulation", params=PARAMS)).status_code == 202
