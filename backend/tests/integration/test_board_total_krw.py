"""성과 보드의 현재 잔고 — 일시금 요약의 `totalKrw` (012 T070) — FR-018, SC-010, data-model 4.1,
contracts/rest-api.md 1.2.

- 주식·가상자산 **일시금** 표 경로의 `summary`에 `totalKrw`(기준일의 원화 총자산 — 잔고 + 예수금,
  매도 비용 전)가 있다. 적립식(011)의
  `totalKrw`와 같은 이름·같은 뜻이다
- `totalKrw − (principalKrw ?? principal) = profit`이 0원 차이다 — 투자 수익을 만든 같은 원화
  평가값이다(따로 환산하면 1원이 어긋날 수 있다)
- 원화 종목·원화 원금이면 일 단위 표 기준일 행의 `balance + cash`와 같다. 행의 `balance`는 **보유
  평가액만**이라 예수금만큼 작다 — 그대로 쓰면 현재
  잔고 − 투자 원금이 투자 수익과 맞지 않는다(FR-018 실패 양상)
- `/series`에는 없다. 적립식 요약은 `totalKrw − contributedKrw = profit`이다(그대로)
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest
from httpx2 import ASGITransport, AsyncClient
from sqlalchemy import select

from src.api.main import create_app
from src.db.dialect import upsert
from src.db.models import FxCoverage, FxRate, Stock, StockCoverage, StockDividend, StockPrice
from src.db.session import get_session
from tests.integration.crypto_support import add_coin, seed_daily, seed_usd

D = dt.date.fromisoformat
KRX_DAYS = [D("2026-09-01") + dt.timedelta(days=i) for i in range(30)]
KRX_DAYS = [d for d in KRX_DAYS if d.weekday() < 5]
#: 해외 종목 — 주가도 환율도 오른다(달러 기준과 원화 기준이 다르다).
AAPL_PRICE = {
    "2021-08-02": "100",
    "2021-09-01": "100",
    "2021-09-02": "100",
    "2021-09-03": "100",
    "2021-10-01": "110",
}
USD_FX = {
    "2021-08-02": "1150",
    "2021-09-01": "1160",
    "2021-09-02": "1165",
    "2021-09-03": "1170",
    "2021-10-01": "1190",
}


@pytest.fixture
async def client(session_factory):  # type: ignore[no-untyped-def]
    async with session_factory() as s:
        await upsert(
            s,
            Stock,
            [
                {
                    "market": "KRX",
                    "symbol": "005930.KS",
                    "name": "삼성전자",
                    "currency": "KRW",
                    "first_available_date": D("1975-06-11"),
                },
                {
                    "market": "NASDAQ",
                    "symbol": "AAPL",
                    "name": "Apple Inc.",
                    "currency": "USD",
                    "first_available_date": D("1980-12-12"),
                },
            ],
        )
        await s.commit()
        ids = {r.symbol: int(r.id) for r in (await s.execute(select(Stock))).scalars()}
        await upsert(
            s,
            StockPrice,
            [
                {
                    "stock_id": ids["005930.KS"],
                    "quote_date": day,
                    "open_raw": Decimal(50000 + 100 * i),
                    "close_raw": Decimal(50050 + 100 * i),
                    "close_adjusted": Decimal(50050 + 100 * i),
                    "source": "yahoo:chart",
                }
                for i, day in enumerate(KRX_DAYS)
            ],
        )
        await upsert(
            s,
            StockPrice,
            [
                {
                    "stock_id": ids["AAPL"],
                    "quote_date": D(d),
                    "open_raw": Decimal(v),
                    "close_raw": Decimal(v),
                    "close_adjusted": Decimal(v),
                    "source": "yahoo:chart",
                }
                for d, v in AAPL_PRICE.items()
            ],
        )
        await upsert(
            s,
            StockDividend,
            [
                {
                    "stock_id": ids["005930.KS"],
                    "ex_date": D("2026-09-15"),
                    "amount_per_share": Decimal("700"),
                    "source": "yahoo:chart",
                },
                {
                    "stock_id": ids["AAPL"],
                    "ex_date": D("2021-09-01"),
                    "amount_per_share": Decimal("10"),
                    "source": "yahoo:chart",
                },
            ],
        )
        await upsert(
            s,
            StockCoverage,
            [
                {
                    "stock_id": ids["005930.KS"],
                    "covered_from": D("2026-09-01"),
                    "covered_through": D("2026-10-31"),
                },
                {
                    "stock_id": ids["AAPL"],
                    "covered_from": D("2021-08-01"),
                    "covered_through": D("2021-10-31"),
                },
            ],
            preserve=(),
        )
        await upsert(
            s,
            FxRate,
            [
                {
                    "currency_code": "USD",
                    "quote_date": D(d),
                    "base_rate": Decimal(v),
                    "quote_unit": 1,
                    "source": "ECOS:731Y001",
                    "is_provisional": False,
                }
                for d, v in USD_FX.items()
            ],
        )
        await upsert(
            s,
            FxCoverage,
            [
                {
                    "currency_code": "USD",
                    "covered_from": D("2021-07-01"),
                    "covered_through": D("2021-10-31"),
                }
            ],
            preserve=(),
        )
        await s.commit()

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
    await seed_daily(
        session_factory, coin_id, "btc_2020_2021.json", covered=(D("2020-01-01"), D("2021-12-31"))
    )
    await seed_usd(session_factory, D("2019-12-01"), D("2022-12-31"))
    return coin_id


#: 재투자를 끄면 배당이 예수금에 쌓인다 — 잔고(보유 평가액)와 현재 잔고가 다르다.
KRX = {
    "market": "KRX",
    "symbol": "005930.KS",
    "start": "2026-09-01",
    "principal": "10000000",
    "principalCurrency": "KRW",
    "reinvest": "false",
    "end": "2026-09-30",
    "limit": "50",
}
AAPL = {
    "market": "NASDAQ",
    "symbol": "AAPL",
    "start": "2021-08-01",
    "end": "2021-10-31",
    "reinvest": "true",
    "limit": "50",
}


async def get(client: AsyncClient, path: str, params: dict[str, str]) -> dict:
    res = await client.get(path, params=params)
    assert res.status_code == 200, res.text
    body: dict = res.json()
    return body


def basis(summary: dict) -> Decimal:
    return Decimal(summary.get("principalKrw", summary["principal"]))


class Test주식_일시금:
    async def test_원화_원금은_원금_더하기_수익이고_기준일_행의_잔고_더하기_예수금이다(
        self, client
    ) -> None:
        body = await get(client, "/api/stocks/simulation", KRX)
        summary = body["summary"]
        total = Decimal(summary["totalKrw"])
        assert total - basis(summary) == Decimal(summary["profit"])
        latest = [r for r in body["rows"] if r["date"] == summary["asOf"]][-1]
        assert Decimal(latest["cash"]) > 0, "예수금이 있어야 이 검사가 뜻이 있다"
        assert total == Decimal(latest["balance"]) + Decimal(latest["cash"])
        assert total != Decimal(latest["balance"]), "표의 잔고 열(보유 평가액)과 다르다"

    @pytest.mark.parametrize(
        ("principal", "currency"),
        [("1000000", "KRW"), ("1000", "USD")],
        ids=["원화원금", "달러원금"],
    )
    async def test_해외_종목도_원금_더하기_수익이다(
        self, client, principal: str, currency: str
    ) -> None:
        body = await get(
            client,
            "/api/stocks/simulation",
            {**AAPL, "principal": principal, "principalCurrency": currency},
        )
        summary = body["summary"]
        assert ("principalKrw" in summary) == (currency == "USD")
        assert Decimal(summary["totalKrw"]) - basis(summary) == Decimal(summary["profit"])

    async def test_단위를_바꿔도_같다(self, client) -> None:
        totals = {
            (await get(client, "/api/stocks/simulation", {**KRX, "period": unit}))["summary"][
                "totalKrw"
            ]
            for unit in ("daily", "weekly", "monthly")
        }
        assert len(totals) == 1

    async def test_시계열에는_없다(self, client) -> None:
        res = await client.get("/api/stocks/simulation/series", params=KRX)
        assert res.status_code == 200, res.text
        assert "totalKrw" not in res.text


class Test가상자산_일시금:
    @pytest.mark.parametrize(
        ("principal", "currency"),
        [("10000000", "KRW"), ("10000", "USD")],
        ids=["원화원금", "달러원금"],
    )
    async def test_원금_더하기_수익이다(
        self, client, btc: int, principal: str, currency: str
    ) -> None:
        body = await get(
            client,
            "/api/crypto/simulation",
            {
                "coinId": str(btc),
                "start": "2021-03-01",
                "principal": principal,
                "principalCurrency": currency,
                "end": "2021-03-21",
                "limit": "50",
            },
        )
        summary = body["summary"]
        assert Decimal(summary["totalKrw"]) - basis(summary) == Decimal(summary["profit"])
        assert Decimal(summary["totalKrw"]) > 0


class Test적립식은_그대로다:
    async def test_총_납입_원금_더하기_수익이다(self, client) -> None:
        body = await get(
            client,
            "/api/stocks/recurring-simulation",
            {
                "market": "KRX",
                "symbol": "005930.KS",
                "start": "2026-09-01",
                "amount": "1000000",
                "principalCurrency": "KRW",
                "frequency": "weekly",
                "reinvest": "false",
                "end": "2026-09-30",
                "limit": "50",
            },
        )
        summary = body["summary"]
        assert Decimal(summary["totalKrw"]) - Decimal(summary["contributedKrw"]) == Decimal(
            summary["profit"]
        )
