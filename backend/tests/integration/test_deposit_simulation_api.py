"""예금 시뮬레이션 API (T013) — 008 FR-002~FR-007, FR-010, FR-016, FR-019, FR-024, FR-026,
FR-035, SC-005, SC-006, contracts/rest-api `GET /api/deposit/simulation`.

- **받지 않은 달이 있고 오늘(한국 시간) 확인하지 않았으면 202** — 결과를 싣지 않는다
- 오늘 확인했는데 없는 달은 **미발표**다 — 200, 그 달부터 잠정(`provisionalFrom`)
- 오늘 확인이 실패했고 받아 둔 금리로 답할 수 있으면 200 + `recheckFailed` — 같은 날 202가
  되풀이되지 않는다
- 금액은 원 단위 정수 문자열, 금리는 출처 문자열 그대로, 행은 최신순
"""
from __future__ import annotations

import datetime as dt

import pytest
from httpx2 import ASGITransport, AsyncClient

from src.api.main import create_app
from src.db.models import JobStatus
from src.db.session import get_session
from src.repository import deposit_job
from src.worker.deposit_queue import get_deposit_queue
from tests.integration.deposit_support import NOW_UTC, TODAY, seed_rates

D = dt.date.fromisoformat
BASE = {"institution": "commercial_bank", "start": "2020-01-15", "principal": "10000000"}


@pytest.fixture
async def client(session_factory, monkeypatch):  # type: ignore[no-untyped-def]
    monkeypatch.setattr("src.api.services.deposit_simulation.kst_today", lambda: TODAY)
    app = create_app()

    async def _session():  # type: ignore[no-untyped-def]
        async with session_factory() as s:
            yield s

    app.dependency_overrides[get_session] = _session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        yield c


async def simulate(client, **over: str):  # type: ignore[no-untyped-def]
    return await client.get("/api/deposit/simulation", params={**BASE, **over})


class Test수집_판정:
    async def test_받은_적이_없으면_202와_필요한_구간이다(self, client) -> None:  # type: ignore[no-untyped-def]
        response = await simulate(client)
        assert response.status_code == 202
        body = response.json()
        assert body["status"] == "collecting" and body["institution"] == "commercial_bank"
        assert (body["missingFrom"], body["missingThrough"]) == ("2020-01", "2026-10")
        assert body["progressUrl"] == f"/api/deposit/progress?jobId={body['jobId']}"
        assert "summary" not in body
        assert get_deposit_queue().is_active("commercial_bank")

    async def test_오늘_확인하지_않았으면_202다(self, client, session_factory) -> None:  # type: ignore[no-untyped-def]
        await seed_rates(session_factory, checked_on=D("2026-10-03"))
        response = await simulate(client)
        assert response.status_code == 202
        assert (response.json()["missingFrom"], response.json()["missingThrough"]) == (
            "2026-09", "2026-10")

    async def test_오늘_확인했으면_없는_달은_미발표_200(self, client, session_factory) -> None:  # type: ignore[no-untyped-def]
        await seed_rates(session_factory)
        response = await simulate(client)
        assert response.status_code == 200
        assert not get_deposit_queue().is_active("commercial_bank")

    async def test_오늘_확인이_실패했으면_202를_되풀이하지_않는다(  # type: ignore[no-untyped-def]
            self, client, session_factory) -> None:
        await seed_rates(session_factory, checked_on=D("2026-10-03"))
        async with session_factory() as s:
            job_id, _ = await deposit_job.acquire_or_get_running(
                s, "commercial_bank", D("2020-01-01"), D("2026-10-01"), months_total=82)
            await deposit_job.finish_job(
                s, job_id, JobStatus.FAILED,
                error=deposit_job.job_error("network", "출처에 연결하지 못했습니다"), now=NOW_UTC)
            await s.commit()
        response = await simulate(client)
        assert response.status_code == 200
        assert response.json()["summary"]["recheckFailed"] == {
            "kind": "network", "reason": "출처에 연결하지 못했습니다"}


