"""시뮬레이션 이력 — 목록·저장·삭제·옮기기·보관 기간 (012 T053) — FR-011~FR-014, research
R12-10·R12-11, contracts/rest-api.md 2~6.

**기한이 지난 항목을 읽고 쓸 때마다 먼저 지운다**(목록·저장·삭제·옮기기는 그 자산군, 보관 기간
저장은 모든 자산군). 기간을 줄인 뒤 다음 날까지 남는 일
(FR-012 *늦게 일어남*)을 배경 태스크 없이 막는다 — 조회가 쓰기를 하는 유일한 경우다. 보관 기간은
**보관 기준 시각**(마지막 실행 — 옮긴 항목은 옮긴
시각)으로 잰다. 처음 저장 시각으로 재면 다시 실행한 항목이, 브라우저의 원래 시각으로 재면 옮긴
항목이 곧바로 지워진다(*다른 곳에서 일어남*).

지금 시각은 `utc_now()`로 얻는다 — 테스트는 이것을 바꾼다(가상자산 `utc_yesterday`와 같은 방식).
시각은 UTC(시간대 없는 값)로 저장하고 응답은 `Z`를
붙인 ISO 시각이다.
"""

from __future__ import annotations

import datetime as dt
import json
from collections.abc import Mapping
from typing import Final

from sqlalchemy.ext.asyncio import AsyncSession

from src.api.errors import InvalidHistory, InvalidQuery, InvalidSetting
from src.api.services.history_conditions import AssetClass, validate
from src.repository import simulation_history as repo
from src.repository.history_setting import DEFAULT_RETENTION, get_retention, save_retention
from src.repository.simulation_history import StoredHistory

Json = dict[str, object]

#: 보관 기간 → 일 수. 무기한은 `None`이다.
RETENTION_DAYS: Final[dict[str, int | None]] = {
    "days_7": 7,
    "days_30": 30,
    "days_90": 90,
    "days_180": 180,
    "days_365": 365,
    "unlimited": None,
}
OPTIONS: Final[list[int | None]] = [7, 30, 90, 180, 365, None]


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.UTC).replace(tzinfo=None)


def _iso(value: dt.datetime) -> str:
    return value.strftime("%Y-%m-%dT%H:%M:%SZ")


def _saved_at(raw: object) -> dt.datetime | None:
    """브라우저 옛 항목의 `savedAt`(마지막 실행 시각). 없거나 읽을 수 없으면 `None` — 그때는 옮긴
    시각을 쓴다(항목은 건너뛰지 않는다)."""
    value = raw.get("savedAt") if isinstance(raw, dict) else None
    if not isinstance(value, str):
        return None
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed
    return parsed.astimezone(dt.UTC).replace(tzinfo=None)


async def _days(session: AsyncSession) -> int | None:
    return RETENTION_DAYS[await get_retention(session)]


async def _purge(session: AsyncSession, asset: AssetClass | None) -> int | None:
    days = await _days(session)
    if days is not None:
        await repo.purge(session, utc_now() - dt.timedelta(days=days), asset)
    return days


async def _body(session: AsyncSession, asset: AssetClass) -> Json:
    days = await _purge(session, asset)
    entries = await repo.list_entries(session, asset)
    return {
        "entries": [
            {**json.loads(e.condition), "id": e.key, "lastRunAt": _iso(e.last_run_at)}
            for e in entries
        ],
        "retentionDays": days,
    }


async def list_history(session: AsyncSession, asset: AssetClass) -> Json:
    body = await _body(session, asset)
    await session.commit()
    return body


async def put_history(
    session: AsyncSession, asset: AssetClass, payload: Mapping[str, object]
) -> Json:
    """실행한 조건을 저장한다. 같은 조건이면 마지막 실행·보관 기준 시각을 지금으로 바꾼다(맨 앞으로
    온다)."""
    if "condition" not in payload:
        raise InvalidHistory("condition: 없습니다")
    condition = validate(asset, payload["condition"])
    now = utc_now()
    await repo.save(session, asset, [StoredHistory(condition.key, condition.text, now, now)])
    body = await _body(session, asset)
    await session.commit()
    return body


