"""가상자산 적립식 경로 (011 T034) — FR-002, FR-017~FR-021, SC-002, contracts/rest-api §2.

- 수집 판정은 일시금과 같은 함수다(같은 202 본문)
- 오류
  - `invalid_query`(주기·금액), `currency_pair_not_allowed`, `before_listing`(400),
    `unknown_coin`(404)
  - `fx_not_available_before`(수집 전 — 환율 출처가 늦게 시작)
  - `fx_unavailable`(계산 중 — 그 납입일 이전 확정 환율 없음, 분석 F1)
- 원화 원금이면 납입마다 그날 환전한다(현금 살 때 + 90% 우대). 평가는 그 행의 매매기준율이다
- 출처 결측일의 납입은 다음 일봉으로 미뤄 합친다(`deferred`)
- 요약
  - `contributed` = 넣은 횟수 × 납입액, 수익률의 분모는 `contributedKrw`
  - 매도 비용은 기준일 평가액 × 수수료율(원 미만 버림)이고, 2027-01-01 전 기준일의 세금은 0이다
  - 기준일이 2027-01-01 이후면 세금·매도 뒤 수익을 **비운다**(0으로 메우지 않는다 — FR-020)
- 계산 끝은 일시금 라우트의 `calculation_end`(min(`end`, UTC 어제))다. 2027년 기준일은 그 모듈의
  시계를 바꿔 만든다(분석 C1)
"""

from __future__ import annotations

import datetime as dt
import re
from decimal import ROUND_FLOOR, Decimal

import pytest
from httpx2 import ASGITransport, AsyncClient
from sqlalchemy import delete

from src.api.main import create_app
from src.db.dialect import upsert
from src.db.models import Currency, FxRate
from src.db.session import get_session
from src.ingestion.investing.parse import DailyBar
from src.repository import crypto_daily
from src.repository.spread import spread_set
from src.simulation.fx_convert import exchange_rate, to_foreign
from src.simulation.money import buy_fraction, quantize_rate
from tests.integration.crypto_support import ETH_ID, add_coin, seed_daily, seed_usd, usd_rate

D = dt.date.fromisoformat
P = Decimal
PATH = "/api/crypto/recurring-simulation"
EIGHT = re.compile(r"^\d+\.\d{8}$")

PARAMS = {"start": "2021-01-01", "amount": "10000", "principalCurrency": "KRW",
          "frequency": "daily", "end": "2021-01-31", "limit": "50"}


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


async def run(client: AsyncClient, coin_id: int, status: int = 200, **over: str) -> dict:
    response = await client.get(PATH, params={"coinId": str(coin_id), **PARAMS, **over})
    assert response.status_code == status, response.text
    return response.json()  # type: ignore[no-any-return]


async def cash_buy(session_factory) -> Decimal:  # type: ignore[no-untyped-def]
    async with session_factory() as s:
        return (await spread_set(s, "USD")).cash_buy


def floor_won(value: Decimal) -> Decimal:
    return value.quantize(P("1"), rounding=ROUND_FLOOR)


class Test수집_판정:
    async def test_받지_않은_구간이면_일시금과_같은_202다(self, session_factory, client) -> None:
        coin_id = await add_coin(session_factory)
        await seed_usd(session_factory, D("2019-12-01"), D("2022-12-31"))
        recurring = await run(client, coin_id, 202)
        response = await client.get("/api/crypto/simulation", params={
            "coinId": str(coin_id), "start": "2021-01-01", "principal": "10000",
            "principalCurrency": "KRW", "end": "2021-01-31"})
        assert response.status_code == 202
        assert recurring == response.json()
        assert recurring["status"] == "collecting"

    async def test_환율이_비면_202_fx다(self, session_factory, client) -> None:
        coin_id = await add_coin(session_factory)
        await seed_daily(session_factory, coin_id, "btc_2020_2021.json",
                         covered=(D("2020-01-01"), D("2021-12-31")))
        body = await run(client, coin_id, 202)
        assert body["fx"]["currency"] == "USD"


