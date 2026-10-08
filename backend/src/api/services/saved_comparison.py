"""저장한 비교 — 목록·저장·삭제 (013 T072) — FR-016~FR-018, contracts/rest-api.md 2~4.

저장소는 `SavedComparisonRepository` Protocol로 받는다(헌법 원칙 IV) — 경로가
`src.repository.saved_comparison` 모듈을 넘기고, 단위 테스트는 메모리 안 가짜를 넘긴다. **보관
기간이 없다** — 012 이력과 달리 읽고 쓸 때 지우는 일이 없다(명확화 3). 저장할 때마다 새 항목이다.

지금 시각은 `utc_now()`로 얻는다 — 테스트는 이것을 바꾼다. 저장 시각은 초 단위로 자른다 — DB
`DATETIME`이 소수 초를 반올림해, 응답의 `entry`와 목록의 같은 항목이 1초 다를 수 있다. 응답 시각은
`Z`를 붙인 ISO 시각이다.
"""

from __future__ import annotations

import datetime as dt
import json
from collections.abc import Mapping
from typing import Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from src.api.errors import InvalidComparison
from src.api.services.comparison_conditions import validate_condition, validate_name
from src.repository.saved_comparison import StoredComparison

Json = dict[str, object]


class SavedComparisonRepository(Protocol):
    async def list_entries(self, session: AsyncSession) -> list[StoredComparison]: ...

    async def add(
        self, session: AsyncSession, *, name: str, asset: str, condition: str,
        saved_at: dt.datetime,
    ) -> int: ...

    async def remove(self, session: AsyncSession, comparison_id: int) -> None: ...


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.UTC).replace(tzinfo=None)


def _iso(value: dt.datetime) -> str:
    return value.strftime("%Y-%m-%dT%H:%M:%SZ")


def _entry(row: StoredComparison) -> Json:
    return {
        "id": row.id,
        "name": row.name,
        "asset": row.asset,
        "condition": json.loads(row.condition),
        "savedAt": _iso(row.saved_at),
    }


async def _entries(session: AsyncSession, repo: SavedComparisonRepository) -> list[Json]:
    return [_entry(r) for r in await repo.list_entries(session)]


async def list_body(session: AsyncSession, repo: SavedComparisonRepository) -> Json:
    """목록 — 저장 시각 내림차순, 같은 초는 `id` 내림차순(저장소 차례 그대로)."""
    entries = await _entries(session, repo)
    await session.commit()
    return {"entries": entries}


async def save(
    session: AsyncSession, repo: SavedComparisonRepository, payload: object
) -> Json:
    """이름과 조건을 검증해 새 항목으로 저장한다 — 201 본문 `{entry, entries}`. 검증이 실패하면
    저장소를 부르지 않는다."""
    if not isinstance(payload, Mapping):
        raise InvalidComparison("본문: {name, condition} 객체여야 합니다")
    name = validate_name(payload.get("name"))
    condition = validate_condition(payload.get("condition"))
    saved_at = utc_now().replace(microsecond=0)
    new_id = await repo.add(
        session, name=name, asset=condition.asset, condition=condition.text, saved_at=saved_at)
    entries = await _entries(session, repo)
    await session.commit()
    entry = _entry(StoredComparison(new_id, name, condition.asset, condition.text, saved_at))
    return {"entry": entry, "entries": entries}


async def delete(
    session: AsyncSession, repo: SavedComparisonRepository, comparison_id: int
) -> Json:
    """항목을 지우고 남은 목록을 돌려준다. 없는 `id`도 지운 것으로 본다(멱등)."""
    await repo.remove(session, comparison_id)
    entries = await _entries(session, repo)
    await session.commit()
    return {"entries": entries}
