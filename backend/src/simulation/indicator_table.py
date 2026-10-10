"""지표 모달의 일자별 표 값 (014 반복 2026-10-10b) — FR-013, FR-029, SC-012, research R14-21,
data-model §5a.

**순수 함수 모듈이다**(헌법 원칙 IV). 기준일은 012 `period_table`의 규칙을 그대로 쓴다(주 = 금요일
이하의 마지막 거래일, 없으면 마지막 · 월 = 말일 이하의 마지막 거래일) — 값의 열쇠가
`period_table.build_table`이 고르는 대표일과 같아야 표의 행과 값이 맞는다.

- 일 행: 그 날의 시가·고가·저가·종가, 대비 = 직전 거래일 종가와의 차이
- 주·월 행: 시가 = 그 기간 **첫 거래일의** 시가(비었으면 비운다 — 다음 날 시가로 메우지 않는다, 원칙
  V), 고가·저가 = 기간의 최댓값·최솟값(값이 있는 날만), 종가 = 대표일 종가, 대비 = 앞 기간 대표
  종가와의 차이
- 앞 행이 없으면 대비를 비운다. 앞 종가가 0 이하면 등락률을 비운다(음수 가격 — spec Edge Cases)
- 잠정 날(오늘 현재 시세·외환 잠정 고시)이 든 행은 잠정이다
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Collection, Sequence
from dataclasses import dataclass
from decimal import Decimal

from src.simulation.money import quantize_rate
from src.simulation.period_table import PeriodUnit, anchor_of, period_bounds


@dataclass(frozen=True, slots=True)
class TableBar:
    date: dt.date
    open: Decimal | None
    high: Decimal | None
    low: Decimal | None
    close: Decimal


@dataclass(frozen=True, slots=True)
class TableValue:
    open: Decimal | None
    high: Decimal | None
    low: Decimal | None
    close: Decimal
    change: Decimal | None
    change_rate: Decimal | None
    provisional: bool


def _representative(group: Sequence[TableBar], unit: PeriodUnit) -> TableBar:
    if unit == "weekly":
        friday = anchor_of(group[0].date, unit)
        upto = [b for b in group if b.date <= friday]
        return upto[-1] if upto else group[-1]
    return group[-1]


def _extreme(values: Sequence[Decimal | None], pick: str) -> Decimal | None:
    present = [v for v in values if v is not None]
    if not present:
        return None
    return max(present) if pick == "max" else min(present)


def table_values(
    bars: Sequence[TableBar], unit: PeriodUnit, *, provisional: Collection[dt.date]
) -> dict[dt.date, TableValue]:
    """대표일 → 그 행의 값. `bars`는 날짜 차례다."""
    groups: list[list[TableBar]] = []
    if unit == "daily":
        groups = [[b] for b in bars]
    else:
        keyed: dict[tuple[dt.date, dt.date], list[TableBar]] = {}
        for b in bars:
            keyed.setdefault(period_bounds(b.date, unit), []).append(b)
        groups = [keyed[k] for k in sorted(keyed)]
    out: dict[dt.date, TableValue] = {}
    previous: Decimal | None = None
    for group in groups:
        rep = _representative(group, unit)
        change = None if previous is None else rep.close - previous
        rate = (
            quantize_rate(change / previous)
            if change is not None and previous is not None and previous > 0
            else None
        )
        out[rep.date] = TableValue(
            open=group[0].open,
            high=_extreme([b.high for b in group], "max"),
            low=_extreme([b.low for b in group], "min"),
            close=rep.close,
            change=change,
            change_rate=rate,
            provisional=any(b.date in provisional for b in group),
        )
        previous = rep.close
    return out
