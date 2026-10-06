"""가상자산 시뮬레이션 API (T024) — 007 FR-002, FR-007~FR-009, FR-013, FR-022, FR-024~FR-028,
FR-035, FR-036, FR-037a, SC-003, SC-006, SC-007, contracts/rest-api `GET /api/crypto/simulation`.

**받지 못한 구간이 있으면 계산하지 않는다**(202). 받은 만큼만 계산한 수익률은 값이 멀쩡해 보이지만
틀렸다. 일봉과 환율을 함께 본다 — 시세 통화(USD)가 KRW가 아니라 원금 통화와 관계없이 KRW 평가에
환율이 필요하다(006 FR-068).

행의 금액은 시세 통화(USD)로 남고, 투자 수익·수익률은 **KRW 기준**이다(FR-035). 수량은 소수 8자리
문자열이다(FR-026).
"""
from __future__ import annotations

import dataclasses
import datetime as dt
import json
from decimal import Decimal
from typing import Self

import pytest
from httpx2 import ASGITransport, AsyncClient
from sqlalchemy import func, select

from src.api.main import create_app
from src.db.models import CryptoCollectionJob, CryptoCoverage
from src.db.session import get_session
from src.repository import crypto_daily
from src.worker.crypto_queue import get_crypto_queue
from tests.integration.crypto_support import (
    LEASH_ID,
    SHIB_ID,
    add_coin,
    fixture,
    seed_daily,
    seed_usd,
    usd_rate,
)

D = dt.date.fromisoformat
P = Decimal


@pytest.fixture
async def client(session_factory):  # type: ignore[no-untyped-def]
    app = create_app()

    async def _session():  # type: ignore[no-untyped-def]
        async with session_factory() as s:
            yield s

    app.dependency_overrides[get_session] = _session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def btc(session_factory) -> int:  # type: ignore[no-untyped-def]
    """수집을 마친 BTC — 2020-01-01 ~ 2021-12-31 일봉과 커버리지, 넉넉한 USD 환율."""
    coin_id = await add_coin(session_factory)
    await seed_daily(session_factory, coin_id, "btc_2020_2021.json",
                     covered=(D("2020-01-01"), D("2021-12-31")))
    await seed_usd(session_factory, D("2019-12-01"), D("2022-12-31"))
    return coin_id


def params(coin_id: int, **over: str) -> dict[str, str]:
    base = {"coinId": str(coin_id), "start": "2020-01-15", "principal": "10000",
            "principalCurrency": "USD", "end": "2021-12-31", "limit": "50"}
    base.update(over)
    return base


async def simulate(client: AsyncClient, coin_id: int, status: int = 200, **over: str) -> dict:
    response = await client.get("/api/crypto/simulation", params=params(coin_id, **over))
    assert response.status_code == status, response.text
    return response.json()


class Test수집_게이트:
    async def test_받지_않은_구간이면_202이고_결과가_없다(self, session_factory, client) -> None:
        coin_id = await add_coin(session_factory)
        await seed_usd(session_factory, D("2019-12-01"), D("2022-12-31"))
        body = await simulate(client, coin_id, 202)
        assert body["status"] == "collecting" and body["coinId"] == coin_id
        # 시작 월 1일부터 받는다 — 시작 월의 첫 일봉이 매수일이다(FR-025)
        assert (body["missingFrom"], body["missingThrough"]) == ("2020-01-01", "2021-12-31")
        assert body["progressUrl"] == f"/api/crypto/progress?jobId={body['jobId']}"
        assert "rows" not in body and "summary" not in body and "fx" not in body
        assert get_crypto_queue().is_active(coin_id)

    async def test_같은_조건을_다시_요청하면_같은_작업이다(self, session_factory, client) -> None:
        coin_id = await add_coin(session_factory)
        await seed_usd(session_factory, D("2019-12-01"), D("2022-12-31"))
        first = await simulate(client, coin_id, 202)
        second = await simulate(client, coin_id, 202)
        assert first["jobId"] == second["jobId"]

    async def test_환율이_비면_202_fx다(self, session_factory, client) -> None:
        coin_id = await add_coin(session_factory)
        await seed_daily(session_factory, coin_id, "btc_2020_2021.json",
                         covered=(D("2020-01-01"), D("2021-12-31")))
        body = await simulate(client, coin_id, 202)
        assert body["fx"]["currency"] == "USD"
        assert "jobId" not in body

    async def test_달러_원금이어도_환율을_본다(self, session_factory, client) -> None:
        """006 FR-068 — 투자 수익은 원금 통화와 관계없이 KRW다."""
        coin_id = await add_coin(session_factory)
        await seed_daily(session_factory, coin_id, "btc_2020_2021.json",
                         covered=(D("2020-01-01"), D("2021-12-31")))
        body = await simulate(client, coin_id, 202, principalCurrency="USD")
        assert "fx" in body


