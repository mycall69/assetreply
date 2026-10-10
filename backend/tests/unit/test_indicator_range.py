"""보는 기간 8개 (014 반복 2026-10-10b T104) — FR-011, data-model §5.

순수 함수다(DB·HTTP 없음). 기간은 그 시장 현지의 오늘에서 센다. 1개월·n년 전 같은 날이 없으면 그 달
말일이다(011
`months_later`와 같은 뜻).
"""

from __future__ import annotations

import datetime as dt

import pytest

from src.simulation.indicator_range import DEFAULT_RANGE, RANGES, is_intraday, range_of, range_start

D = dt.date


def test_기간은_여덟이고_처음은_1년이다() -> None:
    assert RANGES == ("1d", "5d", "1m", "1y", "5y", "10y", "20y", "all")
    assert DEFAULT_RANGE == "1y"


@pytest.mark.parametrize(
    ("raw", "expected"), [(None, "1y"), ("5y", "5y"), ("weekly", "1y"), ("", "1y"), ("all", "all")]
)
def test_틀리거나_없으면_1년이다(raw: str | None, expected: str) -> None:
    assert range_of(raw) == expected


def test_일_주는_장중이다() -> None:
    assert [r for r in RANGES if is_intraday(r)] == ["1d", "5d"]


@pytest.mark.parametrize(
    ("today", "key", "start"),
    [
        (D(2026, 10, 9), "1m", D(2026, 9, 9)),
        (D(2026, 10, 9), "1y", D(2025, 10, 9)),
        (D(2026, 10, 9), "5y", D(2021, 10, 9)),
        (D(2026, 10, 9), "10y", D(2016, 10, 9)),
        (D(2026, 10, 9), "20y", D(2006, 10, 9)),
        (D(2026, 3, 31), "1m", D(2026, 2, 28)),
        (D(2028, 2, 29), "1y", D(2027, 2, 28)),
    ],
)
def test_기간의_시작일(today: dt.date, key: str, start: dt.date) -> None:
    assert range_start(today, key) == start  # type: ignore[arg-type]


def test_모두와_장중은_시작일이_없다() -> None:
    assert range_start(D(2026, 10, 9), "all") is None
    assert range_start(D(2026, 10, 9), "1d") is None
