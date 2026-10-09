"""시장 거래 시간·장 상태 (014 T019) — FR-006, FR-007, SC-009, research R14-7, data-model 3.

출처가 시장 상태를 주지 않는다(실측). 오늘이 거래일인지는 출처의 세션 날짜로, 장중·점심·마감은
시장마다 정해 둔 시간표로
판정한다. 시차를 고정하지 않는다 — 서머타임 전환 주에 미국 장 상태가 한 시간 틀리지 않게(SC-009).
출처가 세션 날짜를 주지
않는 선물·외환은 "갱신 없는 세션"(세션 시작 뒤 한 시간 넘게 오늘 값이 없음)을 휴장으로 본다(I1).
"""

from __future__ import annotations

import datetime as dt
from zoneinfo import ZoneInfo

import pytest

from src.simulation.market_session import market_state, session_start, trading_date

UTC = dt.UTC
KST = ZoneInfo("Asia/Seoul")
NY = ZoneInfo("America/New_York")
CHI = ZoneInfo("America/Chicago")
DETECT = 3600


def at(tz: ZoneInfo, *parts: int) -> dt.datetime:
    return dt.datetime(*parts, tzinfo=tz).astimezone(UTC)


def state(
    market: str,
    now: dt.datetime,
    *,
    session: dt.datetime | None = None,
    value: dt.datetime | None = None,
) -> str:
    return market_state(
        market, now, source_session_start=session, value_time=value, holiday_detect_seconds=DETECT
    )


# ── krx ──


def test_한글날_KOSPI는_출처_세션이_지난_거래일이라_휴장() -> None:
    now = at(KST, 2026, 10, 9, 14, 30)
    assert state("krx", now, session=at(KST, 2026, 10, 8, 9, 0)) == "holiday"


@pytest.mark.parametrize(
    ("hm", "expected"),
    [((8, 30), "pre_open"), ((10, 0), "open"), ((15, 10), "open"), ((15, 31), "closed")],
)
def test_KOSPI_거래일의_시간표(hm: tuple[int, int], expected: str) -> None:
    now = at(KST, 2026, 10, 8, *hm)
    value = at(KST, 2026, 10, 8, 9, 30) if hm >= (9, 30) else at(KST, 2026, 10, 7, 20, 5)
    assert state("krx", now, session=at(KST, 2026, 10, 8, 9, 0), value=value) == expected


def test_KOSPI_마감은_출처의_15시가_아니라_15시_30분() -> None:
    now = at(KST, 2026, 10, 8, 15, 20)
    assert state("krx", now, session=at(KST, 2026, 10, 8, 9, 0), value=now) == "open"


# ── 점심 휴장 ──


@pytest.mark.parametrize(
    ("market", "tz", "hm"),
    [
        ("tse", "Asia/Tokyo", (11, 45)),
        ("hkex", "Asia/Hong_Kong", (12, 30)),
        ("sse", "Asia/Shanghai", (12, 0)),
    ],
)
def test_점심_휴장(market: str, tz: str, hm: tuple[int, int]) -> None:
    zone = ZoneInfo(tz)
    now = at(zone, 2026, 10, 8, *hm)
    value = at(zone, 2026, 10, 8, 11, 29)
    assert state(market, now, session=at(zone, 2026, 10, 8, 9, 0), value=value) == "break"


def test_도쿄_오후_장은_15시_30분까지() -> None:
    zone = ZoneInfo("Asia/Tokyo")
    now = at(zone, 2026, 10, 8, 15, 15)
    assert state("tse", now, value=now) == "open"


# ── 미국 서머타임 ──


def test_서머타임_시작_뒤_월요일_한국_22시_30분은_장중() -> None:
    assert state("us_equity", at(KST, 2026, 3, 9, 22, 30)) == "open"


def test_서머타임_시작_전_금요일_한국_22시_30분은_개장_전() -> None:
    assert state("us_equity", at(KST, 2026, 3, 6, 22, 30)) == "pre_open"


def test_서머타임_끝난_뒤_월요일_한국_23시_30분은_장중_22시_45분은_개장_전() -> None:
    assert state("us_equity", at(KST, 2026, 11, 2, 23, 30)) == "open"
    assert state("us_equity", at(KST, 2026, 11, 2, 22, 45)) == "pre_open"


def test_미국_장_마감_뒤() -> None:
    assert state("us_equity", at(NY, 2026, 10, 8, 16, 30)) == "closed"


# ── 선물(cme) ──


