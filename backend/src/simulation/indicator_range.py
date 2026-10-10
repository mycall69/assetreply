"""지표 모달의 보는 기간 8개 (014 반복 2026-10-10b) — FR-011, data-model §5.

**순수 함수 모듈이다**(헌법 원칙 IV). 기간은 보는 범위이고 점을 묶지 않는다(명확화 2026-10-10 —
명확화 1 대체): 일(`1d`)·주(`5d`)는 장중, 월(`1m`)·1년·5년·10년·20년은 그 기간의 일봉 전부,
모두(`all`)는 저장된 일봉 전부다.

시작일은 그 시장 현지의 오늘에서 1개월·n년 전 같은 날이다. 그 날이 없으면 그 달 말일이다(011
`months_later`와 같은 규칙 — 말일·2월 29일).
"""

from __future__ import annotations

import datetime as dt
from typing import Final, Literal

from src.simulation.contribution_schedule import months_later

RangeKey = Literal["1d", "5d", "1m", "1y", "5y", "10y", "20y", "all"]
RANGES: Final[tuple[RangeKey, ...]] = ("1d", "5d", "1m", "1y", "5y", "10y", "20y", "all")
#: 처음 기간(D1) — 틀리거나 없는 질의도 이것이다(400을 내지 않는다 — 옛 `unit` 주소가 오류가 되지
#: 않는다)
DEFAULT_RANGE: Final[RangeKey] = "1y"
_MONTHS: Final[dict[str, int]] = {"1m": 1, "1y": 12, "5y": 60, "10y": 120, "20y": 240}


def range_of(raw: str | None) -> RangeKey:
    for key in RANGES:
        if raw == key:
            return key
    return DEFAULT_RANGE


def is_intraday(key: RangeKey) -> bool:
    """일·주는 장중 시세다(spec FR-028) — 이력 수집과 무관하다."""
    return key in ("1d", "5d")


def range_start(today: dt.date, key: RangeKey) -> dt.date | None:
    """일봉 기간의 시작일(포함). 모두·장중은 `None`이다."""
    months = _MONTHS.get(key)
    return None if months is None else months_later(today, -months)
