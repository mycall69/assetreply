"""시뮬레이션 이력 경로 (012 T040) — FR-011, FR-013, FR-014, SC-006, contracts/rest-api.md 2~5·7.

- 이력은 로컬 DB에 있다. 자산군마다 따로이고, 같은 조건은 한 항목이다 — 다시 실행하면 맨 앞으로 오고
  마지막 실행 시각이 바뀐다
- 조건만 저장한다(005 R5-9). 식별자는 서버가 계산한다(T039가 화면 lib와 대조한다)
- 옮기기: 항목의 `id`는 쓰지 않고 다시 계산한다. 차례는 브라우저의 `savedAt`이고, 보관 기간은 **옮긴
  시각부터** 잰다(명확화 4) — 45일 전 항목도 남는다
- 지금 시각은 `history.utc_now`를 바꿔 정한다(UTC, 시간대 없는 값)
"""

from __future__ import annotations

import datetime as dt

import pytest
from httpx2 import ASGITransport, AsyncClient

from src.api.main import create_app
from src.api.services import history
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
OTHER = {**LUMP, "start": "2020-01-02"}
COIN = {
    "coinId": 17,
    "symbol": "BTC",
    "name": "Bitcoin",
    "nameKo": "비트코인",
    "slug": "bitcoin",
    "currency": "USD",
}
CRYPTO = {"coin": COIN, "start": "2024-01-15", "principal": "10000", "principalCurrency": "KRW"}


class Clock:
    def __init__(self) -> None:
        self.now = NOW

    def advance(self, **delta: float) -> None:
        self.now += dt.timedelta(**delta)


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


async def put(client: AsyncClient, asset: str, condition: object, status: int = 200) -> dict:
    res = await client.put(f"/api/history/{asset}", json={"condition": condition})
    assert res.status_code == status, res.text
    return res.json()


async def listed(client: AsyncClient, asset: str) -> dict:
    res = await client.get(f"/api/history/{asset}")
    assert res.status_code == 200, res.text
    return res.json()


class Test목록과_저장:
    async def test_빈_목록(self, client, clock) -> None:
        assert await listed(client, "stock") == {"entries": [], "retentionDays": 30}

    async def test_저장한_조건이_목록에_있다(self, client, clock) -> None:
        body = await put(client, "stock", LUMP)
        assert body["retentionDays"] == 30
        assert body["entries"] == [
            {
                **LUMP,
                "id": "KRX|005930.KS|2024-01-15|500000|KRW|R",
                "lastRunAt": "2026-10-06T09:00:00Z",
            }
        ]
        assert (await listed(client, "stock"))["entries"] == body["entries"]

    async def test_같은_조건은_한_항목이고_다시_실행하면_맨_앞이며_시각이_바뀐다(
        self, client, clock
    ) -> None:
        await put(client, "stock", LUMP)
        clock.advance(minutes=5)
        await put(client, "stock", OTHER)
        clock.advance(minutes=5)
        body = await put(client, "stock", LUMP)
        assert [e["start"] for e in body["entries"]] == ["2024-01-15", "2020-01-02"]
        assert body["entries"][0]["lastRunAt"] == "2026-10-06T09:10:00Z"

    async def test_마지막_실행_내림차순이다(self, client, clock) -> None:
        for start in ("2020-01-02", "2021-01-04", "2022-01-03"):
            await put(client, "stock", {**LUMP, "start": start})
            clock.advance(seconds=1)
        assert [e["start"] for e in (await listed(client, "stock"))["entries"]] == [
            "2022-01-03",
            "2021-01-04",
            "2020-01-02",
        ]

    async def test_결과는_저장하지_않는다(self, client, clock) -> None:
        body = await put(
            client, "stock", {**LUMP, "profit": "123", "returnRate": "0.1", "savedAt": "x"}
        )
        assert set(body["entries"][0]) == {"id", "lastRunAt", *LUMP}


class Test삭제:
    async def test_지우면_목록에서_빠지고_다시_지워도_200이다(self, client, clock) -> None:
        await put(client, "stock", LUMP)
        key = "KRX|005930.KS|2024-01-15|500000|KRW|R"
        first = await client.delete("/api/history/stock", params={"id": key})
        assert first.status_code == 200 and first.json()["entries"] == []
        again = await client.delete("/api/history/stock", params={"id": key})
        assert again.status_code == 200

    async def test_id가_없으면_400이다(self, client, clock) -> None:
        res = await client.delete("/api/history/stock")
        assert res.status_code == 400 and res.json()["status"] == "invalid_query"


class Test오류:
    @pytest.mark.parametrize(
        ("method", "path"),
        [
            ("GET", "/api/history/bonds"),
            ("PUT", "/api/history/bonds"),
            ("DELETE", "/api/history/bonds?id=x"),
            ("POST", "/api/history/bonds/import"),
        ],
    )
    async def test_모르는_자산군은_404다(self, client, clock, method: str, path: str) -> None:
        res = await client.request(method, path, json={"condition": LUMP, "entries": []})
        assert res.status_code == 404 and res.json()["status"] == "unknown_asset"

    async def test_틀린_조건은_422이고_칸을_말한다(self, client, clock) -> None:
        body = await put(client, "stock", {**LUMP, "principal": "0"}, status=422)
        assert body["status"] == "invalid_history" and "principal" in body["message"]

    async def test_조건이_없으면_422다(self, client, clock) -> None:
        res = await client.put("/api/history/stock", json={})
        assert res.status_code == 422 and res.json()["status"] == "invalid_history"


