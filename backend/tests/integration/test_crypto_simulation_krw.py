"""원화 원금 (T035) — 007 FR-034~FR-036, SC-007, research R7-8, analyze C1.

원화 원금이면 **첫 매수일에 환전**한다 — 현금 살 때 환율에 스프레드 90% 우대(006과 같은 함수).
환전은 실제로 사는 날에 한다 — 시작일이 아니다. 평가는 **그 행의 매매기준율**이고, 투자 수익 = (잔고
+ 예수금) × 그 행의 환율 − 원금(KRW)이다. 평가·환전에는 **확정 환율만** 쓴다 — 잠정 환율만 있는 날은
앞 확정일의 값과 그 날짜다(헌법 원칙 V, analyze C1).
"""
from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest
from httpx2 import ASGITransport, AsyncClient
from sqlalchemy import delete

from src.api.main import create_app
from src.db.dialect import upsert
from src.db.models import Currency, FxRate
from src.db.session import get_session
from src.repository.spread import spread_set
from src.simulation.fx_convert import exchange_rate, to_foreign
from src.simulation.money import buy_fraction
from tests.integration.crypto_support import add_coin, seed_daily, seed_usd, usd_rate

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
    coin_id = await add_coin(session_factory)
    await seed_daily(session_factory, coin_id, "btc_2020_2021.json",
                     covered=(D("2020-01-01"), D("2021-12-31")))
    return coin_id


PARAMS = {"start": "2020-01-15", "principal": "10000000", "principalCurrency": "KRW",
          "end": "2021-12-31", "limit": "50"}


async def simulate(client: AsyncClient, coin_id: int, status: int = 200, **over: str) -> dict:
    response = await client.get("/api/crypto/simulation",
                                params={"coinId": str(coin_id), **PARAMS, **over})
    assert response.status_code == status, response.text
    return response.json()


async def cash_buy(session_factory) -> Decimal:  # type: ignore[no-untyped-def]
    async with session_factory() as s:
        return (await spread_set(s, "USD")).cash_buy


class Test환전:
    async def test_첫_매수일에_현금_살_때_환율과_우대로_바꾼다(
        self, session_factory, client, btc
    ) -> None:
        await seed_usd(session_factory, D("2019-12-01"), D("2022-12-31"))
        # 012 승인 2026-10-06 — 매수 행은 월 단위로 받아 `buy`로 찾는다(기본 단위가 일이라 첫 쪽에
        # 없다).
        body = await simulate(client, btc, period="monthly")
        base = P(usd_rate(D("2020-01-01")))
        rate = exchange_rate(base, await cash_buy(session_factory))
        assert body["exchange"] == {"rate": str(rate), "rateDate": "2020-01-01",
                                    "kind": "cash_buy_discounted", "spreadDiscount": "0.9"}
        # 현금을 **사는** 것이므로 매매기준율보다 크다
        assert rate > base
        # 환전한 달러로 산다
        working = to_foreign(P("10000000"), rate, "USD")
        expected = buy_fraction(working, P("7196.39111328125"), P("0.001"))
        [bought] = [r for r in body["rows"] if r["kind"] == "buy"]
        assert bought["boughtQuantity"] == format(expected, ".8f")

    async def test_첫_매수일에_고시가_없으면_이전_고시일과_그_날짜다(
        self, session_factory, client, btc
    ) -> None:
        await seed_usd(session_factory, D("2019-12-01"), D("2022-12-31"))
        async with session_factory() as s:
            # 2019-12-31·2020-01-01에 고시가 없다(연말·신정) — 커버리지는 그대로 둔다
            await s.execute(delete(FxRate).where(
                FxRate.currency_code == "USD",
                FxRate.quote_date.in_([D("2019-12-31"), D("2020-01-01")])))
            await s.commit()
        body = await simulate(client, btc)
        assert body["exchange"]["rateDate"] == "2019-12-30"

    async def test_투자_수익은_그_행의_환율로_평가한_KRW_원금_대비다(
        self, session_factory, client, btc
    ) -> None:
        await seed_usd(session_factory, D("2019-12-01"), D("2022-12-31"))
        body = await simulate(client, btc)
        assert "principalKrw" not in body["summary"]
        rates = {r["fxRate"] for r in body["rows"]}
        assert len(rates) > 1, "초기 환율 하나로 전 구간을 평가하면 환율 변동이 사라진다"
        for row in body["rows"]:
            assert (row["fxRate"], row["fxRateDate"]) == (usd_rate(D(row["date"])), row["date"])
            total = (P(row["balance"]) + P(row["cash"])) * P(row["fxRate"])
            assert P(row["profit"]) == total.quantize(P("1")) - P("10000000")
            assert row["principal"] == "10000000"


class Test확정_환율만:
    async def test_행_날짜의_환율이_잠정이면_앞_확정일의_값과_날짜다(
        self, session_factory, client, btc
    ) -> None:
        """analyze C1 — 날짜가 지났는데 아직 잠정인 환율이 계산에 들어가면 결과에 잠정 표시가
        없다."""
        await seed_usd(session_factory, D("2019-12-01"), D("2022-12-31"),
                       provisional=[D("2021-03-01")])
        # 012 승인 2026-10-06 — 3-01은 월 행이 아니라 일 단위의 그날 행이다. 그 날짜까지 쪽을 넘겨
        # 받는다.
        body = await simulate(client, btc, before="2021-03-02", limit="1")
        march = next(r for r in body["rows"] if r["date"] == "2021-03-01")
        assert (march["fxRate"], march["fxRateDate"]) == (usd_rate(D("2021-02-28")), "2021-02-28")


class Test환율로_막힘:
    async def test_환율이_비면_202_fx다(self, client, btc) -> None:
        body = await simulate(client, btc, 202)
        assert body["fx"]["currency"] == "USD" and "jobId" not in body

    async def test_수집으로_채울_수_없는_구간이면_409다(self, session_factory, client, btc) -> None:
        async with session_factory() as s:
            await upsert(s, Currency, [{"code": "USD", "display_name": "미국 달러", "quote_unit": 1,
                                        "source_item_code": "0000001",
                                        "first_available_date": D("2020-06-01")}], preserve=())
            await s.commit()
        await seed_usd(session_factory, D("2020-06-01"), D("2022-12-31"))
        body = await simulate(client, btc, 409)
        assert (body["status"], body["reason"], body["availableFrom"]) == (
            "fx_not_available_before", "before_first_quote", "2020-06-01")

    async def test_수집했는데_값이_없으면_fx_unavailable이다(
        self, session_factory, client, btc
    ) -> None:
        """커버리지는 있는데 첫 매수일과 그 앞 한 달에 확정 환율이 하나도 없다."""
        await seed_usd(session_factory, D("2019-12-01"), D("2022-12-31"))
        async with session_factory() as s:
            await upsert(s, FxRate, [{
                "currency_code": "USD", "quote_date": D("2019-12-01") + dt.timedelta(days=i),
                "base_rate": P("1150"), "quote_unit": 1, "source": "ECOS:731Y001",
                "is_provisional": True} for i in range(60)])
            await s.commit()
        body = await simulate(client, btc, 409)
        assert body["status"] == "fx_unavailable"
