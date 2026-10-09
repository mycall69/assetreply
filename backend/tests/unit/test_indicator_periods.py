"""그래프의 일·주·월·년 대표값 (014 T044) — FR-011~FR-013, SC-005, research R14-12, data-model 5.

주·월은 012 `period_table`의 기준일 규칙을 **그대로** 따른다(주 = 금요일 이하의 마지막 거래일, 월 =
말일 이하의 마지막 거래일) —
화면마다 규칙이 다르면 같은 달이 다른 값으로 보인다(FR-013 실패 양상). 년은 12-31 이하의 마지막
거래일이다.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

from src.simulation.indicator_periods import UNITS, build_points
from src.simulation.period_table import build_table

D = dt.date


def closes(days: list[dt.date]) -> list[tuple[dt.date, Decimal]]:
    return [(day, Decimal(i + 1)) for i, day in enumerate(days)]


def trading_days(start: dt.date, end: dt.date, *, skip: tuple[dt.date, ...] = ()) -> list[dt.date]:
    out = []
    day = start
    while day <= end:
        if day.weekday() < 5 and day not in skip:
            out.append(day)
        day += dt.timedelta(days=1)
    return out


DAYS = trading_days(D(2025, 1, 2), D(2026, 10, 8), skip=(D(2026, 10, 2), D(2026, 9, 30)))
TODAY = D(2026, 10, 9)


def test_단위는_넷() -> None:
    assert UNITS == ("daily", "weekly", "monthly", "yearly")


def test_일_단위는_그날마다() -> None:
    points = build_points(closes(DAYS), "daily", today=TODAY)
    assert [p.date for p in points] == DAYS
    assert not any(p.shifted or p.ongoing for p in points)


def test_주_월_대표일은_012_period_table과_같다() -> None:
    for unit in ("weekly", "monthly"):
        expected = sorted(e.date for e in build_table(DAYS, (), unit, TODAY))
        points = build_points(closes(DAYS), unit, today=TODAY)
        assert [p.date for p in points] == expected, unit


def test_금요일_휴장이면_목요일이_대표이고_옮김() -> None:
    points = {p.date: p for p in build_points(closes(DAYS), "weekly", today=TODAY)}
    assert D(2026, 10, 1) in points and points[D(2026, 10, 1)].shifted  # 10-02(금) 휴장
    assert D(2026, 9, 25) in points and not points[D(2026, 9, 25)].shifted


def test_월말_휴장이면_전날이_대표이고_옮김() -> None:
    points = {p.date: p for p in build_points(closes(DAYS), "monthly", today=TODAY)}
    assert D(2026, 9, 29) in points and points[D(2026, 9, 29)].shifted  # 09-30 휴장
    assert D(2025, 12, 31) in points and not points[D(2025, 12, 31)].shifted


def test_년_대표는_12월_31일_이하의_마지막_거래일() -> None:
    points = build_points(closes(DAYS), "yearly", today=TODAY)
    assert [p.date for p in points] == [D(2025, 12, 31), D(2026, 10, 8)]
    assert not points[0].shifted and not points[0].ongoing
    assert points[1].ongoing and points[1].shifted


def test_끝나지_않은_기간은_ongoing() -> None:
    weekly = build_points(closes(DAYS), "weekly", today=TODAY)
    monthly = build_points(closes(DAYS), "monthly", today=TODAY)
    assert weekly[-1].date == D(2026, 10, 8) and weekly[-1].ongoing
    assert monthly[-1].date == D(2026, 10, 8) and monthly[-1].ongoing
    assert not weekly[-2].ongoing


def test_잠정_꼬리() -> None:
    tail = D(2026, 10, 9)
    data = [*closes(DAYS), (tail, Decimal("999"))]
    daily = build_points(data, "daily", today=TODAY, provisional_dates={tail})
    assert daily[-1].date == tail and daily[-1].provisional and not daily[-2].provisional
    weekly = build_points(data, "weekly", today=TODAY, provisional_dates={tail})
    assert weekly[-1].date == tail and weekly[-1].provisional and weekly[-1].ongoing
    assert weekly[-1].value == Decimal("999")


def test_거래일이_없는_기간은_점이_없다() -> None:
    days = trading_days(
        D(2026, 9, 1), D(2026, 10, 30), skip=tuple(trading_days(D(2026, 10, 5), D(2026, 10, 9)))
    )
    points = build_points(closes(days), "weekly", today=D(2026, 11, 1))
    assert all(not (D(2026, 10, 5) <= p.date <= D(2026, 10, 11)) for p in points)


def test_값은_그_날의_종가다() -> None:
    data = closes(DAYS)
    by_day = dict(data)
    for unit in UNITS:
        for p in build_points(data, unit, today=TODAY):
            assert p.value == by_day[p.date], unit