class Test자산군_분리:
    async def test_주식에_넣은_항목이_가상자산_목록에_없다(self, client, clock) -> None:
        await put(client, "stock", LUMP)
        await put(client, "crypto", CRYPTO)
        assert [e["id"] for e in (await listed(client, "crypto"))["entries"]] == [
            "17|2024-01-15|10000|KRW"
        ]
        assert [e["id"] for e in (await listed(client, "stock"))["entries"]] == [
            "KRX|005930.KS|2024-01-15|500000|KRW|R"
        ]
        assert (await listed(client, "deposit"))["entries"] == []


async def imported(client: AsyncClient, asset: str, entries: object, status: int = 200) -> dict:
    res = await client.post(f"/api/history/{asset}/import", json={"entries": entries})
    assert res.status_code == status, res.text
    return res.json()


class Test옮기기:
    async def test_항목을_옮기고_수를_돌려준다(self, client, clock) -> None:
        body = await imported(
            client,
            "stock",
            [
                {**LUMP, "id": "엉뚱한-식별자", "savedAt": "2026-10-01T00:00:00.000Z"},
                {**OTHER, "id": "x", "savedAt": "2026-09-30T00:00:00.000Z"},
                {"stock": STOCK, "start": "어제"},
            ],
        )
        assert (body["imported"], body["merged"], body["skipped"]) == (2, 0, 1)
        assert [e["id"] for e in body["entries"]] == [
            "KRX|005930.KS|2024-01-15|500000|KRW|R",
            "KRX|005930.KS|2020-01-02|500000|KRW|R",
        ]
        assert [e["lastRunAt"] for e in body["entries"]] == [
            "2026-10-01T00:00:00Z",
            "2026-09-30T00:00:00Z",
        ]

    async def test_45일_전_항목도_옮겨져_남는다(self, client, clock) -> None:
        """명확화 4 — 보관 기간은 옮긴 시각부터 잰다. 브라우저의 원래 시각으로 재면 옮기자마자
        지워진다."""
        body = await imported(client, "stock", [{**LUMP, "savedAt": "2026-08-22T09:00:00.000Z"}])
        assert body["imported"] == 1
        assert [e["lastRunAt"] for e in (await listed(client, "stock"))["entries"]] == [
            "2026-08-22T09:00:00Z"
        ]
        clock.advance(days=29)
        assert len((await listed(client, "stock"))["entries"]) == 1
        clock.advance(days=2)  # 옮긴 시각에서 31일
        assert (await listed(client, "stock"))["entries"] == []

    async def test_이미_있는_조건과_합치면_늦은_쪽이다(self, client, clock) -> None:
        await put(client, "stock", LUMP)  # 2026-10-06 09:00
        body = await imported(
            client,
            "stock",
            [
                {**LUMP, "savedAt": "2026-10-01T00:00:00.000Z"},
                {**OTHER, "savedAt": "2026-10-07T00:00:00.000Z"},
            ],
        )
        assert (body["imported"], body["merged"]) == (1, 1)
        assert [(e["start"], e["lastRunAt"]) for e in body["entries"]] == [
            ("2020-01-02", "2026-10-07T00:00:00Z"),
            ("2024-01-15", "2026-10-06T09:00:00Z"),
        ]

    async def test_같은_조건이_둘이면_하나로_합친다(self, client, clock) -> None:
        body = await imported(
            client,
            "stock",
            [
                {**LUMP, "savedAt": "2026-10-01T00:00:00.000Z"},
                {**LUMP, "savedAt": "2026-10-03T00:00:00.000Z"},
            ],
        )
        assert (body["imported"], body["merged"]) == (1, 1)
        assert [e["lastRunAt"] for e in body["entries"]] == ["2026-10-03T00:00:00Z"]

    async def test_savedAt이_없거나_틀리면_옮긴_시각이고_건너뛰지_않는다(
        self, client, clock
    ) -> None:
        body = await imported(client, "stock", [LUMP, {**OTHER, "savedAt": "어제"}])
        assert (body["imported"], body["skipped"]) == (2, 0)
        assert {e["lastRunAt"] for e in body["entries"]} == {"2026-10-06T09:00:00Z"}

    async def test_011_전_형식도_옮긴다(self, client, clock) -> None:
        old = {
            "id": "saemaul|2020-01-15|10000000",
            "institution": "saemaul",
            "start": "2020-01-15",
            "principal": "10000000",
            "savedAt": "2026-09-01T00:00:00.000Z",
        }
        body = await imported(client, "deposit", [old])
        assert body["entries"][0]["id"] == "saemaul|2020-01-15|10000000"
        assert "product" not in body["entries"][0]

    async def test_본문이_배열이_아니면_400이다(self, client, clock) -> None:
        res = await client.post("/api/history/stock/import", json={"entries": {"a": 1}})
        assert res.status_code == 400 and res.json()["status"] == "invalid_query"
