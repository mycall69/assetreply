"""장중 처음 보이는 범위 (014 반복 2026-10-10c T129) — FR-011, FR-028, research R14-22.

순수 함수다. 받은 장중 점(UTC 시각)을 그 시장의 거래일로 가르고 마지막 세션(일)·최근 5세션(주)의
처음 ~ 끝을 낸다.

- 거래일은 `market_session.trading_date`와 같다 — 정규 시장은 현지 날짜, 환율은 런던 날짜,
  선물(CME)은 18:00 뒤가 다음 거래일
- 세션은 점이 있는 날뿐이다 — 휴장을 꾸미지 않는다. 세션이 모자라면 받은 점 전부다
- 점이 없으면 `None`이다
"""

from __future__ import annotations

import datetime as dt

from src.simulation.intraday_window import session_window

UTC = dt.UTC


def at(day: int, hour: int, minute: int = 0, month: int = 10) -> dt.datetime:
    return dt.datetime(2026, month, day, hour, minute, tzinfo=UTC)


def us_day(day: int) -> list[dt.datetime]:
    """뉴욕 정규 세션 09:30~16:00(서머타임 — 13:30~20:00 UTC)의 30분 점."""
    start = at(day, 13, 30)
    return [start + dt.timedelta(minutes=30 * i) for i in range(14)]


def test_마지막_세션() -> None:
    times = us_day(7) + us_day(8) + us_day(9)
    assert session_window(times, "us_equity", 1) == (at(9, 13, 30), at(9, 20, 0))


def test_최근_5세션은_점이_있는_날만_센다() -> None:
    # 10-06(화)은 점이 없다(출처가 비움) — 세지 않는다
    times = us_day(1) + us_day(2) + us_day(5) + us_day(7) + us_day(8) + us_day(9)
    assert session_window(times, "us_equity", 5) == (at(2, 13, 30), at(9, 20, 0))


def test_세션이_모자라면_전부다() -> None:
    times = us_day(8) + us_day(9)
    assert session_window(times, "us_equity", 5) == (at(8, 13, 30), at(9, 20, 0))


def test_환율은_런던_날짜로_가른다() -> None:
    # 22:30 UTC = 런던 10-08 23:30, 23:00 UTC = 런던 10-09 0시(서머타임)
    times = [at(8, 21, 0), at(8, 22, 30), at(8, 23, 0), at(9, 6, 0), at(9, 20, 30)]
    assert session_window(times, "fx", 1) == (at(8, 23, 0), at(9, 20, 30))


def test_선물은_뉴욕_18시_뒤가_다음_거래일이다() -> None:
    # 22:30 UTC = 뉴욕 18:30(서머타임) → 10-09 거래일
    times = [at(8, 20, 0), at(8, 22, 30), at(9, 15, 0)]
    assert session_window(times, "cme", 1) == (at(8, 22, 30), at(9, 15, 0))


def test_한국은_한국_날짜다() -> None:
    times = [at(7, 0, 0), at(7, 6, 30), at(8, 0, 0), at(8, 6, 30)]  # 09:00·15:30 KST
    assert session_window(times, "krx", 1) == (at(8, 0, 0), at(8, 6, 30))


def test_점이_없으면_None이다() -> None:
    assert session_window([], "us_equity", 1) is None