class Test결과:
    async def test_매수_행(self, client, btc) -> None:
        """research R7-7의 손계산 사례 — 2020-01-01 시가 7,196.39111328125, 원금 10,000달러, 수수료
        0.1%."""
        # 012 승인 2026-10-06 — 매수 행은 `buy`다. 기본 단위가 일이라 첫 쪽에 없어 월 단위로 받는다.
        body = await simulate(client, btc, period="monthly")
        [bought] = [r for r in body["rows"] if r["kind"] == "buy"]
        assert bought["date"] == "2020-01-01" and bought["kind"] == "buy"
        assert bought["openPrice"] == "7196.39111328125000"
        assert bought["boughtQuantity"] == "1.38819719"
        assert bought["heldQuantity"] == "1.38819719"
        assert bought["tradeFee"] == "9.9900099215980029296875"
        assert bought["cash"] == "0.0000684803990673828125"
        assert "firstDayMissing" not in bought

    async def test_매수가_없는_행에는_수수료가_없다(self, client, btc) -> None:
        # 012 승인 2026-10-06 — 월 행은 그 달 말일 기준(기간 행)이다. 24개월의 기간 행 + 매수 행.
        body = await simulate(client, btc, period="monthly")
        latest = body["rows"][0]
        assert latest["date"] == "2021-12-31" and latest["kind"] == "period"
        assert latest["boughtQuantity"] == "0.00000000"
        assert latest["heldQuantity"] == "1.38819719"
        assert "tradeFee" not in latest
        assert len(body["rows"]) == 25
        assert {r["kind"] for r in body["rows"]} == {"period", "buy"}

    async def test_열별_통화(self, client, btc) -> None:
        """잔고·예수금·수수료는 시세 통화, 잔고 KRW는 그 행의 매매기준율, 투자 수익·수익률은 KRW
        기준."""
        body = await simulate(client, btc)
        principal_krw = P(body["summary"]["principalKrw"])
        assert principal_krw == P("10000") * P(usd_rate(D("2020-01-01")))
        for row in body["rows"]:
            day = D(row["date"])
            rate = P(row["fxRate"])
            assert (row["fxRate"], row["fxRateDate"]) == (usd_rate(day), row["date"])
            balance = P(row["balance"])
            assert balance == P(row["heldQuantity"]) * P(row["openPrice"])
            assert P(row["balanceKrw"]) == (balance * rate).quantize(P("1"))
            expected = ((balance + P(row["cash"])) * rate).quantize(P("1")) - principal_krw
            assert P(row["profit"]) == expected
            assert P(row["returnRate"]) == (expected / principal_krw).quantize(P("0.000001"))
            assert row["principal"] == "10000"

    async def test_요약과_조건과_코인(self, client, btc) -> None:
        body = await simulate(client, btc)
        summary = body["summary"]
        assert (summary["principal"], summary["boughtOn"], summary["asOf"], summary["isFinal"]) == (
            "10000", "2020-01-01", "2021-12-31", True)
        # 첫 매수일의 매매기준율로 평가한 원금(KRW 자릿수)
        assert summary["principalKrw"] == str(
            (P("10000") * P(usd_rate(D("2020-01-01")))).quantize(P("1")))
        assert body["condition"] == {"start": "2020-01-15", "principal": "10000",
                                     "principalCurrency": "USD", "tradeFeeRate": "0.001000"}
        assert body["coin"] == {"coinId": btc, "symbol": "BTC", "name": "Bitcoin",
                                "nameKo": "비트코인", "currency": "USD"}
        # 달러 원금이면 환전이 없다(006 FR-052와 같다)
        assert "exchange" not in body

    async def test_요약은_마지막_일봉의_평가다(self, client, btc) -> None:
        # 012 승인 2026-10-06 — 일 단위 표의 맨 위 행이 마지막 일봉(기준일)이라 요약과 같다. 월 단위
        # 맨 위 행도 그 달의 마지막 일봉이다.
        body = await simulate(client, btc)
        assert body["rows"][0]["date"] == body["summary"]["asOf"]
        assert body["summary"]["profit"] == body["rows"][0]["profit"]

    async def test_스크롤로_이어_본다(self, client, btc) -> None:
        # 012 승인 2026-10-06 — 월 단위는 그 달 말일 기준이다.
        first = await simulate(client, btc, limit="5", period="monthly")
        assert (len(first["rows"]), first["hasMore"], first["oldestReturned"]) == (
            5, True, "2021-08-31")
        rest = await simulate(client, btc, limit="50", before=first["oldestReturned"],
                              period="monthly")
        assert rest["rows"][0]["date"] == "2021-07-31" and rest["hasMore"] is False

    async def test_1일이_결측이면_일_단위에_결측_구간_행이다(self, session_factory, client) -> None:
        # 012 승인 2026-10-06 — ◇(firstDayMissing) 대신 일 단위의 결측 구간 행이다(FR-004b·FR-008).
        coin_id = await add_coin(session_factory)
        await seed_daily(session_factory, coin_id, "btc_2020_2021.json",
                         covered=(D("2020-01-01"), D("2021-12-31")), drop=[D("2021-03-01")])
        await seed_usd(session_factory, D("2019-12-01"), D("2022-12-31"))
        body = await simulate(client, coin_id, before="2021-03-03", limit="3")
        assert [(r["date"], r["kind"], r.get("dateTo")) for r in body["rows"]] == [
            ("2021-03-02", "period", None), ("2021-03-01", "missing", "2021-03-01"),
            ("2021-02-28", "period", None)]
        monthly = await simulate(client, coin_id, period="monthly")
        assert all("firstDayMissing" not in r for r in monthly["rows"] + body["rows"])

    async def test_일봉이_끊기면_마지막_일봉까지이고_최종이_아니다(
        self, session_factory, client
    ) -> None:
        """FR-024 — 2022-03-31까지 받았지만 일봉은 2021-12-31에 끝난다."""
        coin_id = await add_coin(session_factory)
        await seed_daily(session_factory, coin_id, "btc_2020_2021.json",
                         covered=(D("2020-01-01"), D("2022-03-31")))
        await seed_usd(session_factory, D("2019-12-01"), D("2022-12-31"))
        body = await simulate(client, coin_id, end="2022-03-31")
        assert (body["summary"]["asOf"], body["summary"]["isFinal"]) == ("2021-12-31", False)

    async def test_아주_작은_가격을_원값_그대로_싣는다(self, session_factory, client) -> None:
        """FR-040 — 표시 자릿수는 화면이 정한다. 서버는 출처 원값(14자리)을 그대로 준다."""
        coin_id = await add_coin(session_factory, SHIB_ID, "SHIB", "Shiba Inu", name_ko=None)
        await seed_daily(session_factory, coin_id, "shib_recent.json",
                         covered=(D("2026-09-01"), D("2026-10-02")))
        await seed_usd(session_factory, D("2026-08-01"), D("2026-10-02"))
        body = await simulate(client, coin_id, start="2026-09-13", end="2026-10-02")
        # 012 승인 2026-10-06 — 맨 아래 행은 시작 월 1일부터의 결측 구간 행이다(FR-004b). 매수 행은
        # `buy`로 찾는다.
        [bought] = [r for r in body["rows"] if r["kind"] == "buy"]
        assert bought["date"] == "2026-09-13"
        assert bought["openPrice"] == "0.00000529999988"
        assert P(bought["boughtQuantity"]) > P("1000000000")


