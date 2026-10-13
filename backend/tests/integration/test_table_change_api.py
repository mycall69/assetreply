"""주식·가상자산 일자별 표 행의 등락 (014 반복 2026-10-13b T221) — spec FR-048, SC-029, contracts
A20, data-model 19.

메뉴 시뮬레이션 경로 넷의 행에 주식 `openChange`·`closeChange`, 가상자산 `openChange`가 더해진다.

- 비교 대상은 **직전 기간의 대표값** — 일 = 직전 시세일(가상자산 결측 구간은 건너뜀), 주·월 = 직전
  주·달의 대표 행. 기간 사이의 사건 행(배당락·재투자·납입)도 같은 기준이고 같은 날 행은 같은 값이다.
  계산 기간의 첫 기간은 `null`이다
- 쪽의 마지막 행도 쪽 너머의 비교 행과 견준다(`comparedTo`가 다음 쪽 행의 날짜)
- 값은 외환 표와 같은 계산(등락폭 저장 정밀도, 등락률 소수 둘째 자리 `ROUND_HALF_EVEN`). 분할 날은
  비교 가격을 분할 비율로 맞추고 `split`(`ratio`)을 싣는다

주식 달력(손으로 만든 국내·미국 종목): 2026-08-03 ~ 10-16 평일, 휴장 9-30·10-05·10-09. 국내는 9-16
배당락(재투자는 그 뒤 둘째 거래일), 미국은 9-15 효력 4:1 분할. 가상자산은 BTC 픽스처 2021-03에서
3-01·3-05·3-08~3-12를 뺀다(012 표 테스트와 같은 결측).
"""

from __future__ import annotations

import datetime as dt
from decimal import ROUND_HALF_EVEN, ROUND_HALF_UP, Decimal

import pytest
from httpx2 import ASGITransport, AsyncClient
from sqlalchemy import select

from src.api.main import create_app
from src.db.dialect import upsert
from src.db.models import Stock, StockCoverage, StockDividend, StockPrice, StockSplit
from src.db.session import get_session
from tests.integration.crypto_support import add_coin, seed_daily, seed_usd

D = dt.date.fromisoformat
HOLIDAYS = {"2026-09-30", "2026-10-05", "2026-10-09"}
SPLIT_DAY = D("2026-09-15")
ZERO_OPEN = D("2026-10-06")
CRYPTO_DROPPED = [D("2021-03-01"), D("2021-03-05"), *(D(f"2021-03-{d:02d}") for d in range(8, 13))]
Json = dict[str, object]


def trading_days() -> list[dt.date]:
    out, day = [], D("2026-08-03")
    while day <= D("2026-10-16"):
        if day.weekday() < 5 and day.isoformat() not in HOLIDAYS:
            out.append(day)
        day += dt.timedelta(days=1)
    return out


def krx_prices(i: int) -> tuple[Decimal, Decimal]:
    """시가·종가가 따로 움직이고 내리는 날도 있다 — 두 키가 같은 값이면 한쪽을 빠뜨려도 지나간다."""
    open_ = Decimal(50000 + 100 * i - (700 if i % 4 == 3 else 0))
    close = Decimal(50200 + 130 * i - (900 if i % 5 == 2 else 0))
    return open_, close


def us_prices(day: dt.date, i: int) -> tuple[Decimal, Decimal]:
    base = Decimal("400") if day < SPLIT_DAY else Decimal("100")
    step = Decimal(i) / (4 if day < SPLIT_DAY else 16)
    return base + step, base + step + Decimal("1.250000")


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
async def stocks(session_factory) -> None:  # type: ignore[no-untyped-def]
    async with session_factory() as s:
        await upsert(s, Stock, [
            {"market": "KRX", "symbol": "005930.KS", "name": "삼성전자", "currency": "KRW",
             "first_available_date": D("1975-06-11")},
            {"market": "NASDAQ", "symbol": "NVDA", "name": "NVIDIA", "currency": "USD",
             "first_available_date": D("1999-01-22")},
        ])
        await s.commit()
        ids = {r.symbol: int(r.id) for r in (await s.execute(select(Stock))).scalars()}
        rows = []
        for i, day in enumerate(trading_days()):
            for symbol, (open_, close) in (("005930.KS", krx_prices(i)),
                                           ("NVDA", us_prices(day, i))):
                if symbol == "005930.KS" and day == ZERO_OPEN:
                    open_ = Decimal("0")  # 출처가 시가를 비운 날(T226 실측과 같은 꼴)
                rows.append({"stock_id": ids[symbol], "quote_date": day, "open_raw": open_,
                             "close_raw": close, "close_adjusted": close, "source": "yahoo:chart"})
        await upsert(s, StockPrice, rows)
        await upsert(s, StockDividend, [{"stock_id": ids["005930.KS"], "ex_date": D("2026-09-16"),
                                         "amount_per_share": Decimal("400"),
                                         "source": "yahoo:chart"}])
        await upsert(s, StockSplit, [{"stock_id": ids["NVDA"], "effective_date": SPLIT_DAY,
                                      "numerator": 4, "denominator": 1, "source": "yahoo:chart"}])
        await upsert(s, StockCoverage, [
            {"stock_id": sid, "covered_from": D("2026-08-01"), "covered_through": D("2026-10-31")}
            for sid in ids.values()], preserve=())
        await s.commit()
    await seed_usd(session_factory, D("2026-07-01"), D("2026-10-31"))


