"""그 거래일의 정규 세션이 끝났는가 (버그 stock-provisional-bar) — 014 research R14-7.

주식 시세 어댑터가 출처의 마지막 봉이 장중 값인지 가르는 데 쓴다. 시간표는 시장마다 정해 둔 것이다 —
출처의 세션 시각은 믿지 않는다(KOSPI 마감을 15:00으로 준다). 시차를 고정하지 않는다 — 서머타임 전환
주에 미국 장이 한 시간 틀린다.
"""

from __future__ import annotations

import datetime as dt
from zoneinfo import ZoneInfo

import pytest

from src.simulation.market_session import session_finished

KST = ZoneInfo("Asia/Seoul")
NY = ZoneInfo("America/New_York")
JST = ZoneInfo("Asia/Tokyo")
D = dt.date.fromisoformat


def at(tz: ZoneInfo, *parts: int) -> dt.datetime:
    return dt.datetime(*parts, tzinfo=tz).astimezone(dt.UTC)


@pytest.mark.parametrize(("hm", "finished"), [
    ((8, 59), False), ((9, 0), False), ((12, 0), False), ((15, 29), False), ((15, 30), True),
    ((20, 0), True)])
def test_KRX_오늘_세션(hm: tuple[int, int], finished: bool) -> None:
    assert session_finished("krx", D("2026-10-08"), at(KST, 2026, 10, 8, *hm)) is finished


def test_지난_거래일은_끝났다() -> None:
    """한국 날짜의 어제를 묻는 기본 계산 끝 — 국내 종목은 늘 끝난 세션이다."""
    assert session_finished("krx", D("2026-10-08"), at(KST, 2026, 10, 9, 0, 19)) is True


def test_미국_장중() -> None:
    """한국 00:23(10-09)은 뉴욕 10-08 11:23이다.

    한국 날짜의 어제(10-08)가 미국의 오늘이고 장이 열려 있다."""
    assert session_finished("us_equity", D("2026-10-08"), at(KST, 2026, 10, 9, 0, 23)) is False


def test_미국_마감_뒤() -> None:
    assert session_finished("us_equity", D("2026-10-08"), at(NY, 2026, 10, 8, 16, 0)) is True
    assert session_finished("us_equity", D("2026-10-08"), at(KST, 2026, 10, 9, 9, 0)) is True


def test_서머타임이_끝난_뒤의_미국_마감은_한국_6시다() -> None:
    """2026-11-01에 서머타임이 끝난다. 11-02(월) 마감 16:00 EST = 한국 11-03 06:00."""
    assert session_finished("us_equity", D("2026-11-02"), at(KST, 2026, 11, 3, 5, 30)) is False
    assert session_finished("us_equity", D("2026-11-02"), at(KST, 2026, 11, 3, 6, 0)) is True


def test_도쿄_점심은_끝나지_않았다() -> None:
    assert session_finished("tse", D("2026-10-08"), at(JST, 2026, 10, 8, 12, 0)) is False
    assert session_finished("tse", D("2026-10-08"), at(JST, 2026, 10, 8, 15, 30)) is True


def test_지금_거래일보다_뒤의_날은_끝나지_않았다() -> None:
    assert session_finished("krx", D("2026-10-09"), at(KST, 2026, 10, 8, 20, 0)) is False


def test_모르는_시장은_거절() -> None:
    with pytest.raises(KeyError):
        session_finished("nowhere", D("2026-10-08"), at(KST, 2026, 10, 8, 20, 0))
