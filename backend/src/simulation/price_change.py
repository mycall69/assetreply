"""투자 성과표의 가격 등락 — 순수 함수 (014 반복 2026-10-13b — FR-048, data-model 19.3, research
R14-38).

주식·가상자산 일자별 표의 행마다 가격(주식 시작가·종가, 가상자산 시가)의 직전 기간 대표값 대비
등락이다. 등락은 외환 표·요약 칸과 **같은 함수**(`fx_change.rate_change`)라 같은 반올림이다 — 비교할
날짜를 고르는 일은 부르는 쪽(`period_table.previous_representative`)의 몫이다.

주식 표는 원주가다. 비교 날짜 뒤 ~ 행 날짜에 효력이 생긴 분할·병합이 있으면 **비교 가격을 그 누적
비율로 맞춘다** — 원주가 그대로면 1:4 분할 날이 −75%로 보인다. 비율·반올림은 010
`split_adjust.split_restated_close`와 같다. 배당은 맞추지 않는다(010 차트와 같은 원칙).

`Decimal`만 쓴다(헌법 원칙 VI).
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterable
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from math import gcd

from src.simulation.fx_change import Direction, Quote, rate_change
from src.simulation.reinvest import SplitOn
from src.simulation.split_adjust import PRICE_QUANTUM


@dataclass(frozen=True, slots=True)
class PriceChange:
    """한 가격의 비교 날짜 대비 등락. `split_ratio`는 비교 가격을 맞춘 누적 비율(`"분자:분모"`)이고
    맞추지 않았으면 `None`이다."""

    compared_to: dt.date
    absolute: Decimal
    percent: Decimal | None
    direction: Direction
    split_ratio: str | None


def _ratio(splits: Iterable[SplitOn], after: dt.date, upto: dt.date) -> tuple[int, int]:
    """효력일이 (`after`, `upto`]인 분할·병합의 누적 비율(약분)."""
    numerator = denominator = 1
    for split in splits:
        if after < split.date <= upto:
            numerator *= split.numerator
            denominator *= split.denominator
    common = gcd(numerator, denominator)
    return numerator // common, denominator // common


def price_change(current: Decimal | None, previous: Decimal | None, *, compared_to: dt.date,
                 day: dt.date, splits: Iterable[SplitOn] = ()) -> PriceChange | None:
    """`day`의 `current`와 `compared_to`의 `previous`를 견준다. 가격 하나라도 없으면 `None`이다.

    효력일이 비교 날짜 당일이면 비교 가격이 이미 분할 뒤라 맞추지 않고, 행 날짜 당일이면 그 날
    가격이 분할 뒤라 맞춘다.
    """
    if current is None or previous is None:
        return None
    numerator, denominator = _ratio(splits, compared_to, day)
    adjusted = numerator != denominator
    base = ((previous * denominator / numerator).quantize(PRICE_QUANTUM, rounding=ROUND_HALF_UP)
            if adjusted else previous)
    change = rate_change(current, Quote(compared_to, base))
    assert change is not None  # 비교 대상을 넘겼다
    return PriceChange(compared_to=change.compared_to, absolute=change.absolute,
                       percent=change.percent, direction=change.direction,
                       split_ratio=f"{numerator}:{denominator}" if adjusted else None)
