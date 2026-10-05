"""분할만 반영한 수정 종가 (010 반복 1, research R10-13) — 순수 함수(DB·HTTP 없음, 헌법 원칙 IV).

차트의 주가 선은 원주가를 그리면 분할 날 비율만큼 떨어져 폭락처럼 보인다. 그래서 그 날의 원주가
종가를 **그 날 뒤**에 효력이 생긴 분할 비율로 나눈다 — 분할 날에도 선이 이어지고 일반 시세 차트와
같은 모양이다. 효력일 당일 이후의 종가는 이미 분할 뒤 값이라 그 분할로 나누지 않는다. 병합(분자 <
분모)도 같은 식이다.

배당은 소급하지 않는다. 출처(Yahoo)의 수정 종가는 배당까지 소급하고 받은 시점마다 기준이 달라 쓰지
않는다. 같은 원주가·분할 기록에서 늘 같은 값이 나오고, 결과는 저장하지 않는다(원칙 V — 명시 규칙).

이 값은 **차트 표시용**이다 — 재투자 계산(`reinvest`)은 지금처럼 원주가와 분할 날 주식 수 조정만
쓴다(005 FR-011). 그래서 출처의 수정가와 이름을 가른다(`split_restated_close`) — 005의 가드
(`tests/unit/test_no_adjusted_price.py`)가 시뮬레이션 계층에서 출처 수정가의 이름을 찾는다.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterable
from decimal import ROUND_HALF_UP, Decimal

from src.simulation.reinvest import SplitOn

#: 저장된 원주가와 같은 자릿수(소수 6자리). 나누어떨어지지 않는 비율(3:2 등)만 반올림한다.
PRICE_QUANTUM = Decimal("0.000001")


def split_restated_close(close: Decimal, day: dt.date, splits: Iterable[SplitOn]) -> Decimal:
    """`close`(그 날 원주가 종가) ÷ ∏(분자 / 분모) — 곱은 효력일이 `day` 뒤인 분할 전부."""
    numerator = denominator = 1
    for split in splits:
        if split.date > day:
            numerator *= split.numerator
            denominator *= split.denominator
    return (close * denominator / numerator).quantize(PRICE_QUANTUM, rounding=ROUND_HALF_UP)
