"""이력 보관 기간 (012 T041) — FR-012, SC-007, contracts/rest-api.md 6, research R12-10.

- 보관 기준 시각(마지막 실행 — 옮긴 항목은 옮긴 시각)이 기간보다 오래된 항목은 목록에 보이지 않고
  DB에서도 지워진다. 경과 시간으로 잰다(30일 = 30 × 24시간)
- 다시 실행한 항목은 처음 저장 시각이 오래돼도 남는다 — FR-012 실패 양상 *다른 곳에서 일어남*
- 기간을 줄이면 곧바로 지운다 — *늦게 일어남*(다음 날까지 남음)을 막는다. 다시 늘려도 돌아오지
  않는다
- `/api/history/settings`는 자산군 경로(`/api/history/{asset}`)로 잡히지 않는다
"""

from __future__ import annotations

import datetime as dt

import pytest
from httpx2 import ASGITransport, AsyncClient
from sqlalchemy import func, select

from src.api.main import create_app
from src.api.services import history
from src.db.models import SimulationHistory
from src.db.session import get_session

NOW = dt.datetime(2026, 10, 6, 9, 0, 0)
STOCK = {"market": "KRX", "symbol": "005930.KS", "name": "삼성전자", "currency": "KRW"}
LUMP = {
    "stock": STOCK,
    "start": "2024-01-15",
    "principal": "500000",
    "principalCurrency": "KRW",
    "reinvest": True,
}
DEPOSIT = {"institution": "commercial_bank", "start": "2015-01-15", "principal": "1000000"}


class Clock:
    def __init__(self) -> None:
        self.now = NOW


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> Clock:
    c = Clock()
    monkeypatch.setattr(history, "utc_now", lambda: c.now)
    return c


@pytest.fixture
async def client(session_factory):  # type: ignore[no-untyped-def]
    app = create_app()

    async def _session():  # type: ignore[no-untyped-def]
        async with session_factory() as s:
            yield s

    app.dependency_overrides[get_session] = _session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


async def run_at(
    client: AsyncClient,
    clock: Clock,
    when: dt.datetime,
    asset: str = "stock",
    condition: dict[str, object] | None = None,
) -> None:
    clock.now = when
    res = await client.put(f"/api/history/{asset}", json={"condition": condition or LUMP})
    assert res.status_code == 200, res.text


async def entries(client: AsyncClient, asset: str = "stock") -> list[dict]:
    res = await client.get(f"/api/history/{asset}")
    assert res.status_code == 200, res.text
    return res.json()["entries"]


async def stored(session_factory) -> int:  # type: ignore[no-untyped-def]
    async with session_factory() as s:
        return int(
            (await s.execute(select(func.count()).select_from(SimulationHistory))).scalar_one()
        )


class Test경계:
    async def test_30일_1초_전은_지우고_정확히_30일_전과_29일_전은_남긴다(
        self, client, clock, session_factory
    ) -> None:
        await run_at(
            client,
            clock,
            NOW - dt.timedelta(days=30, seconds=1),
            condition={**LUMP, "start": "2020-01-02"},
        )
        await run_at(
            client, clock, NOW - dt.timedelta(days=30), condition={**LUMP, "start": "2021-01-04"}
        )
        await run_at(
            client, clock, NOW - dt.timedelta(days=29), condition={**LUMP, "start": "2022-01-03"}
        )
        clock.now = NOW
        assert [e["start"] for e in await entries(client)] == ["2022-01-03", "2021-01-04"]
        assert await stored(session_factory) == 2  # 목록에서만 숨기지 않는다 — DB에서도 지웠다

    async def test_다시_실행한_항목은_처음_저장이_오래돼도_남는다(self, client, clock) -> None:
        await run_at(client, clock, NOW - dt.timedelta(days=60))
        await run_at(client, clock, NOW - dt.timedelta(days=1))
        clock.now = NOW
        assert len(await entries(client)) == 1

    async def test_무기한은_지우지_않는다(self, client, clock) -> None:
        clock.now = NOW
        res = await client.put("/api/history/settings", json={"retentionDays": None})
        assert res.status_code == 200 and res.json()["retentionDays"] is None
        await run_at(client, clock, NOW - dt.timedelta(days=4000))
        clock.now = NOW
        assert len(await entries(client)) == 1


class Test설정:
    async def test_기본값(self, client, clock) -> None:
        res = await client.get("/api/history/settings")
        assert res.status_code == 200
        assert res.json() == {
            "retentionDays": 30,
            "isDefault": True,
            "options": [7, 30, 90, 180, 365, None],
        }

    async def test_줄이면_곧바로_모든_자산군에서_지운다(
        self, client, clock, session_factory
    ) -> None:
        await run_at(client, clock, NOW - dt.timedelta(days=8))
        await run_at(client, clock, NOW - dt.timedelta(days=8), asset="deposit", condition=DEPOSIT)
        await run_at(
            client,
            clock,
            NOW - dt.timedelta(days=1),
            asset="deposit",
            condition={**DEPOSIT, "start": "2016-01-15"},
        )
        clock.now = NOW
        res = await client.put("/api/history/settings", json={"retentionDays": 7})
        assert res.status_code == 200
        assert res.json() == {
            "retentionDays": 7,
            "isDefault": False,
            "options": [7, 30, 90, 180, 365, None],
        }
        assert await stored(session_factory) == 1  # 목록을 읽기 전에 이미 지웠다
        assert await entries(client) == []
        assert [e["start"] for e in await entries(client, "deposit")] == ["2016-01-15"]

    async def test_다시_늘려도_지운_항목은_돌아오지_않는다(self, client, clock) -> None:
        await run_at(client, clock, NOW - dt.timedelta(days=8))
        clock.now = NOW
        await client.put("/api/history/settings", json={"retentionDays": 7})
        await client.put("/api/history/settings", json={"retentionDays": 365})
        assert await entries(client) == []

    @pytest.mark.parametrize("bad", [10, "30", True, 30.0, 0, -7, "unlimited"])
    async def test_선택지_밖이면_422이고_기본값으로_바꾸지_않는다(
        self, client, clock, bad: object
    ) -> None:
        res = await client.put("/api/history/settings", json={"retentionDays": bad})
        assert res.status_code == 422 and res.json()["status"] == "invalid_setting"
        assert (await client.get("/api/history/settings")).json()["retentionDays"] == 30

    async def test_retentionDays가_없으면_422다(self, client, clock) -> None:
        res = await client.put("/api/history/settings", json={})
        assert res.status_code == 422 and res.json()["status"] == "invalid_setting"

    async def test_설정_경로는_자산군_경로로_잡히지_않는다(self, client, clock) -> None:
        res = await client.get("/api/history/settings")
        assert "entries" not in res.json()