class Test오류:
    async def test_주기가_밖이면_기본값으로_바꾸지_않고_400이다(self, client, btc) -> None:
        body = await run(client, btc, 400, frequency="hourly")
        assert body["status"] == "invalid_query"
        assert "daily · weekly · monthly · yearly" in body["message"]

    @pytest.mark.parametrize("amount", ["0", "-5", "abc"])
    async def test_납입액이_0_이하거나_숫자가_아니면_400이다(
        self, client, btc, amount: str
    ) -> None:
        body = await run(client, btc, 400, amount=amount)
        assert body["status"] == "invalid_query"

    @pytest.mark.parametrize("currency", ["EUR", "BTC"])
    async def test_원화도_시세_통화도_아니면_막는다(self, client, btc, currency: str) -> None:
        body = await run(client, btc, 400, principalCurrency=currency)
        assert (body["status"], body["allowed"]) == ("currency_pair_not_allowed", ["KRW", "USD"])

    async def test_모르는_코인은_404다(self, client) -> None:
        body = await run(client, 99999999, 404)
        assert body["status"] == "unknown_coin"

    async def test_첫_일봉보다_이르면_수집_전에_400이다(self, session_factory, client) -> None:
        coin_id = await add_coin(session_factory, first_available=D("2010-07-18"))
        body = await run(client, coin_id, 400, start="2009-01-01", end="2009-02-01")
        assert (body["status"], body["startableFrom"]) == ("before_listing", "2010-07-18")

    async def test_환율_출처가_늦게_시작하면_수집_전에_409다(self, session_factory, client) -> None:
        coin_id = await add_coin(session_factory)
        await seed_daily(session_factory, coin_id, "btc_2020_2021.json",
                         covered=(D("2020-01-01"), D("2021-12-31")))
        async with session_factory() as s:
            await upsert(s, Currency, [{"code": "USD", "display_name": "미국 달러", "quote_unit": 1,
                                        "source_item_code": "0000001",
                                        "first_available_date": D("2020-06-01")}], preserve=())
            await s.commit()
        await seed_usd(session_factory, D("2020-06-01"), D("2022-12-31"))
        body = await run(client, coin_id, 409, start="2020-01-15", end="2020-02-15")
        assert body["status"] == "fx_not_available_before"

    async def test_납입일_이전_확정_환율이_없으면_계산_중에_409다(
        self, session_factory, client, btc
    ) -> None:
        # 커버리지는 그대로 두고 고시만 지운다 — 첫 납입(2021-01-01)에 쓸 환율이 없다.
        # 그 납입을 빼고 계산하면 총 납입 원금이 조용히 준다(FR-005)
        async with session_factory() as s:
            await s.execute(delete(FxRate).where(FxRate.currency_code == "USD",
                                                 FxRate.quote_date <= D("2021-01-01")))
            await s.commit()
        body = await run(client, btc, 409)
        assert body["status"] == "fx_unavailable"


