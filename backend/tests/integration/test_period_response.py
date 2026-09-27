"""기간 단위 응답 필드 (T020, T021) — 004 FR-014, FR-015a, FR-017, FR-018, SC-012.

**세 사실은 각각 따로 실린다** (FR-015b). `shiftedFrom`·`isOngoing`·`isProvisional`은
동시에 참일 수 있고, 하나로 합쳐 보내면 화면이 되돌릴 수 없다 (research R4-4).

`shiftedFrom`은 **옮겨졌을 때만 키가 있다** (FR-014). 정상 상태에 값을 두면 화면이
존재 여부가 아니라 내용을 검사해야 한다.
"""
from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest
from httpx2 import ASGITransport, AsyncClient

from src.api.main import create_app
from src.db.dialect import upsert
from src.db.models import FxRate
from src.db.session import get_session

TODAY = dt.date.today()

# 2026-07-17(금) 결측 → 그 주는 07-16(목)이 마지막 → 옮겨짐
# 2026-07-24·07-31은 금요일 → 옮겨지지 않음. 07-31은 7월 말일이기도 하다
# 2026-08-14가 8월의 마지막 고시 → 월 단위에서 08-31로부터 옮겨짐
FIXED = ["2026-07-13", "2026-07-16", "2026-07-24", "2026-07-31", "2026-08-14"]


@pytest.fixture
async def client(session_factory):
    async with session_factory() as s:
        await upsert(s, FxRate, [
            {"currency_code": "USD", "quote_date": dt.date.fromisoformat(d),
             "base_rate": Decimal("1300.00") + Decimal(i), "quote_unit": 1,
             "source": "ECOS:731Y001", "is_provisional": False}
            for i, d in enumerate(FIXED)
        ] + [
            # 오늘의 잠정값 — 진행 중 구간과 잠정값이 한 행에 겹치는 경우를 만든다
            {"currency_code": "USD", "quote_date": TODAY,
             "base_rate": Decimal("1360.00"), "quote_unit": 1,
             "source": "ECOS:731Y001", "is_provisional": True},
        ])
        await s.commit()

    app = create_app()

    async def _override():
        async with session_factory() as s:
            yield s

    app.dependency_overrides[get_session] = _override
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


async def rows(client: AsyncClient, unit: str) -> dict[str, dict[str, object]]:
    body = (await client.get(
        "/api/fx/daily", params={"currency": "USD", "period": unit, "limit": 200})).json()
    return {r["date"]: r for r in body["rows"]}


@pytest.mark.parametrize("unit", ["daily", "weekly", "monthly"])
async def test_구간_필드는_모든_단위에_있다(client: AsyncClient, unit: str) -> None:
    """단위에 따라 응답 구조가 달라지면 화면이 두 형태를 다뤄야 한다."""
    for row in (await rows(client, unit)).values():
        assert {"periodFrom", "periodTo", "isOngoing"} <= set(row)
        assert isinstance(row["isOngoing"], bool)


async def test_일_단위의_구간은_그날_하루다(client: AsyncClient) -> None:
    for date, row in (await rows(client, "daily")).items():
        assert row["periodFrom"] == date
        assert row["periodTo"] == date
        assert row["isOngoing"] is False
        assert "shiftedFrom" not in row


async def test_옮겨진_행에만_원래_기준일이_실린다(client: AsyncClient) -> None:
    """FR-013, FR-014 — 모든 행에 늘 표시가 있으면 구별의 의미가 사라진다."""
    weekly = await rows(client, "weekly")
    assert weekly["2026-07-16"]["shiftedFrom"] == "2026-07-17"
    assert "shiftedFrom" not in weekly["2026-07-24"]
    assert "shiftedFrom" not in weekly["2026-07-31"]


async def test_월_단위도_같은_방식으로_옮긴다(client: AsyncClient) -> None:
    monthly = await rows(client, "monthly")
    assert monthly["2026-08-14"]["shiftedFrom"] == "2026-08-31"
    assert "shiftedFrom" not in monthly["2026-07-31"]  # 7월 말일에 고시가 있었다


async def test_주_경계가_응답에_그대로_실린다(client: AsyncClient) -> None:
    """FR-019 — 선택 날짜가 어느 행에 속하는지 화면이 판정하려면 필요하다."""
    row = (await rows(client, "weekly"))["2026-07-16"]
    assert row["periodFrom"] == "2026-07-13"  # 월요일
    assert row["periodTo"] == "2026-07-19"  # 일요일


@pytest.mark.parametrize("unit", ["weekly", "monthly"])
async def test_아직_끝나지_않은_구간은_진행_중이다(client: AsyncClient, unit: str) -> None:
    """FR-015a — 드러나지 않으면 사용자는 그 값을 구간의 마지막 값으로 읽는다."""
    row = (await rows(client, unit))[TODAY.isoformat()]
    assert row["isOngoing"] is True


async def test_지난_구간은_진행_중이_아니다(client: AsyncClient) -> None:
    assert (await rows(client, "monthly"))["2026-07-31"]["isOngoing"] is False


async def test_진행_중과_잠정값은_다른_사실이다(client: AsyncClient) -> None:
    """FR-015b — 하나로 뭉뚱그리면 사용자가 이유를 알 수 없다."""
    now = (await rows(client, "weekly"))[TODAY.isoformat()]
    assert now["isOngoing"] is True
    assert now["isProvisional"] is True

    # 지난 주의 금요일 행은 셋 다 독립적으로 거짓이다 — 하나의 플래그였다면
    # 이 둘을 같은 자리에서 구별할 수 없다.
    past = (await rows(client, "weekly"))["2026-07-24"]
    assert past["isOngoing"] is False
    assert past["isProvisional"] is False
    assert "shiftedFrom" not in past


@pytest.mark.parametrize("unit", ["daily", "weekly", "monthly"])
async def test_파생_4종이_모든_단위에서_같은_규칙이다(client: AsyncClient, unit: str) -> None:
    """FR-017, SC-012 — 주·월 경로가 002의 산출을 우회하면 같은 날짜가 단위에 따라
    다른 값을 갖는다. 값은 정확해 보이고 화면도 정상이라 드러나지 않는다."""
    daily = await rows(client, "daily")
    row = (await rows(client, unit))["2026-08-14"]
    assert row["derived"] == daily["2026-08-14"]["derived"]
    assert row["baseRate"] == daily["2026-08-14"]["baseRate"]
    assert set(row["derived"]) == {"cashBuy", "cashSell", "remitSend", "remitReceive"}
    for value in row["derived"].values():
        assert isinstance(value, str)


@pytest.mark.parametrize("unit", ["daily", "weekly", "monthly"])
async def test_잠정_구분이_모든_단위에서_유지된다(client: AsyncClient, unit: str) -> None:
    """FR-018, SC-012."""
    assert (await rows(client, unit))[TODAY.isoformat()]["isProvisional"] is True
    if unit != "daily":
        assert (await rows(client, unit))["2026-07-31"]["isProvisional"] is False


@pytest.mark.parametrize("unit", ["daily", "weekly", "monthly"])
async def test_스프레드_가정_표시가_모든_단위에_남는다(client: AsyncClient, unit: str) -> None:
    """FR-017 — 현재 스프레드를 그 날짜에 적용한 가정임을 밝히는 표시."""
    body = (await client.get(
        "/api/fx/daily", params={"currency": "USD", "period": unit})).json()
    assert body["spreadBasis"] == "current"
    assert set(body["appliedSpread"]) == {
        "cashBuy", "cashSell", "remitSend", "remitReceive"}