class Test오류:
    async def test_첫_일봉보다_이르면_수집_전에_막는다(self, session_factory, client) -> None:
        """FR-008 — 기록된 시작 가능 날짜보다 이르면 수집하지 않고 그 날짜를 알린다."""
        coin_id = await add_coin(session_factory, first_available=D("2010-07-18"))
        body = await simulate(client, coin_id, 400, start="2009-01-01")
        assert (body["status"], body["startableFrom"], body["basis"]) == (
            "before_listing", "2010-07-18", "price_start")
        async with session_factory() as s:
            assert (await s.execute(
                select(func.count()).select_from(CryptoCollectionJob))).scalar() == 0

    async def test_수집_뒤_시작_월에_일봉이_없으면_막는다(self, session_factory, client) -> None:
        coin_id = await add_coin(session_factory)
        await seed_daily(session_factory, coin_id, "btc_2011_06.json",
                         covered=(D("2009-01-01"), D("2011-07-31")))
        await seed_usd(session_factory, D("2008-12-01"), D("2011-07-31"))
        body = await simulate(client, coin_id, 400, start="2009-01-15", end="2011-07-31")
        assert (body["status"], body["startableFrom"]) == ("before_listing", "2011-06-01")

    async def test_시작일이_계산_끝보다_늦으면_400이다(self, client, btc) -> None:
        body = await simulate(client, btc, 400, start="2022-01-05", end="2021-12-31")
        assert (body["status"], body["lastDay"]) == ("start_after_end", "2021-12-31")

    async def test_계산_끝의_기본은_UTC_어제다(self, client, btc) -> None:
        """FR-022 — 마지막으로 마감된 UTC 하루. 한국 시간 어제로 두면 한국 오전 9시 전에 마감 전
        일봉을 요구한다."""
        yesterday = dt.datetime.now(dt.UTC).date() - dt.timedelta(days=1)
        response = await client.get("/api/crypto/simulation", params={
            "coinId": str(btc), "start": "2100-01-01", "principal": "10000",
            "principalCurrency": "USD"})
        assert response.status_code == 400
        assert response.json()["lastDay"] == yesterday.isoformat()

    async def test_모르는_코인은_다시_고르라고_한다(self, client) -> None:
        body = await simulate(client, 99999999, 404)
        assert (body["status"], body["action"]) == ("unknown_coin", "reselect")

    async def test_일봉이_없는_코인은_시세_없음이다(self, session_factory, client) -> None:
        coin_id = await add_coin(session_factory, LEASH_ID, "LEASH", "Doge Killer", name_ko=None)
        async with session_factory() as s:
            await crypto_daily.record_coverage(s, coin_id, D("2026-09-01"), D("2026-10-02"))
            await s.commit()
        await seed_usd(session_factory, D("2026-08-01"), D("2026-10-02"))
        body = await simulate(client, coin_id, 404, start="2026-09-13", end="2026-10-02")
        assert body["status"] == "no_price_data"

    @pytest.mark.parametrize("currency", ["EUR", "JPY", "BTC"])
    async def test_원화도_시세_통화도_아니면_막는다(self, client, btc, currency: str) -> None:
        body = await simulate(client, btc, 400, principalCurrency=currency)
        assert (body["status"], body["allowed"]) == ("currency_pair_not_allowed", ["KRW", "USD"])

    @pytest.mark.parametrize("principal", ["0", "-5", "abc"])
    async def test_원금이_0_이하거나_숫자가_아니면_400이다(
        self, client, btc, principal: str
    ) -> None:
        body = await simulate(client, btc, 400, principal=principal)
        assert body["status"] == "invalid_query"