@pytest.fixture
async def btc(session_factory) -> int:  # type: ignore[no-untyped-def]
    coin_id = await add_coin(session_factory)
    await seed_daily(session_factory, coin_id, "btc_2020_2021.json",
                     covered=(D("2020-01-01"), D("2021-12-31")), drop=CRYPTO_DROPPED)
    await seed_usd(session_factory, D("2019-12-01"), D("2022-12-31"))
    return coin_id


KRX = {"market": "KRX", "symbol": "005930.KS", "start": "2026-08-03", "principal": "10000000",
       "principalCurrency": "KRW", "reinvest": "true", "end": "2026-10-16", "limit": "200"}
NVDA = {**KRX, "market": "NASDAQ", "symbol": "NVDA"}
KRX_RECURRING = {"market": "KRX", "symbol": "005930.KS", "start": "2026-08-07", "amount": "1000000",
                 "principalCurrency": "KRW", "frequency": "weekly", "reinvest": "true",
                 "end": "2026-10-16", "limit": "200"}


def crypto(coin_id: int) -> dict[str, str]:
    return {"coinId": str(coin_id), "start": "2021-03-01", "principal": "10000",
            "principalCurrency": "USD", "end": "2021-03-21", "limit": "200"}


def crypto_recurring(coin_id: int) -> dict[str, str]:
    return {"coinId": str(coin_id), "start": "2021-03-01", "amount": "100",
            "principalCurrency": "USD", "frequency": "daily", "end": "2021-03-21", "limit": "200"}


async def get(client: AsyncClient, path: str, params: dict[str, str], **over: str) -> Json:
    response = await client.get(path, params={**params, **over})
    assert response.status_code == 200, response.text
    return response.json()  # type: ignore[no-any-return]


async def rows_of(client: AsyncClient, path: str, params: dict[str, str],
                  **over: str) -> list[Json]:
    rows = (await get(client, path, params, **over))["rows"]
    assert isinstance(rows, list)
    return rows


def prices(daily: list[Json], key: str) -> dict[str, Decimal]:
    """일 단위 표의 날짜별 가격 — 같은 날 행은 같은 가격이다."""
    out: dict[str, Decimal] = {}
    for row in daily:
        if row["kind"] == "missing":
            continue
        value = Decimal(str(row[key]))
        assert out.setdefault(str(row["date"]), value) == value, row["date"]
    return out


def expected(current: Decimal, previous: Decimal) -> tuple[str, str, str]:
    delta = current - previous
    percent = (delta / previous * 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)
    direction = "up" if delta > 0 else "down" if delta < 0 else "flat"
    return str(delta), str(percent), direction


def check(row: Json, key: str, price: str, by_date: dict[str, Decimal], compared_to: str | None,
          ratio: tuple[int, int] | None = None) -> None:
    change = row[key]
    if compared_to is None:
        assert change is None, (row["date"], key)
        return
    previous = by_date[compared_to]
    if Decimal(str(row[price])) <= 0 or previous <= 0:
        assert change is None, (row["date"], key)  # 0 이하는 출처가 비운 값 — 견주지 않는다
        return
    assert isinstance(change, dict), (row["date"], key, change)
    assert change["comparedTo"] == compared_to, (row["date"], key)
    if ratio is not None:
        previous = (previous * ratio[1] / ratio[0]).quantize(Decimal("0.000001"),
                                                             rounding=ROUND_HALF_UP)
    absolute, percent, direction = expected(Decimal(str(row[price])), previous)
    assert Decimal(str(change["absolute"])) == Decimal(absolute), (row["date"], key)
    assert change["percent"] == percent, (row["date"], key)
    assert change["direction"] == direction, (row["date"], key)
    want_split = None if ratio is None else {"ratio": f"{ratio[0]}:{ratio[1]}"}
    assert change["split"] == want_split, (row["date"], key)