class Test매일_원화:
    async def test_조건과_코인(self, client, btc) -> None:
        body = await run(client, btc)
        assert body["condition"] == {
            "mode": "recurring", "start": "2021-01-01", "amount": "10000",
            "principalCurrency": "KRW", "frequency": "daily", "tradeFeeRate": "0.001000"}
        assert body["coin"]["coinId"] == btc and body["coin"]["currency"] == "USD"

    async def test_행은_납입마다이고_최신순이다(self, client, btc) -> None:
        rows = (await run(client, btc))["rows"]
        assert [r["date"] for r in rows] == [
            (D("2021-01-31") - dt.timedelta(days=i)).isoformat() for i in range(31)]
        assert {r["kind"] for r in rows} == {"contribution"}
        assert all(r["contribution"] == "10000" and "deferred" not in r for r in rows)

    async def test_첫_납입은_그날_환전한_달러로_소수_8자리까지_산다(
        self, session_factory, client, btc
    ) -> None:
        rows = (await run(client, btc))["rows"]
        first = rows[-1]
        base = P(usd_rate(D("2021-01-01")))
        rate = exchange_rate(base, await cash_buy(session_factory))
        assert (P(first["exchangeRate"]), first["exchangeRateDate"]) == (rate, "2021-01-01")
        # 평가는 매매기준율이다 — 환전 환율과 따로다
        assert (first["fxRate"], first["fxRateDate"]) == (usd_rate(D("2021-01-01")), "2021-01-01")
        working = to_foreign(P("10000"), rate, "USD")
        bought = buy_fraction(working, P(first["openPrice"]), P("0.001"))
        assert first["boughtQuantity"] == format(bought, ".8f")
        assert first["heldQuantity"] == format(bought, ".8f")

    async def test_납입마다_그날_환율로_환전한다(self, session_factory, client, btc) -> None:
        spread = await cash_buy(session_factory)
        for row in (await run(client, btc))["rows"]:
            base = P(usd_rate(D(row["date"])))
            assert (P(row["exchangeRate"]), row["exchangeRateDate"]) == (
                exchange_rate(base, spread), row["date"])

    async def test_수량은_소수_8자리_문자열이다(self, client, btc) -> None:
        for row in (await run(client, btc))["rows"]:
            assert EIGHT.match(row["boughtQuantity"]), row["boughtQuantity"]
            assert EIGHT.match(row["heldQuantity"]), row["heldQuantity"]

    async def test_원화_분모는_납입마다_더하고_수익은_그_행의_환율로_평가한다(
        self, client, btc
    ) -> None:
        rows = list(reversed((await run(client, btc))["rows"]))
        for count, row in enumerate(rows, start=1):
            assert (P(row["contributed"]), P(row["contributedKrw"])) == (
                P(10000 * count), P(10000 * count))
            rate = P(row["fxRate"])
            assert P(row["balance"]) == P(row["heldQuantity"]) * P(row["openPrice"])
            assert P(row["balanceKrw"]) == (P(row["balance"]) * rate).quantize(P("1"))
            total = ((P(row["balance"]) + P(row["pending"])) * rate).quantize(P("1"))
            assert P(row["profit"]) == total - P(row["contributedKrw"])
            basis = P(row["contributedKrw"])
            assert P(row["returnRate"]) == quantize_rate(P(row["profit"]) / basis)

    async def test_요약(self, client, btc) -> None:
        body = await run(client, btc)
        summary, latest = body["summary"], body["rows"][0]
        assert (P(summary["contributed"]), P(summary["contributedKrw"]), summary["contributions"],
                summary["pendingAfterEnd"]) == (P("310000"), P("310000"), 31, 0)
        assert (summary["heldQuantity"], P(summary["pending"])) == (
            latest["heldQuantity"], P(latest["pending"]))
        assert (summary["asOf"], summary["isFinal"]) == ("2021-01-31", True)
        assert P(summary["profit"]) == P(latest["profit"])
        assert P(summary["totalKrw"]) == P(latest["profit"]) + P("310000")
        # 매수 수수료 합은 행마다 그 행의 매매기준율로 원화로 바꿔 더한 뒤 원 미만을 버린다
        buy_fees = floor_won(sum((P(r["tradeFee"]) * P(r["fxRate"]) for r in body["rows"]), P(0)))
        assert P(summary["buyFeeTotal"]) == buy_fees

    async def test_매도_비용은_시행_전이라_세금이_0이다(self, client, btc) -> None:
        body = await run(client, btc)
        summary, latest = body["summary"], body["rows"][0]
        sale = summary["saleCost"]
        fee = floor_won(P(latest["balanceKrw"]) * P("0.001"))
        assert sale == {"fee": str(fee), "tax": "0", "total": str(fee), "taxKind": "not_yet_taxed"}
        assert P(summary["feeTotal"]) == P(summary["buyFeeTotal"]) + fee
        assert summary["taxTotal"] == "0"
        after = P(summary["profit"]) - fee
        assert P(summary["profitAfterSale"]) == after
        assert P(summary["returnRateAfterSale"]) == quantize_rate(after / P("310000"))