class _Resp:
    def __init__(self, body: str) -> None:
        self._body = body
        self.status = 200

    async def text(self) -> str:
        return self._body

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *exc: object) -> None:
        return None


class _HistorySession:
    """출처 흉내 — 일봉 API만 답한다. 요청 구간의 행만 실은 실제 응답 모양이다."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def get(self, url: str, *, params: dict[str, str] | None = None, **_: object) -> _Resp:
        params = dict(params or {})
        assert "/historical/" in url, url
        self.calls.append((params["start-date"], params["end-date"]))
        start, end = D(params["start-date"]), D(params["end-date"])
        doc = json.loads(fixture("btc_2020_2021.json"))
        doc["data"] = [r for r in doc["data"]
                       if start <= D(r["rowDateTimestamp"][:10]) <= end] or None
        return _Resp(json.dumps(doc))

    async def close(self) -> None:
        return None


class Test실행_주체:
    """202를 받은 요청이 `lifespan`의 가상자산 수집 줄로 이어져 작업이 끝나고, 다시 요청하면
    200이다(006 D1의 교훈)."""

    async def test_수집_줄이_작업을_끝내고_다시_요청하면_200이다(
        self, session_factory, monkeypatch
    ) -> None:
        from fastapi.testclient import TestClient

        from src.api.routes import crypto_progress
        from src.ingestion.investing import client as investing_client

        coin_id = await add_coin(session_factory)
        await seed_usd(session_factory, D("2019-12-01"), D("2022-12-31"))
        real = investing_client.InvestingClient
        fake = _HistorySession()

        async def no_sleep(_: float) -> None:
            return None

        def make(settings, **_: object):  # type: ignore[no-untyped-def]
            fast = dataclasses.replace(settings, investing_min_interval_ms=0)
            return real(fast, session=fake, sleep=no_sleep)  # type: ignore[arg-type]

        monkeypatch.setattr(investing_client, "InvestingClient", make)
        monkeypatch.setattr(crypto_progress, "POLL_SECONDS", 0.02)

        with TestClient(create_app()) as tc:
            first = tc.get("/api/crypto/simulation", params=params(coin_id))
            assert first.status_code == 202, first.text
            with tc.stream("GET", first.json()["progressUrl"]) as response:
                text = "".join(response.iter_text())
            assert "event: completed" in text, text
            # 012 승인 2026-10-06 — 매수 행은 월 단위로 받아 `buy`로 찾는다(기본 단위가 일이라 첫
            # 쪽에 없다).
            second = tc.get("/api/crypto/simulation", params=params(coin_id, period="monthly"))

        assert second.status_code == 200, second.text
        [bought] = [r for r in second.json()["rows"] if r["kind"] == "buy"]
        assert bought["boughtQuantity"] == "1.38819719"
        assert fake.calls == [("2020-01-01", "2021-12-30"), ("2021-12-31", "2021-12-31")]
        async with session_factory() as s:
            coverage = await s.get(CryptoCoverage, coin_id)
        assert coverage is not None and coverage.covered_from == D("2020-01-01")