class Test결과:
    async def test_참조값_1의_요약과_회차와_행(self, client, session_factory) -> None:  # type: ignore[no-untyped-def]
        await seed_rates(session_factory)
        body = (await simulate(client)).json()
        assert body["institution"] == {"key": "commercial_bank", "name": "시중은행"}
        assert body["condition"] == {"start": "2020-01-15", "principal": "10000000",
                                     "interestTaxRate": "0.154000"}
        s = body["summary"]
        assert (s["principal"], s["profit"], s["returnRate"], s["asOf"], s["isFinal"]) == (
            "10000000", "1557207", "0.155721", "2026-10-04", True)
        assert s["currentTerm"] == {
            "joinedOn": "2026-01-15", "maturesOn": "2027-01-15", "rate": "2.84",
            "rateMonth": "2026-01", "principal": "11361267", "provisional": False}
        assert (s["provisionalFrom"], s["stopped"], s["recheckFailed"]) == (None, None, None)
        assert body["terms"][1] == {
            "no": 2, "joinedOn": "2021-01-15", "maturesOn": "2022-01-15", "rate": "0.97",
            "rateMonth": "2021-01", "provisional": False, "principal": "10137052",
            "interest": "98329", "tax": "15142", "afterTax": "83187"}
        rows = body["rows"]
        assert rows[0] == {
            "date": "2026-10-01", "kind": "month", "rate": "2.84", "rateMonth": "2026-01",
            "provisional": False, "principal": "11361267", "interest": "228955",
            "tax": "35259", "afterTax": "193696", "balance": "11554963",
            "profit": "1554963", "returnRate": "0.155496"}
        assert rows[-1]["kind"] == "join" and rows[-1]["date"] == "2020-01-15"
        reinvest = next(r for r in rows if r["date"] == "2021-01-15")
        assert reinvest["kind"] == "reinvest", "같은 날은 재예치가 만기보다 앞(최신순)"

    async def test_시작_달이_미발표면_잠정이다(self, client, session_factory) -> None:  # type: ignore[no-untyped-def]
        await seed_rates(session_factory)
        body = (await simulate(client, start="2026-09-15")).json()
        assert body["summary"]["provisionalFrom"] == "2026-09-15"
        assert body["summary"]["currentTerm"]["rateMonth"] == "2026-08"
        assert all(r["provisional"] for r in body["rows"])

    async def test_재예치_달이_결측이면_멈춘다(self, client, session_factory) -> None:  # type: ignore[no-untyped-def]
        await seed_rates(session_factory, drop=("2021-01",))
        s = (await simulate(client)).json()["summary"]
        assert s["stopped"] == {"date": "2021-01-15", "reason": "rate_missing", "month": "2021-01"}
        assert (s["isFinal"], s["asOf"], s["currentTerm"]) == (False, "2021-01-15", None)

    async def test_같은_입력은_같은_결과다(self, client, session_factory) -> None:  # type: ignore[no-untyped-def]
        await seed_rates(session_factory)
        assert (await simulate(client)).json() == (await simulate(client)).json()


class Test오류:
    async def test_첫_달보다_이르면_409와_시작_가능_날짜(self, client, session_factory) -> None:  # type: ignore[no-untyped-def]
        await seed_rates(session_factory)
        response = await simulate(client, start="2010-01-01")
        assert response.status_code == 409
        assert response.json()["status"] == "before_first_month"
        assert response.json()["startableFrom"] == "2012-01-01"

    async def test_시작_달이_결측이면_409(self, client, session_factory) -> None:  # type: ignore[no-untyped-def]
        await seed_rates(session_factory, drop=("2020-01",))
        response = await simulate(client)
        assert response.status_code == 409
        assert response.json() | {"message": ""} == {
            "status": "rate_missing", "month": "2020-01", "message": ""}

    async def test_모르는_투자처(self, client) -> None:  # type: ignore[no-untyped-def]
        response = await simulate(client, institution="kakao_bank")
        assert response.status_code == 400
        assert response.json()["status"] == "unknown_institution"
        assert response.json()["allowed"] == [
            "commercial_bank", "savings_bank", "credit_union", "mutual_finance", "saemaul"]

    async def test_원화가_아닌_원금은_막는다(self, client) -> None:  # type: ignore[no-untyped-def]
        response = await simulate(client, principalCurrency="USD")
        assert response.status_code == 400
        assert response.json()["status"] == "currency_not_allowed"
        assert response.json()["allowed"] == ["KRW"]

    async def test_시작일이_오늘보다_늦으면_400(self, client) -> None:  # type: ignore[no-untyped-def]
        response = await simulate(client, start="2026-10-05")
        assert response.status_code == 400
        assert response.json()["status"] == "start_after_end"
        assert response.json()["lastDay"] == "2026-10-04"

    @pytest.mark.parametrize("principal", ["0", "-5", "abc", "1000.5", "10,000"])
    async def test_원금은_양의_정수_원이다(self, client, principal: str) -> None:  # type: ignore[no-untyped-def]
        response = await simulate(client, principal=principal)
        assert response.status_code == 400
        assert response.json()["status"] == "invalid_query"

    async def test_커버리지는_있는데_금리가_없으면_404(self, client, session_factory) -> None:  # type: ignore[no-untyped-def]
        from src.repository import deposit_rate

        async with session_factory() as s:
            await deposit_rate.record_coverage(
                s, "commercial_bank", first_month=D("2012-01-01"), latest_month=D("2026-08-01"),
                checked_on=TODAY)
            await s.commit()
        response = await simulate(client)
        assert response.status_code == 404
        assert response.json()["status"] == "no_rate_data"
