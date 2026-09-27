"""구간 경계 계산 (T002, T003) — 004 data-model 3절.

주는 월요일~일요일, 월은 1일~말일이다 (spec Assumptions). 경계가 틀리면 기준일 판정과
선택 날짜 강조가 함께 어긋난다 — 값은 정확한데 **무엇의 값인지**가 달라진다.
"""
from __future__ import annotations

import calendar
import datetime as dt

from src.api.services.period_rows import period_bounds

MON, FRI, SUN = 0, 4, 6


def test_일_단위는_그날_하루다() -> None:
    day = dt.date(2026, 9, 23)
    assert period_bounds(day, "daily") == (day, day)


def test_주_경계는_월요일부터_일요일까지다() -> None:
    # 2026-09-23은 수요일. 그 주는 09-21(월) ~ 09-27(일)이다.
    start, end = period_bounds(dt.date(2026, 9, 23), "weekly")
    assert (start, end) == (dt.date(2026, 9, 21), dt.date(2026, 9, 27))
    assert start.weekday() == MON
    assert end.weekday() == SUN


def test_월요일과_일요일_자신도_같은_주에_든다() -> None:
    """경계일이 다음·이전 주로 새면 그 주의 행이 둘이 된다."""
    monday, sunday = dt.date(2026, 9, 21), dt.date(2026, 9, 27)
    assert period_bounds(monday, "weekly") == (monday, sunday)
    assert period_bounds(sunday, "weekly") == (monday, sunday)


def test_주_경계가_달을_넘어간다() -> None:
    """2026-09-28(월)~10-04(일). 주는 달력의 달을 따르지 않는다."""
    assert period_bounds(dt.date(2026, 10, 1), "weekly") == (
        dt.date(2026, 9, 28), dt.date(2026, 10, 4))


def test_주_경계가_해를_넘어간다() -> None:
    """2026-12-28(월)~2027-01-03(일). 연말연시에 주가 쪼개지면 안 된다."""
    for day in (dt.date(2026, 12, 31), dt.date(2027, 1, 1)):
        assert period_bounds(day, "weekly") == (
            dt.date(2026, 12, 28), dt.date(2027, 1, 3))


def test_월_경계는_1일부터_말일까지다() -> None:
    assert period_bounds(dt.date(2026, 9, 23), "monthly") == (
        dt.date(2026, 9, 1), dt.date(2026, 9, 30))


def test_윤년_2월의_말일은_29일이다() -> None:
    assert period_bounds(dt.date(2028, 2, 10), "monthly") == (
        dt.date(2028, 2, 1), dt.date(2028, 2, 29))


def test_평년_2월의_말일은_28일이다() -> None:
    assert period_bounds(dt.date(2026, 2, 10), "monthly") == (
        dt.date(2026, 2, 1), dt.date(2026, 2, 28))


def test_모든_달의_말일이_달력과_일치한다() -> None:
    """월별 일수를 직접 적어 두면 어느 달 하나가 틀려도 드러나지 않는다."""
    for year in (2026, 2028):
        for month in range(1, 13):
            _, end = period_bounds(dt.date(year, month, 15), "monthly")
            assert end.day == calendar.monthrange(year, month)[1]
            assert end.month == month
