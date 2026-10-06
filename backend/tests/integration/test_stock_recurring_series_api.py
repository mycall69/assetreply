"""주식 적립식 시계열 (011 T016) — `GET /api/stocks/recurring-simulation/series`. FR-015, FR-016,
contracts/rest-api §1.

- 점은 표의 행 날짜다 — 같은 날의 행이 여럿이면 그 날의 마지막 상태 하나다
- `balance`는 **원화 총자산**(잔고 + 매수 대기금 + 배당 현금)이다. 일시금 시계열의 잔고(보유분만)와
  다르다 — 1주 미만이라 모은 돈이 선에서 빠지면
  누적 납입 원금 선보다 잔고가 늘 낮아 손실처럼 보인다
- `principal` = 그날까지의 원화 총 납입 원금(표의 `contributedKrw`)
- `price` = 010 반복 1의 수정 종가(시드에 분할이 없어 원주가 종가)
- `maxPoints`로 줄여도 점마다 값이 원래 점과 같다
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from httpx2 import AsyncClient

from tests.integration.stock_recurring_support import (
    AAPL_WEEKLY,
    KRX_MONTHLY,
    app_for,
    client_for,
    krx_price,
    seed,
)

TABLE = "/api/stocks/recurring-simulation"
SERIES = TABLE + "/series"


@pytest.fixture
async def client(session_factory):  # type: ignore[no-untyped-def]
    await seed(session_factory)
    async with client_for(app_for(session_factory)) as http:
        yield http


async def both(http: AsyncClient, params: dict[str, str]) -> tuple[dict, dict]:  # type: ignore[type-arg]
    table = await http.get(TABLE, params={**params, "limit": "200"})
    series = await http.get(SERIES, params=params)
    assert table.status_code == series.status_code == 200, (table.text, series.text)
    return table.json(), series.json()


@pytest.mark.parametrize("params", [KRX_MONTHLY, AAPL_WEEKLY])
async def test_점은_표의_날짜이고_총자산과_누적_납입_원금이다(client: AsyncClient,
                                               params: dict[str, str]) -> None:
    table, series = await both(client, params)
    last_of_day: dict[str, dict] = {}  # type: ignore[type-arg]
    for row in reversed(table["rows"]):  # 오름차순 — 같은 날의 나중 행이 마지막 상태
        last_of_day[row["date"]] = row
    # 012 승인 2026-10-06 — 차트는 그대로(사건 날·그 달 첫 거래일)이고 일 단위 표가 더 촘촘하다.
    # 점마다 같은 날짜의 표 행이 있다.
    assert {p["date"] for p in series["points"]} <= set(last_of_day)
    for point in series["points"]:
        row = last_of_day[point["date"]]
        assert point["principal"] == row["contributedKrw"]
        assert Decimal(point["balance"]) == Decimal(row["profit"]) + Decimal(row["contributedKrw"])
        assert point["returnRate"] == row["returnRate"]
    assert (series["basisCurrency"], series["priceKind"]) == ("KRW", "stock_adjusted_close")


async def test_주가는_수정_종가다(client: AsyncClient) -> None:
    _, series = await both(client, KRX_MONTHLY)
    # DB 자릿수의 문자열 — 값으로 비교한다(사용자 승인 2026-10-06)
    assert Decimal(series["points"][0]["price"]) == krx_price("2026-01-02")[1]
    assert series["priceCurrency"] == "KRW"


async def test_줄여도_점의_값이_같다(client: AsyncClient) -> None:
    _, full = await both(client, AAPL_WEEKLY)
    reduced = (await client.get(SERIES, params={**AAPL_WEEKLY, "maxPoints": "2"})).json()
    by_date = {p["date"]: p for p in full["points"]}
    assert reduced["downsampled"] is True and len(reduced["points"]) == 2
    assert all(p == by_date[p["date"]] for p in reduced["points"])