def test_cme_금요일_17시_30분은_마감_토요일은_휴장() -> None:
    assert state("cme", at(NY, 2026, 10, 9, 17, 30)) == "closed"
    assert state("cme", at(NY, 2026, 10, 10, 12, 0)) == "holiday"


def test_cme_일요일_18시_30분은_장중이고_거래일은_월요일() -> None:
    now = at(NY, 2026, 10, 11, 18, 30)
    assert state("cme", now) == "open"
    assert trading_date("cme", now) == dt.date(2026, 10, 12)


def test_cme_평일_17시_30분은_쉼() -> None:
    assert state("cme", at(NY, 2026, 10, 7, 17, 30)) == "break"


def test_cme_18시_뒤는_다음_거래일() -> None:
    assert trading_date("cme", at(NY, 2026, 10, 7, 20, 0)) == dt.date(2026, 10, 8)
    assert trading_date("cme", at(NY, 2026, 10, 7, 9, 0)) == dt.date(2026, 10, 7)
    assert trading_date("cme", at(NY, 2026, 10, 10, 9, 0)) == dt.date(2026, 10, 9)  # 토 → 금


def test_cme_성탄절은_갱신_없는_세션으로_휴장() -> None:
    """I1 — 출처 세션이 00:00–23:59라 휴일을 모른다. 세션 시작 뒤 오늘 값이 없으면 휴장이다."""
    value = at(NY, 2026, 12, 24, 13, 15)  # 성탄 전날 조기 마감
    assert state("cme", at(NY, 2026, 12, 24, 18, 30), value=value) == "pre_open"
    assert state("cme", at(NY, 2026, 12, 24, 20, 0), value=value) == "holiday"
    assert state("cme", at(NY, 2026, 12, 24, 20, 0), value=at(NY, 2026, 12, 24, 18, 5)) == "open"


def test_cme_세션_시작은_거래일_전날_18시() -> None:
    assert session_start("cme", at(NY, 2026, 10, 12, 10, 0)) == at(NY, 2026, 10, 11, 18, 0)


# ── 외환(fx) ──


def test_fx_토요일은_휴장_일요일_17시_30분은_장중() -> None:
    assert state("fx", at(NY, 2026, 10, 10, 12, 0)) == "holiday"
    assert state("fx", at(NY, 2026, 10, 11, 17, 30)) == "open"
    assert state("fx", at(NY, 2026, 10, 9, 17, 30)) == "closed"


def test_fx_1월_1일은_갱신_없는_세션으로_휴장() -> None:
    london = ZoneInfo("Europe/London")
    value = at(london, 2026, 12, 31, 21, 59)
    assert state("fx", at(london, 2027, 1, 1, 0, 30), value=value) == "pre_open"
    assert state("fx", at(london, 2027, 1, 1, 2, 0), value=value) == "holiday"


def test_fx_거래일은_런던_날짜() -> None:
    assert trading_date("fx", at(NY, 2026, 10, 8, 21, 0)) == dt.date(2026, 10, 9)


# ── 그 밖 ──


def test_VIX_정규_시간_전은_개장_전() -> None:
    assert state("cboe", at(CHI, 2026, 10, 8, 8, 0)) == "pre_open"
    assert state("cboe", at(CHI, 2026, 10, 8, 9, 0)) == "open"


@pytest.mark.parametrize(
    ("market", "tz"),
    [
        ("krx", "Asia/Seoul"),
        ("tse", "Asia/Tokyo"),
        ("hkex", "Asia/Hong_Kong"),
        ("sse", "Asia/Shanghai"),
        ("us_equity", "America/New_York"),
        ("cboe", "America/Chicago"),
    ],
)
def test_주말은_늘_휴장(market: str, tz: str) -> None:
    zone = ZoneInfo(tz)
    assert state(market, at(zone, 2026, 10, 10, 12, 0)) == "holiday"
    assert state(market, at(zone, 2026, 10, 11, 12, 0)) == "holiday"


def test_정규_시장의_거래일은_현지_날짜() -> None:
    assert trading_date("us_equity", at(KST, 2026, 10, 9, 8, 0)) == dt.date(2026, 10, 8)
    assert trading_date("krx", at(KST, 2026, 10, 9, 8, 0)) == dt.date(2026, 10, 9)


def test_모르는_시장은_거절() -> None:
    with pytest.raises(KeyError):
        trading_date("nyse", at(NY, 2026, 10, 8, 9, 0))
