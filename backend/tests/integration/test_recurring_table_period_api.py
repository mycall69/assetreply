"""적립식 표의 기간 단위 (012 T017) — FR-003~FR-005, SC-003, contracts/rest-api.md 1.

주식(손으로 만든 국내 종목 — T015와 같은 달력): 2026-09-01 ~ 10-16 평일, 휴장 9-30·10-05·10-09, 9-25
배당락(재투자 9-29). 매주 금요일
납입(시작 9-04) — 10-09 한글날 납입은 10-12(월)로 미뤄진다.

- 납입 행(미뤄진 `deferred` 포함)·배당·재투자 행은 단위와 관계없이 모두 있다(FR-005)
- 납입이 있는 대표일에는 기간 행이 없고, 그날 **마지막 사건 행**(그날 상태를 보이는 행)이 표시를
  진다
- 응답 `condition`에 `period`가 없다 — 단위는 표를 고르는 것이지 계산 조건이 아니다

가상자산(BTC 픽스처): 2021-03 매일 납입, 3-05·3-08~3-12 출처 결측 — 일 단위 결측 행 수 = 시계열 끊김
수(적립식은 시작일부터 본다).
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest
from httpx2 import ASGITransport, AsyncClient
from sqlalchemy import select

from src.api.main import create_app
from src.db.dialect import upsert
from src.db.models import Stock, StockCoverage, StockDividend, StockPrice
from src.db.session import get_session
from tests.integration.crypto_support import add_coin, seed_daily, seed_usd

D = dt.date.fromisoformat
HOLIDAYS = {"2026-09-30", "2026-10-05", "2026-10-09"}


def trading_days() -> list[dt.date]:
    out, day = [], D("2026-09-01")
    while day <= D("2026-10-16"):
        if day.weekday() < 5 and day.isoformat() not in HOLIDAYS:
            out.append(day)
        day += dt.timedelta(days=1)
    return out


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
async def krx(session_factory) -> None:  # type: ignore[no-untyped-def]
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
                }
            ],
        )
        await s.commit()
        stock_id = int((await s.execute(select(Stock))).scalar_one().id)
        await upsert(
            s,
            StockPrice,
            [
                {
                    "stock_id": stock_id,
                    "quote_date": day,
                    "open_raw": Decimal(50000 + 100 * i),
                    "close_raw": Decimal(50050 + 100 * i),
                    "close_adjusted": Decimal(50050 + 100 * i),
                    "source": "yahoo:chart",
                }
                for i, day in enumerate(trading_days())
            ],
        )
        await upsert(
            s,
            StockDividend,
            [
                {
                    "stock_id": stock_id,
                    "ex_date": D("2026-09-25"),
                    "amount_per_share": Decimal("500"),
                    "source": "yahoo:chart",
                }
            ],
        )
        await upsert(
            s,
            StockCoverage,
            [
                {
                    "stock_id": stock_id,
                    "covered_from": D("2026-09-01"),
                    "covered_through": D("2026-10-31"),
                }
            ],
            preserve=(),
        )
        await s.commit()


STOCK = {
    "market": "KRX",
    "symbol": "005930.KS",
    "start": "2026-09-04",
    "amount": "1000000",
    "principalCurrency": "KRW",
    "frequency": "weekly",
    "reinvest": "true",
    "end": "2026-10-12",
    "limit": "200",
}


async def stock_table(client: AsyncClient, **over: str) -> dict:
    res = await client.get("/api/stocks/recurring-simulation", params={**STOCK, **over})
    assert res.status_code == 200, res.text
    return res.json()


def shape(rows: list[dict]) -> list[tuple[str, str, str | None, bool]]:
    return [(r["date"], r["kind"], r.get("shiftedFrom"), r.get("isOngoing", False)) for r in rows]


class Test주식_적립식:
    async def test_사건_행은_세_단위에_모두_같은_수다(self, client, krx) -> None:
        events = []
        for unit in ("daily", "weekly", "monthly"):
            rows = (await stock_table(client, period=unit))["rows"]
            events.append(
                sorted(
                    (r["date"], r["kind"], tuple(r.get("deferred", [])))
                    for r in rows
                    if r["kind"] in {"contribution", "dividend", "reinvest"}
                )
            )
            assert {r["kind"] for r in rows} <= {
                "contribution",
                "dividend",
                "reinvest",
                "period",
            }, unit
        assert events[0] == events[1] == events[2]
        assert ("2026-10-12", "contribution", ("2026-10-09",)) in events[
            0
        ]  # 미뤄진 납입 표시가 남는다

    async def test_주_단위(self, client, krx) -> None:
        rows = (await stock_table(client, period="weekly"))["rows"]
        assert shape(rows) == [
            ("2026-10-12", "contribution", "2026-10-16", True),  # 대표일의 납입 행이 표시를 진다
            ("2026-10-08", "period", "2026-10-09", False),
            ("2026-10-02", "contribution", None, False),
            ("2026-09-29", "reinvest", None, False),
            ("2026-09-25", "dividend", None, False),  # 같은 날 — 늦은 사건이 위(지금 차례 그대로)
            ("2026-09-25", "contribution", None, False),
            ("2026-09-18", "contribution", None, False),
            ("2026-09-11", "contribution", None, False),
            ("2026-09-04", "contribution", None, False),
        ]

    async def test_같은_날_사건이_여럿이면_그날_마지막_사건_행이_표시를_진다(
        self, client, krx
    ) -> None:
        rows = (await stock_table(client, period="weekly", end="2026-09-25"))["rows"]
        assert shape(rows)[:2] == [
            ("2026-09-25", "dividend", None, True),
            ("2026-09-25", "contribution", None, False),
        ]

    async def test_월_단위(self, client, krx) -> None:
        rows = (await stock_table(client, period="monthly"))["rows"]
        assert shape(rows)[:2] == [
            ("2026-10-12", "contribution", "2026-10-31", True),
            ("2026-10-02", "contribution", None, False),
        ]
        assert ("2026-09-29", "reinvest", "2026-09-30", False) in shape(
            rows
        )  # 9월 대표일(말일 휴장) = 재투자일
        assert all(r["kind"] != "period" for r in rows if r["date"] < "2026-10-01")

    async def test_조건과_요약은_단위와_무관하고_조건에_단위가_없다(self, client, krx) -> None:
        bodies = [await stock_table(client, period=unit) for unit in ("daily", "weekly", "monthly")]
        assert bodies[0]["condition"] == bodies[1]["condition"] == bodies[2]["condition"]
        assert "period" not in bodies[0]["condition"]
        assert bodies[0]["summary"] == bodies[1]["summary"] == bodies[2]["summary"]

    async def test_쪽을_나눠도_같은_날의_행이_갈리지_않는다(self, client, krx) -> None:
        whole = (await stock_table(client))["rows"]
        seen: list[dict] = []
        body = await stock_table(client, limit="1")
        while True:
            dates = {r["date"] for r in body["rows"]}
            assert len(dates) == 1  # 쪽 하나에 한 날 — 그날의 행이 모두 들어 있다
            seen += body["rows"]
            if not body["hasMore"]:
                break
            body = await stock_table(client, limit="1", before=body["oldestReturned"])
        assert seen == whole
        assert [r["kind"] for r in whole if r["date"] == "2026-09-25"] == [
            "dividend",
            "contribution",
        ]


@pytest.fixture
async def btc(session_factory) -> int:  # type: ignore[no-untyped-def]
    coin_id = await add_coin(session_factory)
    await seed_daily(
        session_factory,
        coin_id,
        "btc_2020_2021.json",
        covered=(D("2020-01-01"), D("2021-12-31")),
        drop=[D("2021-03-05"), *(D(f"2021-03-{d:02d}") for d in range(8, 13))],
    )
    await seed_usd(session_factory, D("2019-12-01"), D("2022-12-31"))
    return coin_id


def crypto_params(coin_id: int, **over: str) -> dict[str, str]:
    return {
        "coinId": str(coin_id),
        "start": "2021-03-01",
        "amount": "100",
        "principalCurrency": "USD",
        "frequency": "daily",
        "end": "2021-03-21",
        "limit": "200",
        **over,
    }


class Test가상자산_적립식:
    async def test_일_단위_결측_행_수는_시계열_끊김_수와_같다(self, client, btc: int) -> None:
        res = await client.get("/api/crypto/recurring-simulation", params=crypto_params(btc))
        assert res.status_code == 200, res.text
        rows = res.json()["rows"]
        series = await client.get(
            "/api/crypto/recurring-simulation/series", params=crypto_params(btc)
        )
        gaps = [g for g in series.json()["gaps"] if g["reason"] == "source_missing"]
        missing = [r for r in rows if r["kind"] == "missing"]
        assert sorted((r["date"], r["dateTo"]) for r in missing) == sorted(
            (g["from"], g["to"]) for g in gaps
        )
        assert len(missing) == 2
        assert all("firstDayMissing" not in r for r in rows)

    async def test_납입_행은_세_단위에_모두_같은_수다(self, client, btc: int) -> None:
        counts = []
        for unit in ("daily", "weekly", "monthly"):
            res = await client.get(
                "/api/crypto/recurring-simulation", params=crypto_params(btc, period=unit)
            )
            assert res.status_code == 200, res.text
            rows = res.json()["rows"]
            counts.append(
                sorted(
                    (r["date"], tuple(r.get("deferred", [])))
                    for r in rows
                    if r["kind"] == "contribution"
                )
            )
            assert {r["kind"] for r in rows} <= {"contribution", "period", "missing"}
        assert counts[0] == counts[1] == counts[2]
        assert (
            "2021-03-13",
            ("2021-03-08", "2021-03-09", "2021-03-10", "2021-03-11", "2021-03-12"),
        ) in counts[0]
