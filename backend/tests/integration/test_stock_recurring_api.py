"""주식 적립식 경로 (011 T015) — `GET /api/stocks/recurring-simulation`. FR-002, FR-004, FR-005,
FR-010~FR-014, FR-016, SC-002, contracts/rest-api §1.

이 파일은 **연결**을 본다 — 어느 값이 어디로 가고 요약의 산식이 맞는지다. 계산의 손계산 참조값은
`test_recurring_stock.py`가 고정한다.

- 수집 판정은 일시금과 같은 함수다(같은 202 본문)
- 오류
  - `invalid_query`(주기·금액), `currency_pair_not_allowed`, `before_listing`
  - `fx_not_available_before`(수집 전 — 환율 출처가 늦게 시작), `fx_unavailable`(계산 중 — 그 납입일
    이전 확정 환율 없음, 분석 F1)
- 시작일에 맞춘 예정일이 휴장이면 다음 거래일로 미뤄 합친다(`deferred`). 시드에 없는 날은 휴장이다
- 요약
  - `contributed` = 넣은 횟수 × 납입액
  - `feeTotal` = 매수 수수료 합 + 매도 수수료, `taxTotal` = 배당 소득세 합 + 매도 세금
  - `profitAfterSale` = `profit` − `saleCost.total`, 수익률의 분모는 `contributedKrw`
- 해외 원화 원금이면 납입 행마다 환전 환율(현금 살 때 + 우대)과 평가 환율(매매기준율)이 따로 있다.
  취득가는 매수마다 그 행의 매매기준율이다(010
  반복 4와 같다)
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from httpx2 import AsyncClient
from sqlalchemy import select, update

from src.db.dialect import upsert
from src.db.models import Currency, Stock, StockCoverage, StockPrice
from src.simulation.money import quantize_rate
from tests.integration.stock_recurring_support import (
    AAPL_WEEKLY,
    FX,
    KRX_MONTHLY,
    D,
    aapl_price,
    app_for,
    client_for,
    floor,
    krx_price,
    seed,
)

PATH = "/api/stocks/recurring-simulation"


@pytest.fixture
async def client(session_factory):  # type: ignore[no-untyped-def]
    await seed(session_factory)
    async with client_for(app_for(session_factory)) as http:
        yield http


async def simulate(http: AsyncClient, params: dict[str, str]) -> dict:  # type: ignore[type-arg]
    response = await http.get(PATH, params={**params, "limit": "200"})
    assert response.status_code == 200, response.text
    return response.json()  # type: ignore[no-any-return]


class Test국내_매달:
    async def test_예정일이_휴장이면_다음_거래일로_미뤄_넣는다(self, client: AsyncClient) -> None:
        body = await simulate(client, KRX_MONTHLY)
        rows = body["rows"]
        assert [(r["date"], r["kind"], r.get("deferred")) for r in rows] == [
            ("2026-03-03", "contribution", ["2026-03-02"]),
            ("2026-02-02", "contribution", None),
            ("2026-01-02", "contribution", None),
        ]
        assert [r["contribution"] for r in rows] == ["1000000", "1000000", "1000000"]
        assert [r["contributed"] for r in rows] == ["3000000", "2000000", "1000000"]
        assert body["condition"] == {
            "mode": "recurring", "start": "2026-01-02", "amount": "1000000",
            "principalCurrency": "KRW", "frequency": "monthly", "reinvest": True,
            "tradeFeeRate": "0.000150", "dividendTaxRate": "0.154000",
        }

    async def test_첫_납입은_시가로_사고_잔고는_종가다(self, client: AsyncClient) -> None:
        first = (await simulate(client, KRX_MONTHLY))["rows"][-1]
        open_, close = krx_price("2026-01-02")
        fee = Decimal("1.00015")
        shares = int(Decimal("1000000") / (open_ * fee))
        # 값은 DB 자릿수의 문자열이다("50000.000000") — 값으로 비교한다(사용자 승인 2026-10-06)
        got = (Decimal(first["openPrice"]), Decimal(first["closePrice"]), first["boughtShares"])
        assert got == (open_, close, shares)
        assert Decimal(first["pending"]) == Decimal("1000000") - shares * open_ * fee
        assert Decimal(first["balance"]) == shares * close

    async def test_요약의_산식(self, client: AsyncClient) -> None:
        body = await simulate(client, KRX_MONTHLY)
        summary, latest = body["summary"], body["rows"][0]
        assert (summary["contributions"], summary["contributed"], summary["contributedKrw"],
                summary["pendingAfterEnd"]) == (3, "3000000", "3000000", 0)
        assert (summary["heldShares"], summary["pending"], summary["dividendCash"]) == (
            latest["heldShares"], latest["pending"], latest["dividendCash"])
        sale = Decimal(latest["balance"])
        fee = floor(sale * Decimal("0.000150"))
        tax = floor(sale * Decimal("0.0020"))
        assert summary["saleCost"] == {
            "fee": str(fee), "tax": str(tax), "total": str(fee + tax), "taxKind": "transaction_tax",
            "taxRate": "0.0020", "gain": None, "deduction": None,
        }
        buy_fees = floor(sum((Decimal(r["tradeFee"]) for r in body["rows"] if "tradeFee" in r),
                             Decimal("0")))
        assert summary["buyFeeTotal"] == str(buy_fees)
        assert summary["feeTotal"] == str(buy_fees + fee)
        assert (summary["dividendTaxTotal"], summary["taxTotal"]) == ("0", str(tax))
        parts = ("balance", "pending", "dividendCash")
        total = sum((Decimal(latest[k]) for k in parts), Decimal("0"))
        assert Decimal(summary["totalKrw"]) == total
        assert Decimal(summary["profit"]) == total - Decimal("3000000")
        after = Decimal(summary["profit"]) - (fee + tax)
        assert Decimal(summary["profitAfterSale"]) == after
        assert summary["returnRateAfterSale"] == str(quantize_rate(after / Decimal("3000000")))
        assert (summary["asOf"], summary["isFinal"]) == ("2026-03-03", True)

    async def test_계산_끝_뒤로_미뤄진_납입은_넣지_않고_센다(self, client: AsyncClient) -> None:
        # 03-04(예정일)에 시세가 없고 그 뒤 거래일도 없다 — 매일 납입의 끝은 거래일만이라 생기지
        # 않으므로 매주로 본다
        body = await simulate(client, {**KRX_MONTHLY, "frequency": "weekly", "start": "2026-02-03",
                                       "end": "2026-03-04"})
        # 예정 2-03·2-10·2-17·2-24·3-03 → 실제 2-03, 3-03(2-10·2-17·2-24·3-03)
        summary = body["summary"]
        assert (summary["contributions"], summary["pendingAfterEnd"]) == (5, 0)
        late = await simulate(client, {**KRX_MONTHLY, "frequency": "weekly", "start": "2026-02-04",
                                       "end": "2026-03-04"})
        # 예정 2-04·2-11·2-18·2-25·3-04 → 3-03까지만 시세 — 3-04는 다음 거래일이 없다
        assert (late["summary"]["contributions"], late["summary"]["pendingAfterEnd"]) == (4, 1)

    async def test_쪽을_나눠도_같은_날의_행이_갈리지_않는다(self, client: AsyncClient) -> None:
        first = (await client.get(PATH, params={**KRX_MONTHLY, "limit": "2"})).json()
        assert [r["date"] for r in first["rows"]] == ["2026-03-03", "2026-02-02"]
        assert (first["hasMore"], first["oldestReturned"]) == (True, "2026-02-02")
        second = (await client.get(PATH, params={**KRX_MONTHLY, "limit": "2",
                                                 "before": "2026-02-02"})).json()
        assert [r["date"] for r in second["rows"]] == ["2026-01-02"]
        assert second["hasMore"] is False


class Test해외_원화_매주:
    async def test_납입마다_그날_환전하고_평가_환율이_따로다(self, client: AsyncClient) -> None:
        rows = (await simulate(client, AAPL_WEEKLY))["rows"]
        # 예정 1-02·1-09 … 2-27(매주) → 시세가 있는 날 1-02, 2-02(1-09~1-30), 3-03(2-06~2-27)
        assert [(r["date"], r["contribution"], len(r.get("deferred", []))) for r in rows] == [
            ("2026-03-03", "2000000", 4), ("2026-02-02", "2000000", 4), ("2026-01-02", "500000", 0)]
        for r in rows:
            assert (Decimal(r["fxRate"]), r["fxRateDate"]) == (Decimal(FX[r["date"]]), r["date"])
            assert r["exchangeRateDate"] == r["date"]
            assert Decimal(r["exchangeRate"]) > Decimal(r["fxRate"])
        open_ = aapl_price("2026-01-02")[0]
        last = rows[-1]
        working = (Decimal("500000") / Decimal(last["exchangeRate"])).quantize(Decimal("0.01"))
        assert last["boughtShares"] == int(working / (open_ * Decimal("1.00015")))

    async def test_해외_매도_세금은_원화_차익에서_공제를_뺀_22퍼센트다(
            self, client: AsyncClient) -> None:
        body = await simulate(client, AAPL_WEEKLY)
        summary, rows = body["summary"], body["rows"]
        latest = rows[0]
        fx = Decimal(latest["fxRate"])
        sale_usd = Decimal(latest["balance"])
        sale_krw = floor(sale_usd * fx)
        sell_fee = floor(sale_usd * Decimal("0.000150") * fx)
        acquisition = floor(sum((r["boughtShares"] * Decimal(r["openPrice"]) * Decimal(r["fxRate"])
                                 for r in rows if r["boughtShares"] > 0), Decimal("0")))
        buy_fees = floor(sum((Decimal(r["tradeFee"]) * Decimal(r["fxRate"]) for r in rows
                              if "tradeFee" in r), Decimal("0")))
        gain = sale_krw - acquisition - buy_fees - sell_fee
        tax = floor(max(gain - Decimal("2500000"), Decimal("0")) * Decimal("0.22"))
        assert summary["saleCost"] == {
            "fee": str(sell_fee), "tax": str(tax), "total": str(sell_fee + tax),
            "taxKind": "capital_gains_tax", "taxRate": "0.22", "gain": str(gain),
            "deduction": "2500000",
        }
        assert (summary["contributions"], summary["contributed"], summary["contributedKrw"]) == (
            9, "4500000", "4500000")
        assert summary["buyFeeTotal"] == str(buy_fees)


class Test오류:
    @pytest.mark.parametrize(("over", "status"), [
        ({"frequency": "hourly"}, "invalid_query"),
        ({"amount": "0"}, "invalid_query"),
        ({"amount": "abc"}, "invalid_query"),
        ({"principalCurrency": "USD"}, "currency_pair_not_allowed"),
    ])
    async def test_검증(self, client: AsyncClient, over: dict[str, str], status: str) -> None:
        response = await client.get(PATH, params={**KRX_MONTHLY, **over})
        assert response.status_code == 400
        assert response.json()["status"] == status

    async def test_상장_전_시작일은_400(self, client: AsyncClient) -> None:
        # 일시금과 같은 처리기 — 400 `before_listing`(사용자 승인 2026-10-06 — 처음 409로 잘못 썼다)
        response = await client.get(PATH, params={**KRX_MONTHLY, "start": "1970-01-02"})
        assert (response.status_code, response.json()["status"]) == (400, "before_listing")

    async def test_환율_출처가_늦게_시작하면_수집_전에_409(self, client: AsyncClient,
                                                session_factory) -> None:  # type: ignore[no-untyped-def]
        async with session_factory() as s:
            await s.execute(update(Currency).where(Currency.code == "USD")
                            .values(first_available_date=D("2022-01-03")))
            await s.commit()
        response = await client.get(PATH, params={**AAPL_WEEKLY, "start": "2021-08-02",
                                                  "end": "2021-09-02"})
        assert (response.status_code, response.json()["status"]) == (409, "fx_not_available_before")

    async def test_납입일_이전_확정_환율이_없으면_계산_중에_409(self, client: AsyncClient,
                                                 session_factory) -> None:  # type: ignore[no-untyped-def]
        # 7-30에 시세가 있고 환율 커버리지 안이지만 고시는 8-02부터 — 그 납입을 빼고 계산하지 않는다
        async with session_factory() as s:
            open_, close = aapl_price("2021-08-02")
            aapl = (await s.execute(select(Stock.id).where(Stock.symbol == "AAPL"))).scalar_one()
            await upsert(s, StockPrice, [{"stock_id": aapl, "quote_date": D("2021-07-30"),
                                          "open_raw": open_, "close_raw": close,
                                          "close_adjusted": close, "source": "yahoo:chart"}])
            await s.execute(update(StockCoverage).values(covered_from=D("2021-07-01")))
            await s.commit()
        response = await client.get(PATH, params={**AAPL_WEEKLY, "start": "2021-07-30",
                                                  "end": "2021-09-02"})
        assert (response.status_code, response.json()["status"]) == (409, "fx_unavailable")


async def test_미수집이면_일시금과_같은_202다(session_factory) -> None:  # type: ignore[no-untyped-def]
    await seed(session_factory)
    async with session_factory() as s:
        await s.execute(update(StockCoverage).values(covered_from=D("2026-01-01")))
        await s.commit()
    async with client_for(app_for(session_factory)) as http:
        recurring = await http.get(PATH, params={**KRX_MONTHLY, "start": "2021-08-02"})
        lump = await http.get("/api/stocks/simulation", params={
            "market": "KRX", "symbol": "005930.KS", "start": "2021-08-02", "principal": "1000000",
            "principalCurrency": "KRW", "end": "2026-03-03"})
    assert recurring.status_code == lump.status_code == 202
    assert recurring.json() == lump.json()
