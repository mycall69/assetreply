"""지표 그래프의 일·주·월·년 대표값 (014 T053) — FR-011~FR-013, SC-005, research R14-12, data-model
5.

**순수 함수 모듈이다**(헌법 원칙 IV). 단위는 **점 하나가 나타내는 기간**이다(명확화 1).

- 주·월은 012 `period_table`의 구간(`period_bounds` — 월~일 주, 달력 월)과 기준일(`anchor_of` —
  금요일·말일)을 **그대로** 부르고,
  같은 대표일 규칙(주 = 금요일 이하 마지막 거래일, 월 = 말일 이하 마지막 거래일)을 쓴다 — 화면마다
  규칙이 다르면 같은 달이 다른
  값으로 보인다(FR-013 실패 양상)
- 년은 여기서 더한다 — 12-31 이하 마지막 거래일
- 대표일이 기간 끝과 다르면 `shifted`(📅), 기간 끝이 현지 오늘 뒤면 `ongoing`(⏳ 끝나지 않은 구간)
- 거래일이 없는 기간은 점이 없다 — 앞 기간의 값을 끌어오지 않는다(헌법 원칙 V)

`period_table.PeriodUnit`은 고치지 않는다 — 주식·가상자산 표 경로의 단위 검증이 그대로다.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Collection, Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Final, Literal, get_args

from src.simulation.period_table import anchor_of, period_bounds

Unit = Literal["daily", "weekly", "monthly", "yearly"]
UNITS: Final[tuple[str, ...]] = get_args(Unit)


@dataclass(frozen=True, slots=True)
class PeriodPoint:
    date: dt.date
    value: Decimal
    shifted: bool = False
    ongoing: bool = False
    provisional: bool = False


def _bounds(day: dt.date, unit: Unit) -> tuple[dt.date, dt.date]:
    if unit == "yearly":
        return dt.date(day.year, 1, 1), dt.date(day.year, 12, 31)
    if unit == "weekly":
        return period_bounds(day, "weekly")
    return period_bounds(day, "monthly")


def _anchor(day: dt.date, unit: Unit) -> dt.date:
    if unit == "yearly":
        return dt.date(day.year, 12, 31)
    return anchor_of(day, "weekly" if unit == "weekly" else "monthly")


def _representative(group: Sequence[dt.date], unit: Unit) -> dt.date:
    """012 `period_table`과 같은 규칙 — 주는 금요일 이하의 마지막, 없으면 마지막. 월·년은 마지막."""
    if unit == "weekly":
        friday = _anchor(group[0], unit)
        upto = [day for day in group if day <= friday]
        return upto[-1] if upto else group[-1]
    return group[-1]


def build_points(
    closes: Sequence[tuple[dt.date, Decimal]],
    unit: Unit,
    *,
    today: dt.date,
    provisional_dates: Collection[dt.date] = (),
) -> list[PeriodPoint]:
    """단위의 점을 날짜 차례로. `today`는 그 시장의 현지 오늘이다(끝나지 않은 기간 판정)."""
    provisional = set(provisional_dates)
    values = dict(closes)
    days = sorted(values)
    if unit == "daily":
        return [PeriodPoint(day, values[day], provisional=day in provisional) for day in days]
    groups: dict[tuple[dt.date, dt.date], list[dt.date]] = {}
    for day in days:
        groups.setdefault(_bounds(day, unit), []).append(day)
    points: list[PeriodPoint] = []
    for (_, period_to), group in sorted(groups.items()):
        rep = _representative(group, unit)
        points.append(
            PeriodPoint(
                rep,
                values[rep],
                shifted=rep != _anchor(rep, unit),
                ongoing=period_to > today,
                provisional=rep in provisional,
            )
        )
    return points
