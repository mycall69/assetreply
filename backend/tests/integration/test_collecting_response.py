"""수집 중 응답 (T092) — 005 FR-047~049, SC-028, SC-029, SC-001a.

**부분 결과를 200으로 내려보내지 않는다**(FR-049). 받은 만큼만 계산한 수익률은 값이
멀쩡해 보이지만 틀린 값이고, 사용자는 그것을 최종 결과로 읽는다. 표에 숫자가 있고
오류도 없으므로 알아챌 신호가 없다.
"""
from __future__ import annotations

import datetime as dt
import json
from decimal import Decimal

import pytest
from httpx2 import ASGITransport, AsyncClient
from sqlalchemy import func, select

from src.api.main import create_app
from src.api.routes.stock_progress import POLL_SECONDS, stream_body
from src.db.dialect import upsert
from src.db.models import Stock, StockCollectionJob, StockCoverage, StockPrice
from src.db.session import get_session

D = dt.date.fromisoformat

#: 받아 둔 구간은 2021-08~09뿐이다. 요청은 11월까지라 뒤가 비어 있다.
HELD = ["2021-08-02", "2021-08-03", "2021-09-01", "2021-09-02"]


@pytest.fixture
async def session_and_client(session_factory):
    async with session_factory() as s:
        await upsert(s, Stock, [{
            "market": "KRX", "symbol": "005930.KS", "name": "삼성전자",
            "currency": "KRW", "first_available_date": D("1975-06-11")}])
        await s.commit()
        stock_id = int((await s.execute(select(Stock))).scalar_one().id)
        await upsert(s, StockPrice, [{
            "stock_id": stock_id, "quote_date": D(day),
            "open_raw": Decimal("40000"), "close_raw": Decimal("40000"),
            "close_adjusted": Decimal("40000"), "source": "yahoo:chart"}
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
        yield session_factory, ac


@pytest.fixture
async def client(session_and_client):
    return session_and_client[1]


PARAMS = {"market": "KRX", "symbol": "005930.KS", "start": "2021-08-01",
          "principal": "86997", "principalCurrency": "KRW", "reinvest": "true",
          "end": "2021-11-30"}

COVERED = {**PARAMS, "end": "2021-09-30"}


class Test수집_중_응답:
    async def test_미수집_구간이_있으면_202다(self, client) -> None:
        """FR-047 — 001·002가 정한 수집 중 응답 규약을 잇는다."""
        res = await client.get("/api/stocks/simulation", params=PARAMS)
        assert res.status_code == 202, res.text
        assert res.json()["status"] == "collecting"

    async def test_부분_결과를_함께_주지_않는다(self, client) -> None:
        """FR-049, SC-029 — 숫자가 보이면 사용자는 그것을 최종 결과로 읽는다."""
        res = await client.get("/api/stocks/simulation", params=PARAMS)
        body = res.json()
        assert "rows" not in body
        assert "summary" not in body

    async def test_어느_구간이_비었는지_밝힌다(self, client) -> None:
        res = await client.get("/api/stocks/simulation", params=PARAMS)
        body = res.json()
        assert body["missingFrom"] == "2021-10-01"
        assert body["missingThrough"] == "2021-11-30"

    async def test_구독할_주소를_준다(self, client) -> None:
        """부분 결과를 보여주지 않는 대신 완료 시점을 알려야 한다."""
        body = (await client.get("/api/stocks/simulation", params=PARAMS)).json()
        assert body["progressUrl"] == f"/api/stocks/progress?jobId={body['jobId']}"

    async def test_차트도_같은_202를_준다(self, client) -> None:
        """표만 막고 차트를 내보내면 한쪽은 비어 있고 한쪽은 틀린 값이 보인다."""
        res = await client.get("/api/stocks/simulation/series", params=PARAMS)
        assert res.status_code == 202, res.text
        assert res.json()["status"] == "collecting"

    async def test_다_받은_구간은_200이다(self, client) -> None:
        """받아 둔 구간만 물으면 수집을 시작하지 않는다 — 호출 한도를 낭비한다."""
        res = await client.get("/api/stocks/simulation", params=COVERED)
        assert res.status_code == 200, res.text
        assert len(res.json()["rows"]) > 0


class Test중복_수집:
    async def test_이미_진행_중이면_새_작업을_만들지_않는다(
        self, session_and_client
    ) -> None:
        """FR-048, SC-028 — 중복 수집은 오류 없이 성공하면서 호출만 두 배로 쓴다."""
        factory, client = session_and_client
        first = (await client.get("/api/stocks/simulation", params=PARAMS)).json()
        second = (await client.get("/api/stocks/simulation", params=PARAMS)).json()
        assert first["jobId"] == second["jobId"]

        async with factory() as s:
            count = (await s.execute(
                select(func.count()).select_from(StockCollectionJob))).scalar_one()
        assert count == 1, f"작업이 {count}개 생겼다"

    async def test_표와_차트가_같은_작업을_가리킨다(self, session_and_client) -> None:
        """둘이 따로 작업을 만들면 같은 구간을 두 번 받는다."""
        factory, client = session_and_client
        table = (await client.get("/api/stocks/simulation", params=PARAMS)).json()
        chart = (await client.get(
            "/api/stocks/simulation/series", params=PARAMS)).json()
        assert table["jobId"] == chart["jobId"]


class Test진행_표시:
    async def test_첫_스냅샷이_기다리지_않고_나온다(self, session_and_client) -> None:
        """SC-001a — 처음에 한 박자 쉬면 사용자는 아무 일도 안 일어난다고 읽는다."""
        factory, client = session_and_client
        body = (await client.get("/api/stocks/simulation", params=PARAMS)).json()
        async with factory() as s:
            stream = stream_body(s, body["jobId"], max_frames=1)
            first = await anext(stream)
        assert "snapshot" in first
        assert str(body["jobId"]) in first

    def test_갱신_간격이_십초를_넘지_않는다(self) -> None:
        """SC-001a — 간격이 길면 진행이 멈춘 것처럼 보여 사용자가 새로고침한다."""
        assert POLL_SECONDS <= 10


def snapshot_data(frame: str) -> dict[str, object]:
    data: dict[str, object] = json.loads(frame.split("data: ", 1)[1])
    return data


class Test받은_날:
    """006 T113 — FR-045a, research R6-19, contracts/rest-api 진행 스트림. 반복 2026-10-03.

    진행을 **받은 날 / 받을 날**(달력 일수)로 보인다. 받을 날은 작업 구간의 일수, 받은 날은
    그 구간 가운데 커버리지가 덮는 일수다 — 커버리지는 청크마다 커밋되므로 따로 세지 않는다.
    """

    async def test_작업_구간의_일수와_받은_날을_싣는다(self, session_and_client) -> None:
        factory, client = session_and_client
        body = (await client.get("/api/stocks/simulation", params=PARAMS)).json()
        async with factory() as s:
            data = snapshot_data(await anext(stream_body(s, body["jobId"], max_frames=1)))
        # 비어 있던 2021-10-01~2021-11-30 — 61일. 아직 받은 날은 없다.
        assert (data["rangeStart"], data["rangeEnd"]) == ("2021-10-01", "2021-11-30")
        assert (data["daysDone"], data["daysTotal"]) == (0, 61)
        # 구간 수는 그대로 남는다(호환).
        assert "chunksDone" in data and "chunksTotal" in data

    async def test_구간을_받을수록_받은_날이_는다(self, session_and_client) -> None:
        factory, client = session_and_client
        body = (await client.get("/api/stocks/simulation", params=PARAMS)).json()
        async with factory() as s:
            stock_id = int((await s.execute(select(Stock))).scalar_one().id)
            # 워커가 10월을 받아 커버리지가 10-31까지 늘었다.
            await upsert(s, StockCoverage, [{
                "stock_id": stock_id, "covered_from": D("2021-08-01"),
                "covered_through": D("2021-10-31")}], preserve=())
            await s.commit()
        async with factory() as s:
            data = snapshot_data(await anext(stream_body(s, body["jobId"], max_frames=1)))
        assert (data["daysDone"], data["daysTotal"]) == (31, 61)

    async def test_한_연결에서_진행이_갱신된다(self, session_and_client, monkeypatch) -> None:
        """SC-017 — 실제 스트림은 연결 하나(세션 하나)로 끝까지 간다.

        그 세션이 처음 읽은 값에 머물면, 압축을 고쳐도 화면은 `0 / 61일`에서 멈추고 완료 신호도
        오지 않는다. 워커는 다른 세션에서 커버리지와 작업을 커밋한다.
        """
        import src.api.routes.stock_progress as progress

        monkeypatch.setattr(progress, "POLL_SECONDS", 0)
        factory, client = session_and_client
        job_id = (await client.get("/api/stocks/simulation", params=PARAMS)).json()["jobId"]
        async with factory() as s:
            stream = stream_body(s, job_id, max_frames=5)
            first = snapshot_data(await anext(stream))
            async with factory() as worker:
                stock_id = int((await worker.execute(select(Stock))).scalar_one().id)
                await upsert(worker, StockCoverage, [{
                    "stock_id": stock_id, "covered_from": D("2021-08-01"),
                    "covered_through": D("2021-10-31")}], preserve=())
                job = await worker.get(StockCollectionJob, job_id)
                assert job is not None
                job.chunks_done = 1
                await worker.commit()
            second = snapshot_data(await anext(stream))
        assert (first["daysDone"], second["daysDone"]) == (0, 31)
        assert second["chunksDone"] == 1

    async def test_한_연결에서_완료를_알린다(self, session_and_client, monkeypatch) -> None:
        """완료 신호가 오지 않으면 화면은 결과를 다시 요청하지 않는다(005 FR-049)."""
        import src.api.routes.stock_progress as progress
        from src.db.models import JobStatus

        monkeypatch.setattr(progress, "POLL_SECONDS", 0)
        factory, client = session_and_client
        job_id = (await client.get("/api/stocks/simulation", params=PARAMS)).json()["jobId"]
        async with factory() as s:
            stream = stream_body(s, job_id, max_frames=5)
            await anext(stream)
            async with factory() as worker:
                job = await worker.get(StockCollectionJob, job_id)
                assert job is not None
                job.status = JobStatus.SUCCEEDED
                job.chunks_done = job.chunks_total
                await worker.commit()
            frames = [frame async for frame in stream]
        assert any(frame.startswith("event: completed") for frame in frames), frames