async def delete_history(session: AsyncSession, asset: AssetClass, key: str | None) -> Json:
    """항목을 지운다. 없는 식별자도 지운 것으로 본다(멱등)."""
    if key is None or key == "":
        raise InvalidQuery("id가 필요합니다")
    await repo.remove(session, asset, key)
    body = await _body(session, asset)
    await session.commit()
    return body


def _later(a: StoredHistory, b: StoredHistory) -> StoredHistory:
    """같은 조건 둘을 합친다 — 마지막 실행·보관 기준 시각은 각각 늦은 쪽, 조건 글은 마지막 실행이
    늦은 쪽의 것."""
    newer = a if a.last_run_at >= b.last_run_at else b
    return StoredHistory(
        a.key, newer.condition, max(a.last_run_at, b.last_run_at), max(a.retain_from, b.retain_from)
    )


async def import_history(
    session: AsyncSession, asset: AssetClass, payload: Mapping[str, object]
) -> Json:
    """브라우저 옛 이력을 옮긴다(FR-013). 마지막 실행이 보관 기간보다 오래된 항목도 **모두 옮기고**
    보관 기준 시각은 옮긴 시각이다(명확화 4).
    읽을 수 없는 항목은 건너뛰고 수를 돌려준다 — 화면이 알린다(조용히 버리지 않는다)."""
    entries = payload.get("entries")
    if not isinstance(entries, list):
        raise InvalidQuery("entries: 배열이어야 합니다")
    now = utc_now()
    batch: dict[str, StoredHistory] = {}
    merged = skipped = 0
    for raw in entries:
        try:
            condition = validate(asset, raw)
        except InvalidHistory:
            skipped += 1
            continue
        item = StoredHistory(condition.key, condition.text, _saved_at(raw) or now, now)
        if condition.key in batch:
            merged += 1
            item = _later(batch[condition.key], item)
        batch[condition.key] = item
    existing = await repo.find(session, asset, list(batch))
    imported = 0
    final: list[StoredHistory] = []
    for key, item in batch.items():
        old = existing.get(key)
        if old is None:
            imported += 1
            final.append(item)
        else:
            merged += 1
            final.append(_later(old, item))
    await repo.save(session, asset, final)
    body = await _body(session, asset)
    await session.commit()
    return {"imported": imported, "merged": merged, "skipped": skipped, **body}


async def retention_body(session: AsyncSession) -> Json:
    retention = await get_retention(session)
    return {
        "retentionDays": RETENTION_DAYS[retention],
        "isDefault": retention == DEFAULT_RETENTION,
        "options": OPTIONS,
    }


def _parse_retention(payload: Mapping[str, object]) -> str:
    """선택지 밖이면 막는다 — 기본값으로 바꾸지 않는다(사용자가 고른 것과 다른 기간으로
    지워진다)."""
    if "retentionDays" not in payload:
        raise InvalidSetting("retentionDays: 없습니다 — 7 · 30 · 90 · 180 · 365 · null(무기한)")
    value = payload["retentionDays"]
    if value is None:
        return "unlimited"
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or value not in RETENTION_DAYS.values()
    ):
        raise InvalidSetting(
            f"retentionDays: 7 · 30 · 90 · 180 · 365 · null(무기한) 중 하나여야 합니다: {value!r}"
        )
    return f"days_{value}"


async def put_retention(session: AsyncSession, payload: Mapping[str, object]) -> Json:
    """보관 기간을 저장하고 **곧바로** 모든 자산군의 기한 지난 항목을 지운다(FR-012). 다시 늘려도
    지운 항목은 돌아오지 않는다."""
    await save_retention(session, _parse_retention(payload))
    await _purge(session, None)
    body = await retention_body(session)
    await session.commit()
    return body
