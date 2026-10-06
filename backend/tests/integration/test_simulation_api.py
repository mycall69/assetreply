"""시뮬레이션 표 API (T029) — 005 FR-024~029, contracts/rest-api.

금액·비율은 모두 **문자열**이다. JSON `number`는 IEEE 754라 `Decimal` 정밀도가
손실되며, 이는 헌법 원칙 VI를 API 경계에서 무력화한다.
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

# 2021-08 ~ 2021-11의 평일 시세. 2021-09-01에 배당이 있다.
MONTHS = {
    "2021-08": ["2021-08-02", "2021-08-03"],
    "2021-09": ["2021-09-01", "2021-09-02"],
    "2021-10": ["2021-10-01", "2021-10-05"],
    "2021-11": ["2021-11-01", "2021-11-02"],
}


@pytest.fixture
async def client(session_factory):
    async with session_factory() as s:
        await upsert(s, Stock, [{
            "market": "KRX", "symbol": "005930.KS", "name": "삼성전자",
            "currency": "KRW", "first_available_date": D("1975-06-11")}])
        await s.commit()
        stock_id = int((await s.execute(select(Stock))).scalar_one().id)

        rows = []
        price = Decimal("40000")
        for days in MONTHS.values():
            for day in days:
                rows.append({
                    "stock_id": stock_id, "quote_date": D(day),
                    "open_raw": price, "close_raw": price,
                    "close_adjusted": price, "source": "yahoo:chart"})
                price += Decimal("1000")
        await upsert(s, StockPrice, rows)
        await upsert(s, StockDividend, [{
            "stock_id": stock_id, "ex_date": D("2021-09-01"),
            "amount_per_share": Decimal("300"), "source": "yahoo:chart"}])
        await upsert(s, StockCoverage, [{
            "stock_id": stock_id, "covered_from": D("2021-08-01"),
            "covered_through": D("2021-11-30")}], preserve=())
        await s.commit()

    app = create_app()

    async def _override():
        async with session_factory() as s:
            yield s

    app.dependency_overrides[get_session] = _override
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


PARAMS = {
    "market": "KRX", "symbol": "005930.KS", "start": "2021-08-01",
    "principal": "86997", "principalCurrency": "KRW", "reinvest": "true",
    "end": "2021-11-30",
}


async def fetch(client: AsyncClient, **over: object) -> dict:
    params = {**PARAMS, **over}
    res = await client.get("/api/stocks/simulation", params=params)
    assert res.status_code == 200, res.text
    return res.json()


class Test행_구조:
    async def test_행이_최신순이다(self, client) -> None:
        body = await fetch(client)
        dates = [r["date"] for r in body["rows"]]
        assert dates == sorted(dates, reverse=True)

    async def test_행의_종류는_매수_기간_배당락_재투자다(self, client) -> None:
        """012 FR-003~FR-005(승인 2026-10-06) — 005 FR-025의 월 첫 거래일 스냅샷을 기간 행이
        대체했다."""
        body = await fetch(client, limit=50)
        assert {r["kind"] for r in body["rows"]} <= {"buy", "period", "dividend", "reinvest"}

    async def test_날짜가_실제_거래일이다(self, client) -> None:
        """FR-028 — "2021년 8월"이 아니라 "2021-08-02"다."""
        body = await fetch(client, limit=50)
        all_days = {d for days in MONTHS.values() for d in days}
        assert {r["date"] for r in body["rows"]} <= all_days

    async def test_월_행에_배당_키가_없다(self, client) -> None:
        """FR-026 — 0을 넣으면 "배당이 0원"과 "배당이 없음"을 구별할 수 없다."""
        body = await fetch(client, limit=50)
        for row in body["rows"]:
            if row["kind"] == "month_first":
                assert "dividendPerShare" not in row
                assert "dividendYield" not in row

    async def test_배당락_행에는_배당_값이_있다(self, client) -> None:
        body = await fetch(client, limit=50)
        dividend = next(r for r in body["rows"] if r["kind"] == "dividend")
        assert dividend["dividendPerShare"] == "300.000000"
        assert "dividendYield" in dividend


class Test정밀도:
    async def test_금액과_비율이_문자열이다(self, client) -> None:
        """헌법 원칙 VI — JSON number는 IEEE 754라 경계에서 정밀도가 무너진다."""
        body = await fetch(client)
        row = body["rows"][0]
        for key in ("openPrice", "cash", "principal", "balance", "profit",
                    "returnRate"):
            assert isinstance(row[key], str), f"{key}가 문자열이 아니다"

    async def test_주식_수는_정수다(self, client) -> None:
        body = await fetch(client)
        row = body["rows"][0]
        assert isinstance(row["heldShares"], int)
        assert isinstance(row["boughtShares"], int)


class Test페이지:
    async def test_limit으로_행_수를_제한한다(self, client) -> None:
        body = await fetch(client, limit=2)
        assert len(body["rows"]) == 2
        assert body["hasMore"] is True

    async def test_before로_더_과거를_이어_받는다(self, client) -> None:
        """FR-029 — 004의 커서 방식을 잇는다."""
        first = await fetch(client, limit=2)
        more = await fetch(client, limit=2, before=first["oldestReturned"])
        assert all(r["date"] < first["oldestReturned"] for r in more["rows"])

    async def test_마지막_페이지는_hasMore가_거짓이다(self, client) -> None:
        body = await fetch(client, limit=50)
        assert body["hasMore"] is False


class Test요약과_조건:
    async def test_요약에_원금과_수익과_수익률이_있다(self, client) -> None:
        body = await fetch(client)
        summary = body["summary"]
        assert summary["principal"] == "86997"
        assert isinstance(summary["profit"], str)
        assert isinstance(summary["returnRate"], str)

    async def test_요약에_기준일과_최종_여부가_있다(self, client) -> None:
        """FR-014b — `isFinal`은 항상 명시된다."""
        body = await fetch(client)
        assert body["summary"]["asOf"] == "2021-11-02"
        assert isinstance(body["summary"]["isFinal"], bool)

    async def test_적용된_조건이_실린다(self, client) -> None:
        """FR-018 — 설정은 바뀌므로 값만 남으면 어느 조건의 결과인지 알 수 없다."""
        body = await fetch(client)
        condition = body["condition"]
        assert condition["start"] == "2021-08-01"
        assert condition["reinvest"] is True
        assert "tradeFeeRate" in condition
        assert "dividendTaxRate" in condition

    async def test_종목_정보가_실린다(self, client) -> None:
        body = await fetch(client)
        assert body["stock"]["symbol"] == "005930.KS"
        assert body["stock"]["currency"] == "KRW"


class Test환전_없음:
    async def test_같은_통화면_환전_정보가_없다(self, client) -> None:
        """FR-023 — 환전이 일어나지 않는다."""
        body = await fetch(client)
        assert "exchange" not in body
        assert all("fxRate" not in r for r in body["rows"])
