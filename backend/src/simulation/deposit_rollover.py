"""예금 재예치 시뮬레이션 (T017) — 008 FR-007, FR-018, FR-019, FR-021~FR-029, research R8-7·R8-8.

시작일에 원금 전액으로 **1년 만기 정기예금**에 가입한다. 금리는 가입한 달의 금리로 1년 고정이고,
만기에는 세후 이자를 원금에 더해 **그날 바로** 다시 1년 가입한다(재예치). 재예치 금리는 재예치하는
달의 금리다.

**원 미만 버림은 두 곳뿐이다**(research R8-7):

    이자  I = 0 쪽 절사(P × r / 100)               — 만기분. 1년이 365일이든 366일이든 같다
    경과  a = 0 쪽 절사(P × r / 100 × 경과 일수 / 회차 일수)
    세금  T = 0 쪽 절사(I × 세율), 이자가 0 이하이면 0
    재예치 원금 = P + (I − T)

금리의 달이 **마지막 발표 달 뒤**면 미발표다 — 마지막 발표 달 금리로 **잠정** 계산하고 그 회차부터
모두 잠정으로 표시한다(FR-007, FR-024). 마지막 발표 달 안에서 금리가 없는 달은 **결측**이다 —
보간하지 않는다(헌법 원칙 V). 가입 달이 결측이면 계산하지 않고(`RateMissing`), 재예치 달이 결측이면
그 만기일에서 멈춘다(`stopped`).

**순수 함수 모듈이다.** `repository`·`api`·`db`를 임포트하지 않는다(헌법 원칙 IV). 계산은
`Decimal`이다(헌법 원칙 VI).
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from decimal import ROUND_DOWN, Decimal, localcontext
from typing import Literal

from src.simulation.money import CALC_PRECISION, quantize_rate

_ZERO = Decimal(0)
_HUNDRED = Decimal(100)

RowKind = Literal["join", "month", "maturity", "reinvest"]


class RateMissing(Exception):  # noqa: N818 — 계산이 멈춘 사유의 이름이다(API `rate_missing`)
    """금리 통계가 비어 있는 달에 가입해야 한다 — 보간하지 않는다(헌법 원칙 V)."""

    def __init__(self, month: dt.date) -> None:
        super().__init__(f"{month:%Y-%m} 금리 통계가 비어 있습니다")
        self.month = month


class BeforeFirstMonth(Exception):  # noqa: N818 — API `before_first_month`
    """시작일이 그 투자처의 금리 통계가 시작하는 달보다 이르다(FR-006)."""

    def __init__(self, first_month: dt.date) -> None:
        super().__init__(f"{first_month.isoformat()}부터 금리가 있습니다")
        self.first_month = first_month


@dataclass(frozen=True, slots=True)
class Term:
    """끝난 회차 — 만기 이자와 세금이 정해졌다."""

    no: int
    joined_on: dt.date
    matures_on: dt.date
    rate: Decimal
    #: 그 금리의 달. 잠정이면 대신 쓴 달(마지막 발표 달)이다.
    rate_month: dt.date
    provisional: bool
    principal: Decimal
    interest: Decimal
    tax: Decimal
    after_tax: Decimal


@dataclass(frozen=True, slots=True)
class OpenTerm:
    """계산 끝에 진행 중인 회차."""

    joined_on: dt.date
    matures_on: dt.date
    rate: Decimal
    rate_month: dt.date
    principal: Decimal
    provisional: bool


@dataclass(frozen=True, slots=True)
class Row:
    """표의 행. `month` 행의 이자·세금은 그날까지의 **경과분**, `maturity` 행은 만기분,
    `join`·`reinvest`는 0이다."""

    date: dt.date
    kind: RowKind
    rate: Decimal
    rate_month: dt.date
    provisional: bool
    principal: Decimal
    interest: Decimal
    tax: Decimal
    after_tax: Decimal
    balance: Decimal
    profit: Decimal
    return_rate: Decimal


@dataclass(frozen=True, slots=True)
class Stopped:
    date: dt.date
    reason: Literal["rate_missing"]
    month: dt.date


@dataclass(frozen=True, slots=True)
class Summary:
    principal: Decimal
    balance: Decimal
    profit: Decimal
    return_rate: Decimal
    #: 계산 끝. 멈췄으면 그 만기일이다.
    as_of: dt.date
    is_final: bool
    current_term: OpenTerm | None
    #: 잠정 회차가 시작된 날(가입일 또는 재예치일). 없으면 `None`.
    provisional_from: dt.date | None
    stopped: Stopped | None


@dataclass(frozen=True, slots=True)
class DepositOutcome:
    #: 끝난 회차(오름차순). 진행 중인 회차는 `summary.current_term`이다.
    terms: list[Term]
    #: 최신순. 같은 날이면 재예치가 만기보다 앞이다.
    rows: list[Row]
    summary: Summary


def add_one_year(day: dt.date) -> dt.date:
    """만기일 — 1년 뒤 같은 날. 2월 29일 가입이면 다음 해 2월 28일이다(FR-021)."""
    try:
        return day.replace(year=day.year + 1)
    except ValueError:
        return day.replace(year=day.year + 1, day=28)


def _trunc(value: Decimal) -> Decimal:
    """0 쪽으로 원 미만을 버린다. `-0`을 내지 않는다 — 화면에 `-0`이 보이면 손실로 읽힌다."""
    out = value.to_integral_value(rounding=ROUND_DOWN)
    return _ZERO if out == 0 else out


def maturity_interest(principal: Decimal, rate: Decimal) -> Decimal:
    """만기 이자 — 0 쪽 절사(원금 × 연 금리 / 100)."""
    with localcontext() as ctx:
        ctx.prec = CALC_PRECISION
        return _trunc(principal * rate / _HUNDRED)


def accrued_interest(principal: Decimal, rate: Decimal, joined: dt.date, matures: dt.date,
                     on: dt.date) -> Decimal:
    """그날까지의 경과 이자 — 0 쪽 절사(원금 × 연 금리 / 100 × 경과 일수 / 회차 일수). 만기일이면
    만기 이자와 같다(FR-022). 나눗셈은 한 번만 한다 — 나눠서 곱하면 정확히 정수인 값이 그 아래로
    내려갈 수 있다."""
    elapsed = (on - joined).days
    term_days = (matures - joined).days
    with localcontext() as ctx:
        ctx.prec = CALC_PRECISION
        return _trunc(principal * rate * elapsed / (_HUNDRED * term_days))


def interest_tax(interest: Decimal, tax_rate: Decimal) -> Decimal:
    """이자 소득세 — 0 쪽 절사(이자 × 세율). 이자가 0 이하면 0이다(FR-023)."""
    if interest <= 0:
        return _ZERO
    with localcontext() as ctx:
        ctx.prec = CALC_PRECISION
        return _trunc(interest * tax_rate)


def _month_of(day: dt.date) -> dt.date:
    return day.replace(day=1)


def _next_month(month: dt.date) -> dt.date:
    return month.replace(year=month.year + month.month // 12, month=month.month % 12 + 1)


@dataclass(frozen=True, slots=True)
class _Rate:
    rate: Decimal
    month: dt.date
    provisional: bool


def _rate_resolver(rates: Mapping[dt.date, Decimal],
                   latest_month: dt.date) -> Callable[[dt.date], _Rate]:
    published = [m for m in rates if m <= latest_month]
    fallback = max(published) if published else None

    def rate_for(day: dt.date) -> _Rate:
        month = _month_of(day)
        if month > latest_month:
            # 미발표 — 마지막 발표 달 금리로 잠정 계산한다(FR-007). 확정값과 섞이지 않게
            # 표시한다(헌법 원칙 V).
            if fallback is None:
                raise RateMissing(month)
            return _Rate(rates[fallback], fallback, True)
        if month not in rates:
            raise RateMissing(month)
        return _Rate(rates[month], month, False)

    return rate_for


def simulate_deposit(*, principal: Decimal, start: dt.date, end: dt.date,
                     rates: Mapping[dt.date, Decimal], first_month: dt.date,
                     latest_month: dt.date, tax_rate: Decimal) -> DepositOutcome:
    """시작일부터 계산 끝(오늘, 한국 시간)까지 재예치를 되풀이한다.

    `rates`는 달(1일) → 연 금리(%)다. `latest_month`는 마지막 발표 달이고 그 뒤의 달은 미발표다.
    """
    if start < first_month:
        raise BeforeFirstMonth(first_month)
    if end < start:
        raise ValueError("계산 끝이 시작일보다 이르다")

    rate_for = _rate_resolver(rates, latest_month)
    initial = principal

    def row(day: dt.date, kind: RowKind, r: _Rate, p: Decimal, interest: Decimal = _ZERO,
            tax: Decimal = _ZERO) -> Row:
        after = interest - tax
        balance = p + after
        profit = balance - initial
        with localcontext() as ctx:
            ctx.prec = CALC_PRECISION
            return_rate = quantize_rate(profit / initial)
        return Row(date=day, kind=kind, rate=r.rate, rate_month=r.month, provisional=r.provisional,
                   principal=p, interest=interest, tax=tax, after_tax=after, balance=balance,
                   profit=profit, return_rate=return_rate)

    current = rate_for(start)  # 가입 달이 결측이면 여기서 막힌다(FR-019)
    joined, held = start, principal
    provisional_from = start if current.provisional else None
    ascending: list[Row] = [row(start, "join", current, held)]
    terms: list[Term] = []
    stopped: Stopped | None = None
    balance: Decimal

    while True:
        matures = add_one_year(joined)
        month = _next_month(_month_of(joined))
        while month < matures and month <= end:
            # 매달 1일 — 그날까지의 경과분(FR-022). 가입일·만기일이 1일이면 그날 월 행이 없다.
            accrued = accrued_interest(held, current.rate, joined, matures, month)
            ascending.append(row(month, "month", current, held, accrued,
                                 interest_tax(accrued, tax_rate)))
            month = _next_month(month)

        if matures > end:
            accrued = accrued_interest(held, current.rate, joined, matures, end)
            balance = held + accrued - interest_tax(accrued, tax_rate)
            break

        interest = maturity_interest(held, current.rate)
        tax = interest_tax(interest, tax_rate)
        terms.append(Term(no=len(terms) + 1, joined_on=joined, matures_on=matures,
                          rate=current.rate, rate_month=current.month,
                          provisional=current.provisional, principal=held, interest=interest,
                          tax=tax, after_tax=interest - tax))
        ascending.append(row(matures, "maturity", current, held, interest, tax))
        rolled = held + interest - tax
        try:
            following = rate_for(matures)
        except RateMissing as exc:
            # 재예치 달이 결측이면 그 만기일에서 멈춘다 — 보간하지 않는다(헌법 원칙 V, FR-019).
            stopped = Stopped(date=matures, reason="rate_missing", month=exc.month)
            balance = rolled
            break
        if following.provisional and provisional_from is None:
            provisional_from = matures
        ascending.append(row(matures, "reinvest", following, rolled))
        joined, held, current = matures, rolled, following

    profit = balance - initial
    with localcontext() as ctx:
        ctx.prec = CALC_PRECISION
        return_rate = quantize_rate(profit / initial)
    open_term = None if stopped is not None else OpenTerm(
        joined_on=joined, matures_on=add_one_year(joined), rate=current.rate,
        rate_month=current.month, principal=held, provisional=current.provisional)
    summary = Summary(
        principal=initial, balance=balance, profit=profit, return_rate=return_rate,
        as_of=stopped.date if stopped is not None else end, is_final=stopped is None,
        current_term=open_term, provisional_from=provisional_from, stopped=stopped)
    return DepositOutcome(terms=terms, rows=list(reversed(ascending)), summary=summary)
