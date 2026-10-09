"""휴장·결측 판정 (014 T043) — FR-014, SC-005, research R14-5.

출처가 휴장일 달력을 주지 않는다. 커버리지 안의 빈 평일을 이렇게 가른다:

- 같은 시장 묶음의 다른 지표가 그 날 값이 있으면 **결측**(선을 끊는다)
- 이웃 두 값 사이가 14일을 넘으면 그 사이 평일은 **결측**
- 그 밖의 평일 빈 날과 주말은 **휴장**(점 없음, 선은 이어진다)

결측을 휴장으로 이어 그리면 그 기간에 값이 움직이지 않은 것처럼 보인다(FR-014 실패 양상).
"""

from __future__ import annotations

import datetime as dt

from src.simulation.market_gaps import Sibling, missing_ranges

D = dt.date


def weekdays(start: dt.date, end: dt.date, *, skip: tuple[dt.date, ...] = ()) -> list[dt.date]:
    out = []
    day = start
    while day <= end:
        if day.weekday() < 5 and day not in skip:
            out.append(day)
        day += dt.timedelta(days=1)
    return out


OCT = (D(2026, 10, 1), D(2026, 10, 30))


def test_묶음의_다른_지표만_값이_있으면_결측() -> None:
    gap = D(2026, 10, 14)
    own = weekdays(*OCT, skip=(gap,))
    sibling = Sibling(dates=frozenset(weekdays(*OCT)), covered=OCT)
    assert missing_ranges(own, covered=OCT, siblings=[sibling]) == [(gap, gap)]


def test_묶음이_모두_비면_휴장() -> None:
    holiday = D(2026, 10, 12)
    own = weekdays(*OCT, skip=(holiday,))
    sibling = Sibling(dates=frozenset(weekdays(*OCT, skip=(holiday,))), covered=OCT)
    assert missing_ranges(own, covered=OCT, siblings=[sibling]) == []


def test_묶음_판정은_두_커버리지가_겹치는_구간만() -> None:
    """SOX는 1994년부터다 — 그 전의 다우와 견주지 않는다."""
    dow_cov = (D(1992, 1, 2), D(1994, 6, 30))
    sox_cov = (D(1994, 5, 4), D(1994, 6, 30))
    dow = weekdays(*dow_cov)
    sox = weekdays(*sox_cov)
    assert missing_ranges(dow, covered=dow_cov, siblings=[Sibling(frozenset(sox), sox_cov)]) == []
    assert missing_ranges(sox, covered=sox_cov, siblings=[Sibling(frozenset(dow), dow_cov)]) == []


def test_상해_국경절은_휴장이고_15일_공백은_결측() -> None:
    cov = (D(2026, 9, 1), D(2026, 11, 30))
    golden_week = tuple(weekdays(D(2026, 10, 1), D(2026, 10, 8)))
    own = weekdays(*cov, skip=golden_week)
    assert missing_ranges(own, covered=cov, siblings=[]) == []
    outage = tuple(weekdays(D(2026, 11, 2), D(2026, 11, 13)))  # 금 10-30 → 월 11-16, 17일 공백
    own = weekdays(*cov, skip=outage)
    assert missing_ranges(own, covered=cov, siblings=[]) == [(D(2026, 11, 2), D(2026, 11, 13))]


def test_주말은_늘_휴장() -> None:
    own = weekdays(*OCT)
    sibling = Sibling(dates=frozenset({D(2026, 10, 10)}), covered=OCT)  # 토요일 값이 있어도
    assert missing_ranges(own, covered=OCT, siblings=[sibling]) == []


def test_커버리지_밖은_판정하지_않는다() -> None:
    cov = (D(2026, 10, 10), D(2026, 10, 30))
    own = weekdays(*cov)
    sibling = Sibling(dates=frozenset(weekdays(*OCT)), covered=OCT)
    assert missing_ranges(own, covered=cov, siblings=[sibling]) == []
    assert missing_ranges([], covered=None, siblings=[sibling]) == []


def test_연속한_결측은_주말을_건너_한_구간으로_합친다() -> None:
    gaps = (D(2026, 10, 15), D(2026, 10, 16), D(2026, 10, 19))  # 목·금·월
    own = weekdays(*OCT, skip=gaps)
    sibling = Sibling(dates=frozenset(weekdays(*OCT)), covered=OCT)
    assert missing_ranges(own, covered=OCT, siblings=[sibling]) == [
        (D(2026, 10, 15), D(2026, 10, 19))
    ]
