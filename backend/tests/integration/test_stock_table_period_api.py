"""주식 일시금 표의 기간 단위 (012 T015) — FR-003~FR-005, FR-007~FR-009, SC-002, SC-003, SC-005,
contracts/rest-api.md 1.

시세(손으로 만든 국내 종목): 2026-09-01 ~ 10-16 평일. 휴장 9-30(수 — 9월 말일), 10-05(월 —
대체공휴일), 10-09(금 — 한글날). 9-25(금) 배당락,
재투자는 둘째 거래일(9-28 → 9-29). 시작 9-01(화)이라 첫 매수일은 9-01이다.

- 주 대표일 = 그 주 ∩ 계산 기간에서 금요일 이하의 마지막 시세일. 월 대표일 = 그 달 ∩ 계산 기간의
  마지막 시세일
- 대표일이 기준일(금요일·말일)과 다르면 `shiftedFrom`, 구간의 끝이 계산 끝 뒤면 `isOngoing: true`.
  없으면 키가 없다
- 사건 행(`buy`·`dividend`·`reinvest`)은 단위와 관계없이 모두 있다. 대표일에 사건이 있으면 기간 행이
  없고 그 사건 행이 표시를 진다
- `summary`·`condition`과 시계열은 단위와 무관하다(FR-007)
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
        rows = []
        for i, day in enumerate(trading_days()):
            price = Decimal(50000 + 100 * i)
            rows.append(
                {
                    "stock_id": stock_id,
                    "quote_date": day,
                    "open_raw": price,
                    "close_raw": price + 50,
                    "close_adjusted": price + 50,
                    "source": "yahoo:chart",
                }
            )
        await upsert(s, StockPrice, rows)
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

    app = create_app()

    async def _override():  # type: ignore[no-untyped-def]
        async with session_factory() as s:
            yield s

    app.dependency_overrides[get_session] = _override
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


PARAMS = {
    "market": "KRX",
    "symbol": "005930.KS",
    "start": "2026-09-01",
    "principal": "10000000",
    "principalCurrency": "KRW",
    "reinvest": "true",
    "end": "2026-10-12",
    "limit": "200",
}


async def fetch(client: AsyncClient, status: int = 200, **over: str) -> dict:
    res = await client.get("/api/stocks/simulation", params={**PARAMS, **over})
    assert res.status_code == status, res.text
    return res.json()


def shape(rows: list[dict]) -> list[tuple[str, str, str | None, bool]]:
    return [(r["date"], r["kind"], r.get("shiftedFrom"), r.get("isOngoing", False)) for r in rows]


class Test질의:
    async def test_단위를_주지_않으면_일_단위이고_응답에_단위를_싣는다(self, client) -> None:
        assert (await fetch(client))["period"] == "daily"
        assert (await fetch(client, period="weekly"))["period"] == "weekly"
        assert (await fetch(client, period="monthly"))["period"] == "monthly"

    @pytest.mark.parametrize("bad", ["yearly", "", "Weekly"])
    async def test_틀린_단위는_400이고_기본값으로_바꾸지_않는다(self, client, bad: str) -> None:
        body = await fetch(client, 400, period=bad)
        assert body["status"] == "invalid_query"
        assert body["message"].startswith("기간 단위는 daily · weekly · monthly 중 하나여야 합니다")


class Test행_종류:
    async def test_행의_종류와_매수_행(self, client) -> None:
        for unit in ("daily", "weekly", "monthly"):
            rows = (await fetch(client, period=unit))["rows"]
            kinds = {r["kind"] for r in rows}
            assert kinds <= {"buy", "period", "dividend", "reinvest"}, unit
            assert "month_first" not in kinds
            [buy] = [r for r in rows if r["kind"] == "buy"]
            assert buy["date"] == "2026-09-01" and buy["boughtShares"] > 0 and "tradeFee" in buy

    async def test_일_단위는_시세일마다_한_행이다(self, client) -> None:
        rows = (await fetch(client))["rows"]
        assert [r["date"] for r in rows] == [
            d.isoformat() for d in reversed(trading_days()) if d <= D("2026-10-12")
        ]
        assert all("shiftedFrom" not in r and "isOngoing" not in r for r in rows)
        period = next(r for r in rows if r["kind"] == "period")
        assert (
            period["boughtShares"] == 0
            and "tradeFee" not in period
            and "dividendPerShare" not in period
        )

    async def test_사건_행은_세_단위에_모두_같은_수다(self, client) -> None:
        counts = []
        for unit in ("daily", "weekly", "monthly"):
            rows = (await fetch(client, period=unit))["rows"]
            counts.append(
                sorted(
                    (r["date"], r["kind"])
                    for r in rows
                    if r["kind"] in {"buy", "dividend", "reinvest"}
                )
            )
        assert counts[0] == counts[1] == counts[2]
        assert counts[0] == [
            ("2026-09-01", "buy"),
            ("2026-09-25", "dividend"),
            ("2026-09-29", "reinvest"),
        ]


class Test표시:
    async def test_주_단위(self, client) -> None:
        rows = (await fetch(client, period="weekly"))["rows"]
        assert shape(rows) == [
            ("2026-10-12", "period", "2026-10-16", True),  # 이번 주 — 계산 끝(월)까지, 진행 중
            ("2026-10-08", "period", "2026-10-09", False),  # 금요일 한글날 → 목요일
            ("2026-10-02", "period", None, False),
            ("2026-09-29", "reinvest", None, False),  # 사건 행 — 대표일이 아니어도 늘 있다
            (
                "2026-09-25",
                "dividend",
                None,
                False,
            ),  # 금요일 = 배당락일 — 기간 행 없이 사건 행이 그 주를 보인다
            ("2026-09-18", "period", None, False),
            ("2026-09-11", "period", None, False),
            ("2026-09-04", "period", None, False),
            ("2026-09-01", "buy", None, False),
        ]

    async def test_월_단위_대표일의_사건_행이_표시를_지고_날짜는_사건_날_그대로다(
        self, client
    ) -> None:
        rows = (await fetch(client, period="monthly"))["rows"]
        assert shape(rows) == [
            ("2026-10-12", "period", "2026-10-31", True),
            (
                "2026-09-29",
                "reinvest",
                "2026-09-30",
                False,
            ),  # 말일 휴장 — 9월 대표일이 재투자일이다
            ("2026-09-25", "dividend", None, False),
            ("2026-09-01", "buy", None, False),
        ]

    async def test_계산_끝이_대체공휴일이면_그_주의_행이_없다(self, client) -> None:
        weekly = (await fetch(client, period="weekly", end="2026-10-05"))["rows"]
        assert shape(weekly)[0] == ("2026-10-02", "period", None, False)
        monthly = (await fetch(client, period="monthly", end="2026-10-05"))["rows"]
        assert shape(monthly)[0] == ("2026-10-02", "period", "2026-10-31", True)


class Test단위와_무관:
    async def test_요약과_조건이_세_단위에서_같다(self, client) -> None:
        bodies = [await fetch(client, period=unit) for unit in ("daily", "weekly", "monthly")]
        for key in ("summary", "condition", "stock"):
            assert bodies[0][key] == bodies[1][key] == bodies[2][key], key
        assert "period" not in bodies[0]["condition"]

    async def test_시계열은_단위와_무관하다(self, client) -> None:
        params = {k: v for k, v in PARAMS.items() if k != "limit"}
        plain = await client.get("/api/stocks/simulation/series", params=params)
        weekly = await client.get(
            "/api/stocks/simulation/series", params={**params, "period": "weekly"}
        )
        assert plain.status_code == weekly.status_code == 200
        assert plain.json() == weekly.json()


class Test쪽:
    @pytest.mark.parametrize(("unit", "limit"), [("daily", "7"), ("weekly", "2"), ("monthly", "1")])
    async def test_끝까지_이어_받으면_한_번에_받은_것과_같다(
        self, client, unit: str, limit: str
    ) -> None:
        whole = (await fetch(client, period=unit))["rows"]
        seen: list[dict] = []
        body = await fetch(client, period=unit, limit=limit)
        seen += body["rows"]
        while body["hasMore"]:
            body = await fetch(client, period=unit, limit=limit, before=body["oldestReturned"])
            seen += body["rows"]
        assert seen == whole
        assert body["oldestReturned"] == "2026-09-01"
