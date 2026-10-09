"""지표 이력의 휴장·결측 판정 (014 T052) — FR-014, SC-005, research R14-5.

**순수 함수 모듈이다**(헌법 원칙 IV). 출처가 휴장일 달력을 주지 않아(실측) 커버리지 안의 빈 평일을
이렇게 가른다:

| 조건 | 판정 |
|------|------|
| 주말 | 휴장 |
| 같은 시장 묶음의 다른 지표가 그 날 값이 있음(두 커버리지가 겹치는 구간에서만) | **결측** |
| 이웃 두 값 사이가 14일 초과 | 그 사이 평일 **결측** |
| 그 밖의 평일 | 휴장 |

같은 시장의 다른 지표는 같은 거래소 달력을 따른다 — 한쪽만 비면 출처 결측이다. 14일은 가장 긴
연휴(중국 국경절·춘절 — 주말 포함
9~10일)보다 길다. 결측은 그래프의 선을 끊고, 휴장은 잇는다 — 메우지 않는다(헌법 원칙 V).
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Collection, Sequence
from dataclasses import dataclass
from typing import Final

_SATURDAY: Final = 5
_DAY: Final = dt.timedelta(days=1)
#: 이웃 두 값 사이가 이 일수를 넘으면 그 사이 평일은 결측이다.
LONG_GAP_DAYS: Final = 14

Range = tuple[dt.date, dt.date]


@dataclass(frozen=True, slots=True)
class Sibling:
    """같은 시장 묶음의 다른 지표 — 값이 있는 날과 커버리지."""

    dates: frozenset[dt.date]
    covered: Range | None


def _weekdays_between(start: dt.date, end: dt.date) -> list[dt.date]:
    out: list[dt.date] = []
    day = start
    while day <= end:
        if day.weekday() < _SATURDAY:
            out.append(day)
        day += _DAY
    return out


def _within(day: dt.date, covered: Range | None) -> bool:
    return covered is not None and covered[0] <= day <= covered[1]


def _merge(days: Sequence[dt.date]) -> list[Range]:
    """결측 날짜를 구간으로 합친다 — 주말만 사이에 둔 날은 한 구간이다."""
    runs: list[Range] = []
    for day in sorted(days):
        if runs:
            start, end = runs[-1]
            between = _weekdays_between(end + _DAY, day - _DAY)
            if not between:
                runs[-1] = (start, day)
                continue
        runs.append((day, day))
    return runs


def missing_ranges(
    own_dates: Collection[dt.date],
    *,
    covered: Range | None,
    siblings: Sequence[Sibling],
    long_gap_days: int = LONG_GAP_DAYS,
) -> list[Range]:
    """커버리지 안의 결측 구간(처음, 끝). 휴장은 넣지 않는다."""
    if covered is None:
        return []
    present = set(own_dates)
    missing: set[dt.date] = set()
    for day in _weekdays_between(*covered):
        if day in present:
            continue
        if any(day in s.dates and _within(day, s.covered) for s in siblings):
            missing.add(day)
    ordered = sorted(d for d in present if _within(d, covered))
    for previous, following in zip(ordered, ordered[1:], strict=False):
        if (following - previous).days > long_gap_days:
            missing.update(_weekdays_between(previous + _DAY, following - _DAY))
    return _merge(sorted(missing))
