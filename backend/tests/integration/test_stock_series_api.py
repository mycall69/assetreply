"""차트용 시계열 API (T083a) — 005 FR-033, FR-034, FR-041, SC-032.

**표와 차트가 같은 계산을 봐야 한다.** 다른 경로를 타면 표의 마지막 행과 차트의
끝점이 달라지는데, 둘 다 그럴듯한 숫자라 사용자도 리뷰도 알아채지 못한다 (SC-032).
"""
from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest
from httpx2 import ASGITransport, AsyncClient
from sqlalchemy import select

from src.api.main import create_app
from src.db.dialect import upsert
from src.db.models import FxRate, Stock, StockCoverage, StockDividend, StockPrice
from src.db.session import get_session

D = dt.date.fromisoformat

# 2021-08 ~ 2021-11의 거래일. 2021-09-01에는 배당락 행과 월 행이 **겹친다**.
DAYS = ["2021-08-02", "2021-08-03", "2021-09-01", "2021-09-02",
        "2021-10-01", "2021-10-05", "2021-11-01", "2021-11-02"]
# 환율이 움직여야 환산이 일어났는지 드러난다.
FX = {"2021-08-02": "1150", "2021-09-01": "1160",
      "2021-10-01": "1190", "2021-11-01": "1200"}


@pytest.fixture
async def client(session_factory):
    async with session_factory() as s:
        await upsert(s, Stock, [
            {"market": "KRX", "symbol": "005930.KS", "name": "삼성전자",
             "currency": "KRW", "first_available_date": D("1975-06-11")},
            {"market": "NASDAQ", "symbol": "AAPL", "name": "Apple Inc.",
             "currency": "USD", "first_available_date": D("1980-12-12")},
        ])
        await s.commit()
        ids = {
            r.symbol: int(r.id)
            for r in (await s.execute(select(Stock))).scalars()
        }

        krx = ids["005930.KS"]
        rows = []
        price = Decimal("40000")
        for day in DAYS:
            rows.append({
                "stock_id": krx, "quote_date": D(day),
                "open_raw": price, "close_raw": price,
                "close_adjusted": price, "source": "yahoo:chart"})
            price += Decimal("1000")
        # 주가를 고정해 두면 환산이 일어났는지가 환율 변동만으로 드러난다.
        rows += [{
            "stock_id": ids["AAPL"], "quote_date": D(day),
            "open_raw": Decimal("100"), "close_raw": Decimal("100"),
            "close_adjusted": Decimal("100"), "source": "yahoo:chart"}
            for day in DAYS]
        await upsert(s, StockPrice, rows)

        await upsert(s, StockDividend, [{
            "stock_id": krx, "ex_date": D("2021-09-01"),
            "amount_per_share": Decimal("300"), "source": "yahoo:chart"}])
        await upsert(s, StockCoverage, [
            {"stock_id": krx, "covered_from": D("2021-08-01"),
             "covered_through": D("2021-11-30")},
            {"stock_id": ids["AAPL"], "covered_from": D("2021-08-01"),
             "covered_through": D("2021-11-30")},
        ], preserve=())
        await upsert(s, FxRate, [{
            "currency_code": "USD", "quote_date": D(d),
            "base_rate": Decimal(v), "quote_unit": 1,
            "source": "ECOS:731Y001", "is_provisional": False}
            for d, v in FX.items()])
        await s.commit()

    app = create_app()

    async def _override():
        async with session_factory() as s:
            yield s

    app.dependency_overrides[get_session] = _override
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


PARAMS = {"market": "KRX", "symbol": "005930.KS", "start": "2021-08-01",
          "principal": "86997", "principalCurrency": "KRW", "reinvest": "true",
          "end": "2021-11-30"}

USD_PARAMS = {"market": "NASDAQ", "symbol": "AAPL", "start": "2021-08-01",
              "principal": "1000000", "principalCurrency": "KRW",
              "reinvest": "true", "end": "2021-11-30"}


async def series(client: AsyncClient, **over: object) -> dict:
    res = await client.get("/api/stocks/simulation/series",
                           params={**PARAMS, **over})
    assert res.status_code == 200, res.text
    return res.json()


async def table(client: AsyncClient, **over: object) -> dict:
    res = await client.get("/api/stocks/simulation",
                           params={**PARAMS, "limit": "200", **over})
    assert res.status_code == 200, res.text
    return res.json()


