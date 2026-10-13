"""투자 비교 설정 — 검증·본문 (014 반복 2026-10-13 T216) — spec FR-044, contracts A18, data-model
18.

최대 대상 수는 **JSON 정수 2~100**이고 기본은 20이다(행이 없으면 20). 화면의 **더하기 한도**다 —
비교 조건 검증의 끝(100)은 `comparison_conditions.MAX_TARGETS`이고 설정 값이 아니다(FR-045 — 설정을
낮춰도 저장한 비교를 다시 저장할 수 있다). 설정의 위 끝은 그 상수를 그대로 쓴다 — 둘이 어긋나면
설정한 수만큼 더한 비교를 저장할 수 없다.

틀린 값은 **저장하지 않고** 알린다(`InvalidSetting` → 422) — 기본값이나 가까운 값으로 바꾸면
사용자가 친 값과 다른 한도가 걸린다. 불리언은 Python에서 `int`의 하위형이라 따로 막는다(`true` → 1).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Final

from sqlalchemy.ext.asyncio import AsyncSession

from src.api.errors import InvalidSetting
from src.api.services.comparison_conditions import MAX_TARGETS, MIN_TARGETS
from src.repository import comparison_setting as repo

MIN_SETTING: Final = MIN_TARGETS
MAX_SETTING: Final = MAX_TARGETS
DEFAULT_SETTING: Final = 20

Json = dict[str, object]


def _invalid(value: object) -> InvalidSetting:
    return InvalidSetting(
        f"최대 대상 수는 {MIN_SETTING}~{MAX_SETTING} 사이의 정수여야 합니다: {value}")


def parse_max_targets(payload: object) -> int:
    """`{"maxTargets": <정수>}`에서 값을 읽는다. 칸이 없거나 범위 밖·정수가 아니면
    `InvalidSetting`."""
    if not isinstance(payload, Mapping) or "maxTargets" not in payload:
        raise _invalid("없습니다")
    value = payload["maxTargets"]
    if isinstance(value, bool) or not isinstance(value, int):
        raise _invalid(repr(value))
    if not MIN_SETTING <= value <= MAX_SETTING:
        raise _invalid(value)
    return value


def settings_body(stored: int | None) -> Json:
    """응답 본문(contracts A18) — 저장된 값(없으면 기본)과 화면이 범위·안내를 그릴 상수 셋."""
    return {
        "maxTargets": DEFAULT_SETTING if stored is None else stored,
        "defaultMaxTargets": DEFAULT_SETTING,
        "minTargets": MIN_SETTING,
        "limitTargets": MAX_SETTING,
    }


async def read(session: AsyncSession) -> Json:
    body = settings_body(await repo.get_max_targets(session))
    await session.commit()
    return body


async def update(session: AsyncSession, payload: object) -> Json:
    """검증해 저장하고 다시 읽은 값을 돌려준다. 틀리면 저장소를 부르지 않는다."""
    value = parse_max_targets(payload)
    await repo.save_max_targets(session, value)
    await session.commit()
    return settings_body(await repo.get_max_targets(session))