def previous_day(days: list[str], day: str) -> str | None:
    earlier = [d for d in days if d < day]
    return earlier[-1] if earlier else None


STOCK_KEYS = (("openChange", "openPrice"), ("closeChange", "closePrice"))


class Test주식_일시금:
    async def test_일_단위는_직전_시세일_대비이고_첫_매수는_없다(self, client, stocks) -> None:
        rows = await rows_of(client, "/api/stocks/simulation", KRX)
        days = sorted({str(r["date"]) for r in rows})
        for key, price in STOCK_KEYS:
            by_date = prices(rows, price)
            for row in rows:
                check(row, key, price, by_date, previous_day(days, str(row["date"])))
        assert rows[-1]["kind"] == "buy" and rows[-1]["openChange"] is None
        oct6 = next(r for r in rows if r["date"] == "2026-10-06")
        assert oct6["closeChange"]["comparedTo"] == "2026-10-02"  # type: ignore[index]  # 휴장 10-05를 건너뜀

    async def test_시가가_0인_날과_이튿날의_시가_등락은_없다(self, client, stocks) -> None:
        rows = await rows_of(client, "/api/stocks/simulation", KRX)
        by = {str(r["date"]): r for r in rows}
        assert Decimal(str(by["2026-10-06"]["openPrice"])) == 0
        assert by["2026-10-06"]["openChange"] is None
        assert by["2026-10-07"]["openChange"] is None
        assert by["2026-10-06"]["closeChange"] is not None
        assert by["2026-10-07"]["closeChange"] is not None

    async def test_내린_날과_같은_날이_있다(self, client, stocks) -> None:
        rows = await rows_of(client, "/api/stocks/simulation", KRX)
        directions = {r["openChange"]["direction"] for r in rows if r["openChange"]}  # type: ignore[index]
        assert directions >= {"up", "down"}

    async def test_쪽_경계_행은_다음_쪽의_첫_행과_견준다(self, client, stocks) -> None:
        first = await get(client, "/api/stocks/simulation", KRX, limit="5")
        assert first["hasMore"] is True
        page = first["rows"]
        assert isinstance(page, list)
        nxt = await rows_of(client, "/api/stocks/simulation", KRX, limit="5",
                            before=str(first["oldestReturned"]))
        last = page[-1]
        for key, price in STOCK_KEYS:
            assert last[key]["comparedTo"] == nxt[0]["date"]  # type: ignore[index]
            check(last, key, price, prices([*page, *nxt], price), str(nxt[0]["date"]))

    async def test_월_단위는_직전_달_대표_행_대비이고_사이의_사건_행도_같다(
            self, client, stocks) -> None:
        daily = await rows_of(client, "/api/stocks/simulation", KRX)
        rows = await rows_of(client, "/api/stocks/simulation", KRX, period="monthly")
        kinds = {r["kind"] for r in rows if str(r["date"]).startswith("2026-09")}
        assert {"dividend", "reinvest"} <= kinds
        want = {"2026-10": "2026-09-29", "2026-09": "2026-08-31", "2026-08": None}
        for key, price in STOCK_KEYS:
            by_date = prices(daily, price)
            for row in rows:
                check(row, key, price, by_date, want[str(row["date"])[:7]])

    async def test_주_단위는_직전_주_대표_행_대비다(self, client, stocks) -> None:
        daily = await rows_of(client, "/api/stocks/simulation", KRX)
        rows = await rows_of(client, "/api/stocks/simulation", KRX, period="weekly")
        week = [r for r in rows if "2026-09-14" <= str(r["date"]) <= "2026-09-18"]
        assert {r["kind"] for r in week} >= {"dividend", "reinvest"}
        by_date = prices(daily, "closePrice")
        for row in week:
            check(row, "closeChange", "closePrice", by_date, "2026-09-11")

    async def test_분할_날은_직전_값을_분할_비율로_맞춰_견준다(self, client, stocks) -> None:
        rows = await rows_of(client, "/api/stocks/simulation", NVDA)
        days = sorted({str(r["date"]) for r in rows})
        for key, price in STOCK_KEYS:
            by_date = prices(rows, price)
            for row in rows:
                compared = previous_day(days, str(row["date"]))
                crosses = compared is not None and D(compared) < SPLIT_DAY <= D(str(row["date"]))
                check(row, key, price, by_date, compared, (4, 1) if crosses else None)
        split = next(r for r in rows if r["date"] == SPLIT_DAY.isoformat())
        assert split["closeChange"]["split"] == {"ratio": "4:1"}  # type: ignore[index]
        assert Decimal(split["closeChange"]["percent"]) > Decimal("-10")  # type: ignore[index]  # −75%가 아니다

    async def test_월_단위도_사이의_분할을_맞춘다(self, client, stocks) -> None:
        daily = await rows_of(client, "/api/stocks/simulation", NVDA)
        rows = await rows_of(client, "/api/stocks/simulation", NVDA, period="monthly")
        sep = next(r for r in rows if r["date"] == "2026-09-29")
        check(sep, "openChange", "openPrice", prices(daily, "openPrice"), "2026-08-31", (4, 1))
        oct_ = next(r for r in rows if r["date"] == "2026-10-16")
        check(oct_, "openChange", "openPrice", prices(daily, "openPrice"), "2026-09-29")

    async def test_행의_다른_키와_쪽은_그대로다(self, client, stocks) -> None:
        body = await get(client, "/api/stocks/simulation", KRX, limit="30")
        rows = body["rows"]
        assert isinstance(rows, list)
        for row in rows:
            assert {"openChange", "closeChange", "date", "kind", "openPrice",
                    "closePrice"} <= set(row)
        assert body["hasMore"] is True and body["oldestReturned"] == rows[-1]["date"]