class Test표와의_일치:
    async def test_끝점이_표의_최신_행과_같은_날짜다(self, client) -> None:
        """SC-032 — 표의 마지막 행과 차트 끝점이 어긋나면 안 된다."""
        body = await series(client)
        rows = (await table(client))["rows"]
        assert body["points"][-1]["date"] == rows[0]["date"]

    async def test_모든_점의_수치가_표의_같은_날짜_행과_같다(self, client) -> None:
        """다른 계산 경로를 타면 **둘 다 그럴듯한 다른 숫자**가 나온다."""
        body = await series(client)
        rows = (await table(client))["rows"]
        by_date: dict[str, list[dict]] = {}
        for row in rows:
            by_date.setdefault(row["date"], []).append(row)

        for point in body["points"]:
            same_day = by_date[point["date"]]
            assert any(
                r["balance"] == point["balance"]
                and r["returnRate"] == point["returnRate"]
                for r in same_day), f"{point['date']}의 수치가 표와 다르다"

    async def test_한_날짜에_점이_하나다(self, client) -> None:
        """2021-09-01은 배당락 행과 월 행이 겹친다.

        점을 둘 넣으면 같은 x에 값이 둘이라 차트가 되돌아 그려지거나 라이브러리가
        거부한다 — 표는 멀쩡한데 차트만 깨진다.
        """
        body = await series(client)
        dates = [p["date"] for p in body["points"]]
        assert len(dates) == len(set(dates))

    async def test_점이_날짜_오름차순이다(self, client) -> None:
        body = await series(client)
        dates = [p["date"] for p in body["points"]]
        assert dates == sorted(dates)


class Test결측_구간:
    async def test_휴장일과_미수집이_구분된다(self, client) -> None:
        """FR-034 — 화면이 휴장일은 잇고 미수집은 끊는 근거다 (001 FR-032)."""
        body = await series(client, end="2021-12-31")
        reasons = {g["reason"] for g in body["gaps"]}
        assert "no_quote" in reasons, "커버리지 안의 휴장일이 표시되지 않았다"
        assert "not_collected" in reasons, "커버리지 밖 구간이 표시되지 않았다"

    async def test_커버리지_밖이_미수집이다(self, client) -> None:
        body = await series(client, end="2021-12-31")
        not_collected = [g for g in body["gaps"] if g["reason"] == "not_collected"]
        assert any(g["from"] == "2021-12-01" and g["to"] == "2021-12-31"
                   for g in not_collected), not_collected

    async def test_주말이_미수집으로_분류되지_않는다(self, client) -> None:
        """끊어 그리면 사용자는 받지 못한 구간이 있다고 읽는다."""
        body = await series(client)
        for gap in body["gaps"]:
            if gap["reason"] != "not_collected":
                continue
            assert gap["from"] > "2021-11-30" or gap["to"] < "2021-08-01", gap


class Test원금_통화:
    async def test_기준_통화가_응답에_실린다(self, client) -> None:
        """FR-041 — 밝히지 않으면 사용자가 어느 쪽을 보는지 모른다."""
        body = await series(client, **USD_PARAMS)
        assert body["principalCurrency"] == "KRW"

    async def test_잔고가_원금_통화_규모다(self, client) -> None:
        """종목 통화(USD) 기준이면 100만이 아니라 1천 단위가 나온다."""
        body = await series(client, **USD_PARAMS)
        last = Decimal(body["points"][-1]["balance"])
        assert last > Decimal("100000"), f"종목 통화 기준으로 보인다: {last}"

    async def test_환율이_움직이면_잔고도_움직인다(self, client) -> None:
        """FR-041a — 초기 환율 하나로 전 구간을 환산하면 평평해진다.

        주가를 고정했으므로 변하는 것은 환율뿐이다. 그래도 잔고가 같다면 기준일마다의
        환산이 일어나지 않은 것이다.
        """
        body = await series(client, **USD_PARAMS)
        balances = {p["balance"] for p in body["points"]}
        assert len(balances) > 1, "환율이 움직였는데 잔고가 한 값뿐이다"


class Test다운샘플링:
    async def test_한계를_넘으면_줄이고_그_사실을_밝힌다(self, client) -> None:
        body = await series(client, maxPoints=2)
        assert body["downsampled"] is True
        assert body["algorithm"] == "lttb"
        assert len(body["points"]) <= 2
        assert body["sourcePointCount"] > 2

    async def test_줄여도_끝점은_남는다(self, client) -> None:
        """SC-032는 다운샘플링 뒤에도 성립해야 한다."""
        full = await series(client)
        reduced = await series(client, maxPoints=2)
        assert reduced["points"][-1] == full["points"][-1]
        assert reduced["points"][0] == full["points"][0]

    async def test_한계_안이면_줄이지_않는다(self, client) -> None:
        body = await series(client)
        assert body["downsampled"] is False
        assert len(body["points"]) == body["sourcePointCount"]


class Test정밀도:
    async def test_금액과_비율이_문자열이다(self, client) -> None:
        """헌법 원칙 VI — JSON number는 IEEE 754라 경계에서 정밀도가 무너진다."""
        body = await series(client)
        point = body["points"][0]
        assert isinstance(point["balance"], str)
        assert isinstance(point["returnRate"], str)
