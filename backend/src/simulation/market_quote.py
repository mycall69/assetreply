"""카드의 현재 값·전일 대비 (014 T032) — FR-004, FR-005, FR-007, SC-003, research R14-8·R14-9,
data-model 4.

**순수 함수 모듈이다**(헌법 원칙 IV). 출처 시세와 저장된 이력의 전일 종가를 받아 카드 값을 낸다.
저장하지 않는다.

- **전일 종가는 이력이 먼저다** — 세션 날짜 앞의 마지막 저장 종가. 그래야 카드의 전일이 그래프의
  같은 날 값과 같다
  (SC-003). 이력이 세션 날짜 하루 전까지 닿지 않았으면 출처 값으로 물러나고 `source`라고
  밝힌다(FR-005)
- **출처 값은 하루 변화량에서 역산한 값이 먼저다** — 상해의 출처 전일 종가가 `0.0002050505`로 깨져
  있었다(실측)
- **환율은 늘 출처다**(`source_fx` — 이력이 ECOS라 다른 계열, 명확화 2). 엔은 100엔당(×100 —
  `Decimal` 곱이라 정확)
- 전일 종가가 0 이하이면 등락률을 비운다(WTI 2020-04-20 −37.63) — 0으로 메우지 않는다(원칙 V)
- 지연은 장중에 값의 시각과 받은 시각의 차이로 판정한다 — 출처가 지연 여부를 주지 않는다(R14-9)
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from decimal import Decimal
from typing import Final, Literal

from src.simulation.market_indicators import Indicator
from src.simulation.market_session import MarketState, market_state, trading_date
from src.simulation.money import quantize_rate

PreviousSource = Literal["history", "source", "source_fx"]
Direction = Literal["up", "down", "flat"]

#: 값·차이의 자릿수 — 저장 열(`DECIMAL(20,6)`)과 같다.
_PLACES: Final = Decimal("0.000001")
_ZERO: Final = Decimal(0)
_DAY: Final = dt.timedelta(days=1)
_MINUTE: Final = dt.timedelta(minutes=1)


@dataclass(frozen=True, slots=True)
class SourceQuote:
    """출처 시세 하나(수집 계층이 출처 필드를 이 모양으로 옮긴다 — 원칙 II)."""

    price: Decimal
    market_time: dt.datetime
    full_day_change: Decimal | None
    chart_previous_close: Decimal | None
    #: 출처가 알려 준 현재 세션의 시작 — 오늘이 거래일인지의 근거(R14-7).
    session_start: dt.datetime | None


@dataclass(frozen=True, slots=True)
class Previous:
    close: Decimal
    date: dt.date | None
    source: PreviousSource


@dataclass(frozen=True, slots=True)
class MarketQuote:
    value: Decimal
    value_time: dt.datetime
    session_date: dt.date
    state: MarketState
    provisional: bool
    delay_minutes: int | None
    previous: Previous | None
    change: Decimal | None
    change_rate: Decimal | None
    #: 등락률을 비운 까닭 — `non_positive_base`(전일 ≤ 0), `no_previous`(전일을 알 수 없음).
    change_rate_blank: str | None
    direction: Direction | None


def _q(value: Decimal) -> Decimal:
    return value.quantize(_PLACES)


def session_date_of(indicator: Indicator, quote: SourceQuote) -> dt.date:
    """값의 거래일 — 이력에서 전일 종가를 찾는 기준이다. 휴장이면 마지막 거래일이다."""
    return trading_date(indicator.market, quote.market_time)


def _previous(
    indicator: Indicator,
    quote: SourceQuote,
    *,
    multiplier: Decimal,
    session_date: dt.date,
    history_previous: tuple[dt.date, Decimal] | None,
    coverage_through: dt.date | None,
) -> Previous | None:
    if indicator.history == "fx":
        if quote.chart_previous_close is None:
            return None
        return Previous(_q(quote.chart_previous_close * multiplier), None, "source_fx")
    reaches = coverage_through is not None and coverage_through >= session_date - _DAY
    if history_previous is not None and reaches:
        day, close = history_previous
        return Previous(_q(close), day, "history")
    if quote.full_day_change is not None:
        return Previous(_q((quote.price - quote.full_day_change) * multiplier), None, "source")
    if quote.chart_previous_close is not None:
        return Previous(_q(quote.chart_previous_close * multiplier), None, "source")
    return None


def compose_quote(
    indicator: Indicator,
    quote: SourceQuote,
    *,
    multiplier: Decimal,
    history_previous: tuple[dt.date, Decimal] | None,
    coverage_through: dt.date | None,
    now: dt.datetime,
    fetched_at: dt.datetime,
    delay_notice_seconds: int,
    holiday_detect_seconds: int,
) -> MarketQuote:
    """카드 값 하나(data-model 4). `history_previous`는 세션 날짜 앞의 마지막 저장 종가다."""
    value = _q(quote.price * multiplier)
    session_date = session_date_of(indicator, quote)
    state = market_state(
        indicator.market,
        now,
        source_session_start=quote.session_start,
        value_time=quote.market_time,
        holiday_detect_seconds=holiday_detect_seconds,
    )
    previous = _previous(
        indicator,
        quote,
        multiplier=multiplier,
        session_date=session_date,
        history_previous=history_previous,
        coverage_through=coverage_through,
    )

    change: Decimal | None = None
    rate: Decimal | None = None
    blank: str | None = "no_previous"
    direction: Direction | None = None
    if previous is not None:
        change = _q(value - previous.close)
        direction = "up" if change > 0 else "down" if change < 0 else "flat"
        if previous.close > _ZERO:
            rate, blank = quantize_rate(change / previous.close), None
        else:
            blank = "non_positive_base"

    today = trading_date(indicator.market, now)
    provisional = state in ("open", "break") or (state == "closed" and session_date == today)
    delay: int | None = None
    if state == "open":
        lag = fetched_at - quote.market_time
        if lag > dt.timedelta(seconds=delay_notice_seconds):
            delay = lag // _MINUTE
    return MarketQuote(
        value=value,
        value_time=quote.market_time,
        session_date=session_date,
        state=state,
        provisional=provisional,
        delay_minutes=delay,
        previous=previous,
        change=change,
        change_rate=rate,
        change_rate_blank=blank,
        direction=direction,
    )
