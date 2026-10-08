"""저장한 비교 서비스 — 메모리 안 가짜 저장소로 (013 T083) — FR-016, FR-018, SC-006, 헌법 원칙 IV.

서비스는 저장소 Protocol(`SavedComparisonRepository`)에 기댄다 — DB 없이 이 가짜로 돈다. 저장은
정규화한 조건 글과 이름을 저장소에 넘기고 201 본문(`{entry, entries}`)을 만든다. 검증이 실패하면
저장소를 부르지 않는다. 삭제는 없는 `id`도 저장소에 맡기고 남은 목록을 돌려준다.
"""

from __future__ import annotations

import datetime as dt
import json
from dataclasses import dataclass, field

import pytest

from src.api.errors import InvalidComparison
from src.api.services import saved_comparison as service
from src.repository.saved_comparison import StoredComparison

CONDITION = {
    "v": 1, "asset": "stock", "method": "lump_sum", "frequency": None, "start": "2020-01-02",
    "amount": "10000000", "principalCurrency": "KRW", "reinvest": True,
    "targets": [{"market": "KRX", "symbol": "005930.KS", "name": "삼성전자", "currency": "KRW"},
                {"market": "KRX", "symbol": "000660.KS", "name": "SK하이닉스", "currency": "KRW"}]}
NOW = dt.datetime(2026, 10, 8, 3, 21, 7)


@dataclass
class FakeRepository:
    rows: list[StoredComparison] = field(default_factory=list)
    calls: list[str] = field(default_factory=list)

    async def list_entries(self, session: object) -> list[StoredComparison]:
        self.calls.append("list")
        return sorted(self.rows, key=lambda r: (r.saved_at, r.id), reverse=True)

    async def add(self, session: object, *, name: str, asset: str, condition: str,
                  saved_at: dt.datetime) -> int:
        self.calls.append("add")
        new_id = len(self.rows) + 1
        self.rows.append(StoredComparison(new_id, name, asset, condition, saved_at))
        return new_id

    async def remove(self, session: object, comparison_id: int) -> None:
        self.calls.append("remove")
        self.rows = [r for r in self.rows if r.id != comparison_id]


class FakeSession:
    commits = 0

    async def commit(self) -> None:
        self.commits += 1


@pytest.fixture(autouse=True)
def clock(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(service, "utc_now", lambda: NOW)


class Test저장:
    async def test_정규화한_조건과_이름을_넘기고_201_본문을_만든다(self) -> None:
        repo, session = FakeRepository(), FakeSession()
        body = await service.save(session, repo, {"name": " 주식 2개 ", "condition": CONDITION})
        stored = repo.rows[0]
        assert (stored.name, stored.asset, stored.saved_at) == ("주식 2개", "stock", NOW)
        assert json.loads(stored.condition) == CONDITION
        assert body["entry"] == {"id": 1, "name": "주식 2개", "asset": "stock",
                                 "condition": CONDITION, "savedAt": "2026-10-08T03:21:07Z"}
        assert body["entries"] == [body["entry"]]
        assert session.commits == 1

    async def test_검증이_실패하면_저장소를_부르지_않는다(self) -> None:
        repo, session = FakeRepository(), FakeSession()
        with pytest.raises(InvalidComparison):
            await service.save(session, repo, {"name": "", "condition": CONDITION})
        with pytest.raises(InvalidComparison):
            await service.save(session, repo, {"name": "x", "condition": {**CONDITION, "v": 9}})
        with pytest.raises(InvalidComparison):
            await service.save(session, repo, ["not", "an", "object"])
        assert repo.calls == [] and session.commits == 0

    async def test_같은_조건도_새_항목이다(self) -> None:
        repo, session = FakeRepository(), FakeSession()
        await service.save(session, repo, {"name": "a", "condition": CONDITION})
        body = await service.save(session, repo, {"name": "a", "condition": CONDITION})
        assert [e["id"] for e in body["entries"]] == [2, 1]  # type: ignore[index]


class Test목록과_삭제:
    async def test_목록은_저장소_차례_그대로다(self) -> None:
        repo, session = FakeRepository(), FakeSession()
        await service.save(session, repo, {"name": "a", "condition": CONDITION})
        body = await service.list_body(session, repo)
        assert [e["name"] for e in body["entries"]] == ["a"]  # type: ignore[index]

    async def test_없는_id도_저장소에_맡기고_남은_목록을_돌려준다(self) -> None:
        repo, session = FakeRepository(), FakeSession()
        await service.save(session, repo, {"name": "a", "condition": CONDITION})
        body = await service.delete(session, repo, 999)
        assert repo.calls[-2:] == ["remove", "list"]
        assert [e["id"] for e in body["entries"]] == [1]  # type: ignore[index]
        body = await service.delete(session, repo, 1)
        assert body["entries"] == []