class Test결측일:
    async def test_결측일의_납입은_다음_일봉으로_미뤄_합친다(self, session_factory, client) -> None:
        coin_id = await add_coin(session_factory)
        await seed_daily(session_factory, coin_id, "btc_2020_2021.json",
                         covered=(D("2020-01-01"), D("2021-12-31")),
                         drop=[D("2021-01-10"), D("2021-01-11")])
        await seed_usd(session_factory, D("2019-12-01"), D("2022-12-31"))
        body = await run(client, coin_id)
        # 012 승인 2026-10-06 — 결측일에는 값 행이 없고, 일 단위에는 그 자리에 결측 구간 행 하나가
        # 있다(FR-004b).
        values = [r["date"] for r in body["rows"] if r["kind"] != "missing"]
        assert "2021-01-10" not in values and "2021-01-11" not in values
        gaps = [(r["date"], r["dateTo"]) for r in body["rows"] if r["kind"] == "missing"]
        assert gaps == [("2021-01-10", "2021-01-11")]
        row = next(r for r in body["rows"] if r["date"] == "2021-01-12")
        assert (row["contribution"], row["deferred"]) == ("30000", ["2021-01-10", "2021-01-11"])
        # 미뤄 합쳐도 넣은 예정일 수는 그대로다(SC-002)
        assert body["summary"]["contributions"] == 31
        assert P(body["summary"]["contributed"]) == P("310000")


class Test쪽:
    async def test_스크롤로_이어_본다(self, client, btc) -> None:
        first = await run(client, btc, limit="10")
        assert (len(first["rows"]), first["hasMore"], first["oldestReturned"]) == (
            10, True, "2021-01-22")
        rest = await run(client, btc, before=first["oldestReturned"])
        assert rest["rows"][0]["date"] == "2021-01-21" and rest["hasMore"] is False
        assert rest["oldestReturned"] == "2021-01-01"


class Test과세_시행_뒤:
    async def test_기준일이_2027년이면_세금과_매도_뒤_수익을_비운다(
        self, session_factory, client, monkeypatch
    ) -> None:
        """계산 끝은 min(`end`, UTC 어제)라 시드의 끝만 늦춰서는 2027년 기준일을 만들 수 없다 —
        일시금 라우트 모듈의 시계를 바꾼다(분석 C1)."""
        monkeypatch.setattr("src.api.routes.crypto_simulation.utc_yesterday",
                            lambda: D("2027-01-05"))
        coin_id = await add_coin(session_factory, ETH_ID, "ETH", "Ethereum", name_ko="이더리움")
        days = [D("2026-12-01") + dt.timedelta(days=i) for i in range(35)]
        async with session_factory() as s:
            await crypto_daily.store_bars(s, coin_id, [
                DailyBar(day=d, open=P("3000") + i, high=P("3100") + i, low=P("2900") + i,
                         close=P("3000") + i, volume=None) for i, d in enumerate(days)])
            await crypto_daily.record_coverage(s, coin_id, days[0], days[-1])
            await s.commit()
        await seed_usd(session_factory, D("2026-11-01"), D("2027-01-04"))
        body = await run(client, coin_id, start="2026-12-01", end="2027-01-04",
                         frequency="weekly")
        summary = body["summary"]
        assert summary["asOf"] == "2027-01-04"
        sale = summary["saleCost"]
        assert (sale["tax"], sale["total"], sale["taxKind"]) == (None, None, "outside_rules")
        assert P(sale["fee"]) > 0
        assert (summary["taxTotal"], summary["profitAfterSale"],
                summary["returnRateAfterSale"]) == (None, None, None)
        # 보유 중 값은 그대로 있다
        assert summary["profit"] is not None and summary["returnRate"] is not None
