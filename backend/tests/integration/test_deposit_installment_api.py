"""정기 적금 API (011 T043) — FR-022~FR-031, SC-005, contracts/rest-api §3, research R11-8·R11-9.

- 적금은 시중은행·상호금융만이다. 저축은행·신협·새마을금고는 400 `installment_not_available` —
  정기예금 금리로 대신하지 않는다(FR-029)
- 수집 판정은 두 계열(적금·정기예금)을 함께 본다
  - 받을 것이 있으면 둘 다 수집을 걸고 **적금 쪽을 먼저** 202(`series: "installment"`)로 돌려준다.
    그다음은 정기예금 쪽(`series: "deposit"`)이다
  - 계산 끝이 첫 만기 전이면 정기예금은 필요 없다
- 시작 가능 날짜 = max(적금 첫 달, 정기예금 첫 달 − 1년) — 정기예금의 첫 달을 그대로 내면 사용자가
  1년 늦은 날짜로 옮긴다
- 첫 가입 달 결측은 409 `rate_missing`, 그 뒤 가입 달 결측은 그날 멈춤(`stopped`)
- 200: 정기예금 원금 = 앞 정기예금 만기 금액 + 적금 만기 금액, 총 납입 원금 = 낸 회차 × 월 납입액,
  평가 = 적금 쪽 + 정기예금 쪽
- 금리 계열 키(`…_isav`)는 응답 어디에도 없다(research R11-2) — 화면은 (투자처, 상품)으로 말한다
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
from tests.integration.deposit_support import NOW_UTC, TODAY, rate_of, seed_rates

D = dt.date.fromisoformat
PATH = "/api/deposit/installment-simulation"
BASE = {"institution": "commercial_bank", "start": "2015-01-15", "amount": "1000000"}


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


async def both(session_factory, institution: str = "commercial_bank", **over: object) -> None:  # type: ignore[no-untyped-def]
    await seed_rates(session_factory, f"{institution}_isav", **over)  # type: ignore[arg-type]
    await seed_rates(session_factory, institution)


async def simulate(client, **over: str):  # type: ignore[no-untyped-def]
    return await client.get(PATH, params={**BASE, **over})


class Test입력:
    @pytest.mark.parametrize("institution", ["savings_bank", "credit_union", "saemaul"])
    async def test_적금_통계가_없는_투자처는_400이다(self, client, institution: str) -> None:  # type: ignore[no-untyped-def]
        response = await simulate(client, institution=institution)
        assert response.status_code == 400
        body = response.json()
        assert body["status"] == "installment_not_available"
        assert body["allowed"] == ["commercial_bank", "mutual_finance"]
        assert "정기적금 금리 통계가 없습니다" in body["message"]
        # 수집을 걸지 않는다 — 막힌 입력이면 받지도 않는다
        assert not get_deposit_queue().is_active(institution)

    async def test_모르는_투자처는_400_unknown_institution이다(self, client) -> None:  # type: ignore[no-untyped-def]
        response = await simulate(client, institution="commercial_bank_isav")
        assert (response.status_code, response.json()["status"]) == (400, "unknown_institution")

    @pytest.mark.parametrize("amount", ["0", "abc", "1000000.5", "-1"])
    async def test_월_납입액은_원_단위_양의_정수다(self, client, amount: str) -> None:  # type: ignore[no-untyped-def]
        response = await simulate(client, amount=amount)
        assert (response.status_code, response.json()["status"]) == (400, "invalid_query")


class Test수집_판정:
    async def test_둘_다_받지_않았으면_둘_다_걸고_적금_쪽을_먼저_202로_준다(self, client) -> None:  # type: ignore[no-untyped-def]
        response = await simulate(client)
        assert response.status_code == 202
        body = response.json()
        assert (body["status"], body["institution"], body["series"]) == (
            "collecting", "commercial_bank", "installment")
        assert (body["missingFrom"], body["missingThrough"]) == ("2015-01", "2026-10")
        assert body["progressUrl"] == f"/api/deposit/progress?jobId={body['jobId']}"
        queue = get_deposit_queue()
        assert queue.is_active("commercial_bank_isav") and queue.is_active("commercial_bank")
        assert "_isav" not in response.text

    async def test_적금을_받은_뒤_정기예금이_남았으면_다시_202다(  # type: ignore[no-untyped-def]
            self, client, session_factory) -> None:
        await seed_rates(session_factory, "commercial_bank_isav")
        response = await simulate(client)
        assert response.status_code == 202
        body = response.json()
        assert (body["series"], body["institution"]) == ("deposit", "commercial_bank")
        # 정기예금은 첫 만기 달부터 필요하다
        assert body["missingFrom"] == "2016-01"

    async def test_계산_끝이_첫_만기_전이면_정기예금은_필요_없다(  # type: ignore[no-untyped-def]
            self, client, session_factory) -> None:
        await seed_rates(session_factory, "commercial_bank_isav")
        response = await simulate(client, start="2026-01-15")
        assert response.status_code == 200
        assert not get_deposit_queue().is_active("commercial_bank")
        assert response.json()["deposits"] == []

    async def test_둘_다_받았으면_200이다(self, client, session_factory) -> None:  # type: ignore[no-untyped-def]
        await both(session_factory)
        response = await simulate(client)
        assert response.status_code == 200
        assert "_isav" not in response.text

    @pytest.mark.parametrize(("institution", "start", "startable"), [
        ("commercial_bank", "2010-12-15", "2011-01-01"),
        ("mutual_finance", "2011-12-15", "2012-01-01"),
    ])
    async def test_시작이_이르면_수집_전에_409이고_적금의_시작_가능_날짜다(  # type: ignore[no-untyped-def]
            self, client, session_factory, institution: str, start: str, startable: str) -> None:
        await both(session_factory, institution)
        response = await simulate(client, institution=institution, start=start)
        assert response.status_code == 409
        body = response.json()
        assert (body["status"], body["startableFrom"]) == ("before_first_month", startable)

    async def test_첫_가입_달이_결측이면_409_rate_missing이다(  # type: ignore[no-untyped-def]
            self, client, session_factory) -> None:
        await both(session_factory, drop=("2015-01",))
        response = await simulate(client)
        assert response.status_code == 409
        assert (response.json()["status"], response.json()["month"]) == ("rate_missing", "2015-01")

    async def test_오늘_확인이_실패했으면_받아_둔_금리로_답하고_알린다(  # type: ignore[no-untyped-def]
            self, client, session_factory) -> None:
        await both(session_factory, checked_on=D("2026-10-03"))
        async with session_factory() as s:
            job_id, _ = await deposit_job.acquire_or_get_running(
                s, "commercial_bank_isav", D("2015-01-01"), D("2026-10-01"), months_total=142)
            await deposit_job.finish_job(
                s, job_id, JobStatus.FAILED,
                error=deposit_job.job_error("network", "출처에 연결하지 못했습니다"), now=NOW_UTC)
            await s.commit()
        response = await simulate(client)
        assert response.status_code == 200
        assert response.json()["summary"]["recheckFailed"] == {
            "kind": "network", "reason": "출처에 연결하지 못했습니다"}


class Test결과:
    async def test_조건과_투자처(self, client, session_factory) -> None:  # type: ignore[no-untyped-def]
        await both(session_factory)
        body = (await simulate(client)).json()
        assert body["institution"] == {"key": "commercial_bank", "name": "시중은행"}
        assert body["condition"] == {
            "product": "installment", "start": "2015-01-15", "amount": "1000000",
            "interestTaxRate": "0.154000",
            "installmentItem": "예금은행 정기적금(1~2년 만기) 평균",
            "depositItem": "예금은행 정기예금(1년) 평균 — 일반·특수은행 포함"}

    async def test_첫_적금은_실측_금리의_단리다(self, client, session_factory) -> None:  # type: ignore[no-untyped-def]
        await both(session_factory)
        first = (await simulate(client)).json()["contracts"][0]
        assert first == {
            "no": 1, "joinedOn": "2015-01-15", "maturesOn": "2016-01-15",
            "rate": str(rate_of("commercial_bank_isav", "2015-01")), "rateMonth": "2015-01",
            "provisional": False, "monthly": "1000000", "paid": 12, "interest": "150800",
            "tax": "23223", "afterTax": "127577", "amount": "12127577"}

    async def test_정기예금_원금은_앞_정기예금_만기_금액과_적금_만기_금액의_합이다(  # type: ignore[no-untyped-def]
            self, client, session_factory) -> None:
        await both(session_factory)
        body = (await simulate(client)).json()
        contracts, deposits = body["contracts"], body["deposits"]
        assert (deposits[0]["fromDeposit"], deposits[0]["fromInstallment"]) == (
            "0", contracts[0]["amount"])
        assert deposits[0]["rate"] == str(rate_of("commercial_bank", "2016-01"))
        for before, after, saving in zip(deposits, deposits[1:], contracts[1:], strict=False):
            matured = int(before["principal"]) + int(before["afterTax"])
            assert int(after["fromDeposit"]) == matured
            assert int(after["fromInstallment"]) == int(saving["amount"])
            assert int(after["principal"]) == matured + int(saving["amount"])

    async def test_보드(self, client, session_factory) -> None:  # type: ignore[no-untyped-def]
        await both(session_factory)
        body = (await simulate(client)).json()
        s = body["summary"]
        paid = sum(c["paid"] for c in body["contracts"]) + s["currentInstallment"]["paid"]
        assert s["installments"] == paid
        assert int(s["contributed"]) == paid * 1000000
        assert int(s["installmentValue"]) + int(s["depositValue"]) == int(s["balance"])
        assert int(s["profit"]) == int(s["balance"]) - int(s["contributed"])
        assert (s["asOf"], s["isFinal"], s["provisionalFrom"], s["stopped"]) == (
            TODAY.isoformat(), True, None, None)
        # 2026-01-15 가입한 12번째 적금이 진행 중이다 — 2026-10-04까지 낸 회차는 9
        assert (s["currentInstallment"]["no"], s["currentInstallment"]["joinedOn"],
                s["currentInstallment"]["paid"]) == (12, "2026-01-15", 9)
        assert s["currentDeposit"]["no"] == 11
        interest = sum(int(c["interest"]) for c in body["contracts"]) + sum(
            int(d["interest"]) for d in body["deposits"])
        assert int(s["interestTotal"]) == interest
        # 보드의 세후 이자 구성(적금 · 예금)은 서버가 나눠 준다 — 화면은 더하지 않는다
        assert int(s["installmentAfterTax"]) == sum(int(c["afterTax"]) for c in body["contracts"])
        assert int(s["depositAfterTax"]) == sum(int(d["afterTax"]) for d in body["deposits"])
        assert int(s["installmentAfterTax"]) + int(s["depositAfterTax"]) == int(s["afterTaxTotal"])

    async def test_행은_최신순이고_종류마다_칸이_있다(self, client, session_factory) -> None:  # type: ignore[no-untyped-def]
        await both(session_factory)
        rows = (await simulate(client)).json()["rows"]
        dates = [r["date"] for r in rows]
        assert dates == sorted(dates, reverse=True)
        kinds = {r["kind"] for r in rows}
        assert kinds == {"installment", "month", "installment_maturity", "deposit_maturity",
                         "deposit_join"}
        for row in rows:
            assert int(row["installmentValue"]) + int(row["depositValue"]) == int(row["balance"])
            if row["kind"] == "installment":
                assert (row["amount"], 1 <= row["installmentNo"] <= 12) == ("1000000", True)
            elif row["kind"] == "month":
                assert "rate" not in row and "amount" not in row
            elif row["kind"] == "deposit_join":
                assert int(row["fromDeposit"]) + int(row["fromInstallment"]) == int(row["amount"])
            else:
                assert int(row["amount"]) > 0 and "interest" in row and "afterTax" in row
        same_day = [r["kind"] for r in rows if r["date"] == "2017-01-15"]
        assert same_day == ["installment", "deposit_join", "deposit_maturity",
                            "installment_maturity"]

    async def test_둘째_가입_달이_결측이면_그날_멈춘다(self, client, session_factory) -> None:  # type: ignore[no-untyped-def]
        await both(session_factory, drop=("2016-01",))
        s = (await simulate(client)).json()["summary"]
        assert s["stopped"] == {"date": "2016-01-15", "reason": "rate_missing", "month": "2016-01"}
        assert (s["isFinal"], s["asOf"], s["balance"]) == (False, "2016-01-15", "12127577")
