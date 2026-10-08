"""저장한 비교 API (013 T063) — FR-016~FR-019, SC-006, contracts/rest-api.md 2~5.

- `GET /api/comparison/saved` — 최근 저장 차례(`savedAt` 내림차순, 같은 초는 `id` 내림차순). 보관
  기간이 없다
- `POST /api/comparison/saved` — 201 `{entry, entries}`. 같은 조건·이름이어도 새 행이다(명확화 3)
- `DELETE /api/comparison/saved/{id}` — 200 남은 목록, 없는 `id`도 200(멱등)
- 검증 실패 422 `invalid_comparison`. 이력 보관 기간을 줄이고 시각을 옮겨도 저장한 비교는 남는다(012
  이력과 따로)
"""

from __future__ import annotations

import datetime as dt

import pytest

from src.api.services import history, saved_comparison
from tests.integration.comparison_support import http

PATH = "/api/comparison/saved"
CONDITION = {
    "v": 1, "asset": "stock", "method": "lump_sum", "frequency": None, "start": "2020-01-02",
    "amount": "10000000", "principalCurrency": "KRW", "reinvest": True,
    "targets": [{"market": "KRX", "symbol": "005930.KS", "name": "삼성전자", "currency": "KRW"},
                {"market": "KRX", "symbol": "000660.KS", "name": "SK하이닉스", "currency": "KRW"}]}


class Clock:
    def __init__(self) -> None:
        self.now = dt.datetime(2026, 10, 8, 3, 0, 0)

    def advance(self, **delta: float) -> None:
        self.now += dt.timedelta(**delta)


@pytest.fixture
def clock(monkeypatch) -> Clock:  # type: ignore[no-untyped-def]
    c = Clock()
    monkeypatch.setattr(saved_comparison, "utc_now", lambda: c.now)
    monkeypatch.setattr(history, "utc_now", lambda: c.now)
    return c


async def save(client, name: str, condition: object = CONDITION):  # type: ignore[no-untyped-def]
    return await client.post(PATH, json={"name": name, "condition": condition})


class Test목록과_저장:
    async def test_처음엔_빈_목록이다(self, session_factory, clock: Clock) -> None:
        async with http(session_factory) as client:
            response = await client.get(PATH)
        assert (response.status_code, response.json()) == (200, {"entries": []})

    async def test_저장은_201과_새_항목과_목록이다(self, session_factory, clock: Clock) -> None:
        async with http(session_factory) as client:
            response = await save(client, "주식 2개 · 2020-01-02 · 일시금")
        assert response.status_code == 201
        body = response.json()
        assert body["entry"] == {"id": body["entry"]["id"],
                                 "name": "주식 2개 · 2020-01-02 · 일시금",
                                 "asset": "stock", "condition": CONDITION,
                                 "savedAt": "2026-10-08T03:00:00Z"}
        assert body["entries"] == [body["entry"]]

    async def test_같은_조건과_이름도_새_행이다(self, session_factory, clock: Clock) -> None:
        async with http(session_factory) as client:
            first = (await save(client, "a")).json()["entry"]["id"]
            second = (await save(client, "a")).json()["entry"]["id"]
            entries = (await client.get(PATH)).json()["entries"]
        assert first != second
        assert [e["id"] for e in entries] == [second, first]

    async def test_차례는_최근_저장_먼저_같은_초는_id_내림차순이다(self, session_factory,
                                                     clock: Clock) -> None:
        async with http(session_factory) as client:
            a = (await save(client, "a")).json()["entry"]["id"]
            b = (await save(client, "b")).json()["entry"]["id"]
            clock.advance(minutes=5)
            c = (await save(client, "c")).json()["entry"]["id"]
            entries = (await client.get(PATH)).json()["entries"]
        assert [e["id"] for e in entries] == [c, b, a]

    async def test_금액은_받은_글자_그대로_남고_결과_키는_버려진다(self, session_factory,
                                                    clock: Clock) -> None:
        condition = {**CONDITION, "amount": "10000000.50", "summary": {"profit": "1"},
                     "comparison": {"profit": "2"}}
        async with http(session_factory) as client:
            entry = (await save(client, "a", condition)).json()["entry"]
        assert entry["condition"]["amount"] == "10000000.50"
        assert "summary" not in entry["condition"] and "comparison" not in entry["condition"]


class Test삭제:
    async def test_지우면_남은_목록이고_없는_id도_200이다(self, session_factory,
                                              clock: Clock) -> None:
        async with http(session_factory) as client:
            a = (await save(client, "a")).json()["entry"]["id"]
            b = (await save(client, "b")).json()["entry"]["id"]
            removed = await client.delete(f"{PATH}/{a}")
            again = await client.delete(f"{PATH}/{a}")
        assert removed.status_code == 200
        assert [e["id"] for e in removed.json()["entries"]] == [b]
        assert (again.status_code, [e["id"] for e in again.json()["entries"]]) == (200, [b])

    async def test_정수가_아닌_id는_422다(self, session_factory, clock: Clock) -> None:
        async with http(session_factory) as client:
            response = await client.delete(f"{PATH}/abc")
        assert response.status_code == 422


class Test거절:
    @pytest.mark.parametrize(("payload", "field"), [
        ({"name": "", "condition": CONDITION}, "name"),
        ({"name": "가" * 101, "condition": CONDITION}, "name"),
        ({"name": "a", "condition": {**CONDITION, "v": 2}}, "v"),
        ({"name": "a", "condition": {**CONDITION, "targets": CONDITION["targets"][:1]}},
         "targets"),
        ({"name": "a"}, "condition"),
    ])
    async def test_검증_실패는_422와_칸이다(self, session_factory, clock: Clock,
                                     payload: dict[str, object], field: str) -> None:
        async with http(session_factory) as client:
            response = await client.post(PATH, json=payload)
            entries = (await client.get(PATH)).json()["entries"]
        assert response.status_code == 422
        assert response.json()["status"] == "invalid_comparison"
        assert response.json()["message"].startswith(field)
        assert entries == []


class Test보관_기간_없음:
    async def test_이력_보관_기간을_줄이고_1년이_지나도_남는다(self, session_factory,
                                                clock: Clock) -> None:
        async with http(session_factory) as client:
            await save(client, "a")
            assert (await client.put("/api/history/settings",
                                     json={"retentionDays": 7})).status_code == 200
            clock.advance(days=365)
            await client.get("/api/history/stock")  # 이력 정리를 돈다
            entries = (await client.get(PATH)).json()["entries"]
        assert [e["name"] for e in entries] == ["a"]
