"""기준일 옮김·진행 중 판정 (T005) — 004 data-model 4·5절.

**2026년 실측 결측일을 사례로 쓴다.** 금요일 5-01·7-17, 말일 1-31·2-28·5-31.
지어낸 날짜로 검증하면 실제로 일어나는 경우를 놓친다.
"""
from __future__ import annotations

import datetime as dt

from src.api.services.period_rows import is_ongoing, period_bounds, shifted_from

TODAY = dt.date(2026, 9, 27)


def test_금요일_고시는_옮겨지지_않는다() -> None:
    """FR-014 — 옮겨지지 않은 행에 표시가 있으면 구별의 의미가 사라진다."""
    assert shifted_from(dt.date(2026, 9, 18), "weekly") is None


def test_금요일이_비면_원래_기준일을_알린다() -> None:
    """FR-013 — 2026-07-17(금)에 고시가 없어 07-16(목)이 쓰인 경우."""
    assert shifted_from(dt.date(2026, 7, 16), "weekly") == dt.date(2026, 7, 17)


def test_또_다른_금요일_결측도_같게_다룬다() -> None:
    """2026-05-01(금) 결측 → 04-30(목)."""
    assert shifted_from(dt.date(2026, 4, 30), "weekly") == dt.date(2026, 5, 1)


def test_말일_고시는_옮겨지지_않는다() -> None:
    assert shifted_from(dt.date(2026, 9, 30), "monthly") is None


def test_말일이_비면_원래_기준일을_알린다() -> None:
    """2026-01-31·02-28·05-31 결측 — 셋 다 주말이라 매년 되풀이된다."""
    assert shifted_from(dt.date(2026, 1, 30), "monthly") == dt.date(2026, 1, 31)
    assert shifted_from(dt.date(2026, 2, 27), "monthly") == dt.date(2026, 2, 28)
    assert shifted_from(dt.date(2026, 5, 29), "monthly") == dt.date(2026, 5, 31)


def test_일_단위는_옮겨지지_않는다() -> None:
    """하루는 그 자신이 기준일이다."""
    assert shifted_from(dt.date(2026, 9, 23), "daily") is None


def test_진행_중인_주는_참이다() -> None:
    """FR-015a — 오늘이 일요일이라도 그 주는 아직 오늘로 끝나지 않았다."""
    _, end = period_bounds(TODAY, "weekly")
    assert is_ongoing(end, TODAY, "weekly") is True


def test_지난_주는_거짓이다() -> None:
    _, end = period_bounds(dt.date(2026, 9, 18), "weekly")
    assert is_ongoing(end, TODAY, "weekly") is False


def test_진행_중인_달은_참이다() -> None:
    _, end = period_bounds(TODAY, "monthly")
    assert is_ongoing(end, TODAY, "monthly") is True


def test_지난_달은_거짓이다() -> None:
    _, end = period_bounds(dt.date(2026, 8, 31), "monthly")
    assert is_ongoing(end, TODAY, "monthly") is False


def test_일_단위는_언제나_진행_중이_아니다() -> None:
    """하루는 그 날짜로 끝난다. 오늘 행에 진행 중 표시가 붙으면 잠정값과 뒤섞인다."""
    assert is_ongoing(TODAY, TODAY, "daily") is False


def test_진행_중인_주는_기준일이_아직_오지_않았을_수_있다() -> None:
    """2026-09-23(수)이 이번 주 마지막 고시일이면 금요일(09-25)은 미래다.

    셋(옮김·진행 중·잠정)이 동시에 참인 경우가 여기서 나온다 (FR-015b).
    """
    quote = dt.date(2026, 9, 23)
    _, end = period_bounds(quote, "weekly")
    assert shifted_from(quote, "weekly") == dt.date(2026, 9, 25)
    assert is_ongoing(end, TODAY, "weekly") is True
