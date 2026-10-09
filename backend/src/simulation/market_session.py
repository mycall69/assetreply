"""시장 거래 시간·거래일·장 상태 (014 T031) — FR-006, FR-007, SC-009, research R14-7, data-model 3.

**순수 함수 모듈이다**(헌법 원칙 IV) — DB·HTTP 없이 지금 시각과 출처의 세션 정보만 받는다.

출처가 시장 상태 필드를 주지 않는다(실측). 판정은 둘로 나눈다:

- **오늘이 거래일인가** — 출처가 알려 주는 현재 세션의 날짜다. 출처는 거래소 달력을 반영한다(한글날
  KOSPI는 지난
  거래일 세션을, 장 전 미국은 오늘 세션을 가리켰다). 세션 날짜가 현지 오늘보다 앞이면 휴장이다
- **장중·점심·마감** — 시장마다 정해 둔 시간표다. 출처의 세션 시각은 믿지 않는다(KOSPI 마감을
  15:00으로, 선물·외환을
  00:00–23:59로 준다)

출처가 세션 날짜를 주지 않는 선물·외환은 **갱신 없는 세션**으로 휴일을 가린다 — 시간표상 세션 안인데
값의 시각이 이번
세션 시작보다 앞이고 시작 뒤 설정 시간이 지났으면 휴장이다(성탄절 CME 등). 조기 마감일에는 마감
뒤에도 장중으로 보인다 —
기준 시각이 멈춘 것으로 드러난다.

시차는 `zoneinfo`로 바꾼다 — 고정하면 서머타임 전환 주에 미국 장 상태가 한 시간 틀린다(SC-009).
시간표는 시각뿐이라 날짜
하드코딩 검사에 걸리지 않는다. 시장 제도가 바뀌면(도쿄 2024-11 마감 15:30 연장 같은) 이 표를 고친다.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Final, Literal
from zoneinfo import ZoneInfo

MarketState = Literal["pre_open", "open", "break", "closed", "holiday"]

_SATURDAY: Final = 5
_SUNDAY: Final = 6
_FRIDAY: Final = 4
_DAY: Final = dt.timedelta(days=1)


@dataclass(frozen=True, slots=True)
class Market:
    """시장 하나의 시간표.

    `sessions`는 평일의 정규 세션(현지 시각)이다. `overnight`은 밤을 넘는 세션의
    규칙(`cme`·`fx`)이고, 그때는
    `sessions`를 쓰지 않는다.
    """

    key: str
    zone: ZoneInfo
    sessions: tuple[tuple[dt.time, dt.time], ...]
    overnight: Literal["cme", "fx"] | None = None


def _t(hour: int, minute: int = 0) -> dt.time:
    return dt.time(hour, minute)


_LONDON: Final = ZoneInfo("Europe/London")
_NEW_YORK: Final = ZoneInfo("America/New_York")

_MARKETS: Final[dict[str, Market]] = {
    "krx": Market("krx", ZoneInfo("Asia/Seoul"), ((_t(9), _t(15, 30)),)),
    "tse": Market("tse", ZoneInfo("Asia/Tokyo"), ((_t(9), _t(11, 30)), (_t(12, 30), _t(15, 30)))),
    "hkex": Market("hkex", ZoneInfo("Asia/Hong_Kong"), ((_t(9, 30), _t(12)), (_t(13), _t(16)))),
    "sse": Market("sse", ZoneInfo("Asia/Shanghai"), ((_t(9, 30), _t(11, 30)), (_t(13), _t(15)))),
    "us_equity": Market("us_equity", _NEW_YORK, ((_t(9, 30), _t(16)),)),
    "cboe": Market("cboe", ZoneInfo("America/Chicago"), ((_t(8, 30), _t(15, 15)),)),
    # 일 18:00 → 다음 날 17:00, 평일 17:00–18:00 쉼. 금 17:00 ~ 일 18:00 주말.
    "cme": Market("cme", _NEW_YORK, (), overnight="cme"),
    # 일 17:00 → 금 17:00(24시간). 하루의 경계는 출처 일봉의 런던 0시다.
    "fx": Market("fx", _NEW_YORK, (), overnight="fx"),
}

_CME_OPEN: Final = _t(18)
_CME_CLOSE: Final = _t(17)
_FX_OPEN_CLOSE: Final = _t(17)


def market(key: str) -> Market:
    """시장의 시간표. 모르는 키면 `KeyError` — 목록 밖 시장을 조용히 다루지 않는다."""
    return _MARKETS[key]


def _local(m: Market, instant: dt.datetime) -> dt.datetime:
    return instant.astimezone(m.zone)


def trading_date(key: str, instant: dt.datetime) -> dt.date:
    """시각이 속한 거래일(그 시장의 현지 날짜).

    - 정규 시장: 현지 날짜
    - `cme`: 18:00 뒤는 다음 거래일, 토 → 금, 일 18:00 전 → 금
    - `fx`: 런던 날짜(출처 일봉의 경계)
    """
    m = market(key)
    if m.overnight == "fx":
        return instant.astimezone(_LONDON).date()
    local = _local(m, instant)
    day = local.date()
    if m.overnight != "cme":
        return day
    weekday = day.weekday()
    if weekday == _SATURDAY:
        return day - _DAY
    if weekday == _SUNDAY:
        return day + _DAY if local.time() >= _CME_OPEN else day - 2 * _DAY
    if weekday < _FRIDAY and local.time() >= _CME_OPEN:
        return day + _DAY
    return day


def session_start(key: str, now: dt.datetime) -> dt.datetime | None:
    """지금 거래일 세션의 시작 시각(UTC). 정규 시장은 오늘 첫 세션의 개장, 주말이면 `None`.

    - `cme`: 거래일 전날 18:00(월요일 거래일은 일요일 18:00)
    - `fx`: 지금 런던 날짜의 0시. 주가 열리는 일요일 17:00(뉴욕)보다 이르면 그 시각
    """
    m = market(key)
    if m.overnight == "cme":
        day = trading_date(key, now)
        return dt.datetime.combine(day - _DAY, _CME_OPEN, m.zone).astimezone(dt.UTC)
    if m.overnight == "fx":
        london_day = now.astimezone(_LONDON).date()
        midnight = dt.datetime.combine(london_day, dt.time(), _LONDON)
        local = _local(m, now)
        if local.weekday() == _SUNDAY:
            week_open = dt.datetime.combine(local.date(), _FX_OPEN_CLOSE, m.zone)
            midnight = max(midnight, week_open)
        return midnight.astimezone(dt.UTC)
    local = _local(m, now)
    if local.weekday() >= _SATURDAY:
        return None
    return dt.datetime.combine(local.date(), m.sessions[0][0], m.zone).astimezone(dt.UTC)


def _schedule_state(m: Market, now: dt.datetime) -> MarketState:
    local = _local(m, now)
    weekday = local.weekday()
    t = local.time()
    if m.overnight == "cme":
        if weekday == _SATURDAY or (weekday == _SUNDAY and t < _CME_OPEN):
            return "holiday"
        if weekday == _FRIDAY and t >= _CME_CLOSE:
            return "closed"
        if weekday < _FRIDAY and _CME_CLOSE <= t < _CME_OPEN:
            return "break"
        return "open"
    if m.overnight == "fx":
        if weekday == _SATURDAY or (weekday == _SUNDAY and t < _FX_OPEN_CLOSE):
            return "holiday"
        if weekday == _FRIDAY and t >= _FX_OPEN_CLOSE:
            return "closed"
        return "open"
    if weekday >= _SATURDAY:
        return "holiday"
    if t < m.sessions[0][0]:
        return "pre_open"
    for opens, closes in m.sessions:
        if opens <= t < closes:
            return "open"
    if t >= m.sessions[-1][1]:
        return "closed"
    return "break"


def market_state(
    key: str,
    now: dt.datetime,
    *,
    source_session_start: dt.datetime | None,
    value_time: dt.datetime | None,
    holiday_detect_seconds: int,
) -> MarketState:
    """지금의 장 상태(data-model 3).

    `source_session_start`는 출처가 알려 준 현재 세션의 시작(정규 시장), `value_time`은 값의
    시각이다.
    """
    m = market(key)
    state = _schedule_state(m, now)
    # 개장 전에는 아직 오늘 세션을 알 수 없다 — 출처가 오늘 세션으로 넘어가는 시각이 시장마다 다를
    # 수 있다. 휴장이면
    # 개장 시각이 지난 뒤 드러난다(출처의 세션 날짜 또는 갱신 없는 세션).
    if state in ("holiday", "pre_open"):
        return state
    today = trading_date(key, now)
    if (
        m.overnight is None
        and source_session_start is not None
        and trading_date(key, source_session_start) < today
    ):
        return "holiday"
    if value_time is None:
        return state
    start = session_start(key, now)
    if start is not None and value_time < start <= now:
        if now - start >= dt.timedelta(seconds=holiday_detect_seconds):
            return "holiday"
        return "pre_open"
    return state


def display_timezone(key: str) -> str:
    """화면이 기준 시각을 보일 현지 시간대. 외환은 출처의 하루 경계(런던 0시)라 런던이다."""
    m = market(key)
    return _LONDON.key if m.overnight == "fx" else m.zone.key