class Test주식_적립식:
    async def test_월_단위의_납입_행과_달_끝_행이_모두_직전_달_대표_행_대비다(
            self, client, stocks) -> None:
        daily = await rows_of(client, "/api/stocks/recurring-simulation", KRX_RECURRING)
        rows = await rows_of(client, "/api/stocks/recurring-simulation", KRX_RECURRING,
                             period="monthly")
        sep = [r for r in rows if str(r["date"]).startswith("2026-09")]
        assert {r["kind"] for r in sep} >= {"contribution", "dividend", "reinvest"}
        want = {"2026-10": "2026-09-29", "2026-09": "2026-08-31", "2026-08": None}
        for key, price in STOCK_KEYS:
            by_date = prices(daily, price)
            for row in rows:
                check(row, key, price, by_date, want[str(row["date"])[:7]])

    async def test_일_단위(self, client, stocks) -> None:
        rows = await rows_of(client, "/api/stocks/recurring-simulation", KRX_RECURRING)
        days = sorted({str(r["date"]) for r in rows})
        for key, price in STOCK_KEYS:
            by_date = prices(rows, price)
            for row in rows:
                check(row, key, price, by_date, previous_day(days, str(row["date"])))


class Test가상자산:
    @pytest.mark.parametrize("path", ["/api/crypto/simulation", "/api/crypto/recurring-simulation"])
    async def test_시가만이고_결측_구간은_건너뛴다(self, client, btc: int, path: str) -> None:
        params = crypto(btc) if path == "/api/crypto/simulation" else crypto_recurring(btc)
        rows = await rows_of(client, path, params)
        priced = [r for r in rows if r["kind"] != "missing"]
        days = sorted({str(r["date"]) for r in priced})
        by_date = prices(rows, "openPrice")
        for row in priced:
            assert "closeChange" not in row
            check(row, "openChange", "openPrice", by_date, previous_day(days, str(row["date"])))
        missing = [r for r in rows if r["kind"] == "missing"]
        assert missing and all(set(r) == {"date", "dateTo", "kind"} for r in missing)
        after_gap = next(r for r in priced if r["date"] == "2021-03-13")
        assert after_gap["openChange"]["comparedTo"] == "2021-03-07"  # type: ignore[index]
        assert next(r for r in priced if r["date"] == "2021-03-02")["openChange"] is None

    async def test_가상자산_주_단위(self, client, btc: int) -> None:
        daily = await rows_of(client, "/api/crypto/simulation", crypto(btc))
        rows = await rows_of(client, "/api/crypto/simulation", crypto(btc), period="weekly")
        by_date = prices(daily, "openPrice")
        # 둘째 주(3-08~3-14)는 월~금이 결측 — 대표일은 일요일 3-14, 셋째 주는 그것과 견준다
        third = next(r for r in rows if "2021-03-15" <= str(r["date"]) <= "2021-03-21")
        check(third, "openChange", "openPrice", by_date, "2021-03-14")
        second = next(r for r in rows if r["date"] == "2021-03-14")
        check(second, "openChange", "openPrice", by_date, "2021-03-04")
