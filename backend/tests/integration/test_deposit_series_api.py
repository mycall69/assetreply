"""예금 차트 시계열 (T027) — 008 FR-036, SC-005, SC-009, contracts/rest-api `GET
/api/deposit/simulation/series`.

**표와 같은 판정·같은 계산이다.** 점은 표의 행 날짜(같은 날의 만기·재예치는 점 하나)에 계산 끝을
더한 것이고, 그 날짜의 값은 **표의 행과 같다** — 경로가 갈리면 차트와 표가 어긋나는데 양쪽 다
그럴듯한 숫자라 알아챌 신호가 없다(005 SC-032와 같은 이유). 끝점은 보드와 같다. 결측은 계산을
멈추므로 점 사이에 빈 구간이 없다(`gaps: []`).
"""
from __future__ import annotations

import pytest
from httpx2 import ASGITransport, AsyncClient

from src.api.main import create_app
from src.db.session import get_session
from tests.integration.deposit_support import TODAY, seed_rates

BASE = {"institution": "commercial_bank", "start": "2020-01-15", "principal": "10000000"}


@pytest.fixture
async def client(session_factory, monkeypatch):  # type: ignore[no-untyped-def]
    monkeypatch.setattr("src.api.services.deposit_simulation.kst_today", lambda: TODAY)
    app = create_app()

    async def _session():  # type: ignore[no-untyped-def]
        async with session_factory() as s:
            yield s

    app.dependency_overrides[get_session] = _session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        yield c


async def both(client, **over: str):  # type: ignore[no-untyped-def]
    params = {**BASE, **over}
    table = (await client.get("/api/deposit/simulation", params=params)).json()
    series = (await client.get("/api/deposit/simulation/series", params=params)).json()
    return table, series


class Test점과_값:
    async def test_점은_행_날짜와_계산_끝이고_값이_표와_같다(self, client, session_factory) -> None:  # type: ignore[no-untyped-def]
        await seed_rates(session_factory)
        table, series = await both(client)
        row_dates = sorted({r["date"] for r in table["rows"]})
        dates = [p["date"] for p in series["points"]]
        assert dates == [*row_dates, "2026-10-04"]
        by_date = {p["date"]: p for p in series["points"]}
        for row in table["rows"]:
            point = by_date[row["date"]]
            assert (point["balance"], point["returnRate"]) == (row["balance"], row["returnRate"])
        summary = table["summary"]
        end = series["points"][-1]
        assert int(end["balance"]) == int(summary["principal"]) + int(summary["profit"])
        assert end["returnRate"] == summary["returnRate"]

    async def test_같은_날의_만기와_재예치는_점_하나다(self, client, session_factory) -> None:  # type: ignore[no-untyped-def]
        await seed_rates(session_factory)
        _, series = await both(client)
        dates = [p["date"] for p in series["points"]]
        assert dates.count("2021-01-15") == 1
        assert len(dates) == len(set(dates))

    async def test_머리와_꼬리(self, client, session_factory) -> None:  # type: ignore[no-untyped-def]
        await seed_rates(session_factory)
        _, series = await both(client)
        assert (series["from"], series["to"]) == ("2020-01-15", "2026-10-04")
        assert (series["principalCurrency"], series["basisCurrency"]) == ("KRW", "KRW")
        assert series["gaps"] == []
        assert (series["downsampled"], series["algorithm"]) == (False, "lttb")
        assert series["sourcePointCount"] == len(series["points"])
        assert series["provisionalFrom"] is None

    async def test_점이_많으면_줄이고_원래_수를_밝힌다(self, client, session_factory) -> None:  # type: ignore[no-untyped-def]
        await seed_rates(session_factory)
        _, full = await both(client)
        small = (await client.get("/api/deposit/simulation/series",
                                  params={**BASE, "maxPoints": "10"})).json()
        assert small["downsampled"] is True
        assert small["sourcePointCount"] == len(full["points"])
        assert len(small["points"]) == 10


class Test잠정과_멈춤:
    async def test_잠정이면_그_날짜를_싣는다(self, client, session_factory) -> None:  # type: ignore[no-untyped-def]
        await seed_rates(session_factory)
        table, series = await both(client, start="2025-09-15")
        assert series["provisionalFrom"] == table["summary"]["provisionalFrom"] == "2026-09-15"
        assert "2026-09-15" in [p["date"] for p in series["points"]]

    async def test_결측으로_멈추면_그_만기일에서_끝난다(self, client, session_factory) -> None:  # type: ignore[no-untyped-def]
        await seed_rates(session_factory, drop=("2021-01",))
        table, series = await both(client)
        assert series["to"] == table["summary"]["asOf"] == "2021-01-15"
        assert series["points"][-1]["date"] == "2021-01-15"
        assert series["gaps"] == []


class Test판정과_오류는_표와_같다:
    async def test_받지_않았으면_202(self, client) -> None:  # type: ignore[no-untyped-def]
        response = await client.get("/api/deposit/simulation/series", params=BASE)
        assert response.status_code == 202
        assert response.json()["status"] == "collecting"
        assert (response.json()["missingFrom"], response.json()["missingThrough"]) == (
            "2020-01", "2026-10")

    async def test_모르는_투자처(self, client) -> None:  # type: ignore[no-untyped-def]
        response = await client.get("/api/deposit/simulation/series",
                                    params={**BASE, "institution": "kakao_bank"})
        assert (response.status_code, response.json()["status"]) == (400, "unknown_institution")

    async def test_첫_달보다_이르면_409(self, client, session_factory) -> None:  # type: ignore[no-untyped-def]
        await seed_rates(session_factory)
        response = await client.get("/api/deposit/simulation/series",
                                    params={**BASE, "start": "2010-01-01"})
        assert (response.status_code, response.json()["status"]) == (409, "before_first_month")
