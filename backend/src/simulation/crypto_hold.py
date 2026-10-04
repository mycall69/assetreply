"""가상자산 매수 후 보유 시뮬레이션 (T029) — 007 FR-025~FR-031, research R7-7·R7-9.

시작 월의 **첫 일봉 시가로 원금 전액을 써서 한 번 사고** 보유한다. 추가 매수·매도·배당·분할이 없다 —
주식의 `reinvest.py`를 일반화하지 않는 이유다. 공유할 것이 계산 뼈대뿐이고, 일반화하면 주식의 참조
구현 대조가 흔들린다(R7-7).

- 수량은 소수 8자리에서 **버린다**(FR-026). 수수료 = 수량 × 시가 × 수수료율이고 매수 금액에 더해
  **예수금에서 빠진다**(FR-027)
- 잔고 = 보유 수량 × 그 행의 시가 — 예수금을 포함하지 않는다. 총자산 = 잔고 + 예수금(FR-028)
- 행은 **매달의 첫 일봉**이다. 그 달 1일이 결측이면 그 달의 첫 일봉이 행이고 결측을
  표시한다(FR-030). 결측일을 채우지
  않는다(헌법 원칙 V)

**순수 함수 모듈이다.** `repository`·`api`·`db`를 임포트하지 않는다(헌법 원칙 IV). 계산은
`Decimal`이다(헌법 원칙 VI).
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal, localcontext

from src.simulation.money import CALC_PRECISION, buy_fraction, quantize_rate

_ZERO = Decimal(0)
_ONE = Decimal(1)


@dataclass(frozen=True, slots=True)
class DayOpen:
    """UTC 하루의 시가."""

    date: dt.date
    open_price: Decimal


@dataclass(frozen=True, slots=True)
class HoldCondition:
    start: dt.date
    #: 시세 통화로 바꾼 원금. 원화 원금이면 환전한 금액이다.
    principal: Decimal
    fee_rate: Decimal
    #: 출처의 첫 일봉(수집 중 발견, research R7-10). 그 앞의 날은 결측이 아니라 없던 날이다.
    first_available: dt.date | None = None


@dataclass(frozen=True, slots=True)
class HoldRow:
    date: dt.date
    open_price: Decimal
    bought_quantity: Decimal
    held_quantity: Decimal
    cash: Decimal
    principal: Decimal
    balance: Decimal
    profit: Decimal
    return_rate: Decimal
    #: 그 행의 매수 수수료. 사지 않았으면 `None` — "수수료 0"과 "매수 없음"을 구별한다(005와 같다).
    trade_fee: Decimal | None = None
    #: 그 달 1일 일봉이 출처에 없어 다른 날이 그 달의 행이면 그 1일(FR-030).
    first_day_missing: dt.date | None = None


@dataclass(frozen=True, slots=True)
class HoldOutcome:
    """결과 전체. `rows`는 최신순 월 행이고, `latest`는 **마지막 일봉의 평가**다 — 보드는 이것을
    쓴다(005와 같은 이유).

    `bought_on`은 실제 매수일이다 — 시작 월 1일이 결측이면 1일이 아니다(FR-030).
    """

    rows: list[HoldRow]
    latest: HoldRow | None
    bought_on: dt.date | None


def _row(bar: DayOpen, *, bought: Decimal, held: Decimal, cash: Decimal, condition: HoldCondition,
         trade_fee: Decimal | None = None, first_day_missing: dt.date | None = None) -> HoldRow:
    with localcontext() as ctx:
        ctx.prec = CALC_PRECISION
        balance = held * bar.open_price
        profit = balance + cash - condition.principal
        rate = (quantize_rate(profit / condition.principal)
                if condition.principal > 0 else _ZERO)
    return HoldRow(
        date=bar.date, open_price=bar.open_price, bought_quantity=bought, held_quantity=held,
        cash=cash, principal=condition.principal, balance=balance, profit=profit,
        return_rate=rate, trade_fee=trade_fee, first_day_missing=first_day_missing)


def _missing_first_day(day: dt.date, first_available: dt.date | None) -> dt.date | None:
    """그 달의 첫 일봉이 1일이 아니면 1일이 결측이다 — 다만 출처의 첫 일봉 전은 없던 날이다."""
    first = day.replace(day=1)
    if day == first or (first_available is not None and first < first_available):
        return None
    return first


def simulate_hold(bars: Sequence[DayOpen], condition: HoldCondition) -> HoldOutcome:
    """일봉 시가와 조건에서 월 행과 마지막 평가를 만든다. 일봉이 없는 날은 행을 만들지 않는다(헌법
    원칙 V)."""
    ordered = sorted((b for b in bars if b.date >= condition.start.replace(day=1)),
                     key=lambda b: b.date)
    if not ordered:
        return HoldOutcome(rows=[], latest=None, bought_on=None)

    month_firsts: dict[tuple[int, int], DayOpen] = {}
    for bar in ordered:
        month_firsts.setdefault((bar.date.year, bar.date.month), bar)

    buy_bar = ordered[0]
    held = buy_fraction(condition.principal, buy_bar.open_price, condition.fee_rate)
    with localcontext() as ctx:
        ctx.prec = CALC_PRECISION
        cost = held * buy_bar.open_price
        fee = cost * condition.fee_rate
        cash = condition.principal - cost - fee

    rows = [
        _row(bar, bought=held if bar is buy_bar else _ZERO, held=held,
             cash=cash, condition=condition,
             trade_fee=fee if bar is buy_bar and held > 0 else None,
             first_day_missing=_missing_first_day(bar.date, condition.first_available))
        for bar in month_firsts.values()]
    rows.sort(key=lambda r: r.date, reverse=True)
    latest = _row(ordered[-1], bought=_ZERO, held=held, cash=cash, condition=condition)
    return HoldOutcome(rows=rows, latest=latest, bought_on=buy_bar.date)
