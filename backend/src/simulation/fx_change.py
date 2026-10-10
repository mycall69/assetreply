"""외환 매매기준율의 등락 — 순수 함수 (014 반복 2026-10-10d — FR-031, research R14-24).

요약 칸(`/api/fx/latest`의 전일 대비 — 001 FR-013)과 일자별 표(`/api/fx/daily`의 행)가
**이 함수 하나**를 쓴다. 두 경로가 따로 계산하면 같은 두 날의 등락이 화면 두 곳에서 다른
글자가 된다. 비교할 행을 고르는 일은 부르는 쪽의 몫이다 — 요약은 잠정 값을 직전 확정 값과,
표는 바로 아래 행과 견준다.

`Decimal`만 쓴다(헌법 원칙 VI). 브라우저에는 `Decimal`이 없어 화면이 빼면 끝자리가 틀어진다.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

Direction = Literal["up", "down", "flat"]

_PERCENT_QUANTUM = Decimal("0.01")


@dataclass(frozen=True, slots=True)
class Quote:
    """비교 대상 — 그 날짜와 매매기준율."""

    date: dt.date
    rate: Decimal


@dataclass(frozen=True, slots=True)
class RateChange:
    """한 값의 비교 대상 대비 등락.

    `absolute`는 저장 정밀도 그대로다(반올림하지 않는다). `percent`는 표시용이라 소수 둘째 자리이고
    비교 대상이 0 이하면 `None`이다 — 나눌 수 없는 비율을 지어내지 않는다.
    """

    compared_to: dt.date
    absolute: Decimal
    percent: Decimal | None
    direction: Direction


def rate_change(current: Decimal, previous: Quote | None) -> RateChange | None:
    """`current`의 `previous` 대비 등락. 비교 대상이 없으면(저장된 첫 고시) `None`이다.

    반올림은 `Decimal.quantize`의 기본(짝수 쪽)이다 — 014 전 `/api/fx/latest`가 쓰던
    그대로라 그 응답이 바뀌지 않는다.
    """
    if previous is None:
        return None
    delta = current - previous.rate
    percent = (
        (delta / previous.rate * Decimal(100)).quantize(_PERCENT_QUANTUM)
        if previous.rate > 0
        else None
    )
    direction: Direction = "up" if delta > 0 else "down" if delta < 0 else "flat"
    return RateChange(
        compared_to=previous.date, absolute=delta, percent=percent, direction=direction)
