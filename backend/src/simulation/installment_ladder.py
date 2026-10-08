"""정기 적금 → 정기예금 사다리 (011 T047) — FR-024~FR-028, FR-030, research R11-8.

매달 같은 돈을 **1년 만기·12회 정기 적금**에 붓는다. 적금이 만기되는 날마다:

1. 그날 만기되는 정기예금이 있으면 그 만기 금액과 적금의 만기 금액을 **합친다**
   (첫 만기에는 적금뿐이다)
2. 합친 금액 전액을 그날 가입하는 **1년 만기 정기예금**에 넣는다(008과 같은 계산)
3. 같은 날 새 적금의 첫 회를 낸다

정기예금과 적금은 늘 같은 날 만기된다. 둘 중 하나만 다시 넣으면 원금이 사라지고, 그날 넣지
않으면 이자 없이 노는 돈이 생긴다(FR-026).

**적금 이자는 회차마다 단리다**(FR-025).
- 회차 i(0..11)의 이자 = 월 납입액 × 연 금리 × (12 − i) ÷ 1200
- 만기 이자는 그 합을 한 번 버린다 — 12회를 다 내면 월 납입액 × 연 금리 × 78 ÷ 1200이다
- 모든 회차에 12개월을 붙이면 이자가 약 두 배로 부푼다

**경과 평가**(FR-028, R11-8).
- 적금 쪽 = 낸 회차의 합 + trunc(Σᵢ 회차 이자ᵢ × 경과ᵢ ÷ 기간ᵢ) − 그 세금
  - 기간ᵢ = 회차일 ~ 만기일 일수, 경과ᵢ = 회차일 ~ 그날 일수
  - 회차마다 세후로 나눠 버리면 버림이 회차마다 일어나 만기 금액과 1원씩 어긋난다
- 정기예금 쪽은 008의 `accrued_interest`다
- 만기일의 평가는 실제로 받는 만기 금액의 합과 같다

**금리**는 가입 달의 금리로 그 계약 내내 고정이다. 적금·정기예금 모두 008의 해석기
(`rate_resolver`)를 쓴다.
- 미발표 달은 마지막 발표 달 금리로 **잠정**이다
- 발표 범위 안의 빈 달은 **결측**이다. 첫 적금 가입 달이면 계산하지 않고(`RateMissing`), 그 뒤의
  가입 달이면 그 만기일에서 멈춘다(`Stopped`) — 보간하지 않는다(헌법 원칙 V)

**순수 함수 모듈이다.** `repository`·`api`·`db`를 임포트하지 않는다(헌법 원칙 IV). 계산은
`Decimal`이다(헌법 원칙 VI).
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from decimal import ROUND_DOWN, Decimal, localcontext
from typing import Literal

from src.simulation.contribution_schedule import months_later
from src.simulation.deposit_rollover import (
    BeforeFirstMonth,
    RateMissing,
    ResolvedRate,
    Stopped,
    accrued_interest,
    add_one_year,
    interest_tax,
    maturity_interest,
    rate_resolver,
)
from src.simulation.money import CALC_PRECISION, quantize_rate

#: 적금 하나의 납입 횟수 — 1년 만기·매달(FR-024).
INSTALLMENTS = 12

_ZERO = Decimal(0)
_MONTHS_PER_YEAR_PERCENT = Decimal(1200)

RowKind = Literal["installment", "month", "installment_maturity", "deposit_maturity",
                  "deposit_join"]


@dataclass(frozen=True, slots=True)
class InstallmentContract:
    """만기된 적금 하나."""

    no: int
    joined_on: dt.date
    matures_on: dt.date
    rate: Decimal
    #: 그 금리의 달. 잠정이면 대신 쓴 달(마지막 발표 달)이다.
    rate_month: dt.date
    provisional: bool
    monthly: Decimal
    paid: int
    interest: Decimal
    tax: Decimal
    after_tax: Decimal
    #: 만기 금액 = 납입 합 + 세후 이자.
    amount: Decimal


@dataclass(frozen=True, slots=True)
class OpenInstallment:
    """계산 끝에 진행 중인 적금. `paid`는 계산 끝까지 낸 회차 수다."""

    no: int
    joined_on: dt.date
    matures_on: dt.date
    rate: Decimal
    rate_month: dt.date
    provisional: bool
    paid: int


@dataclass(frozen=True, slots=True)
class LadderDeposit:
    """만기된 정기예금 하나. 원금 = 앞 정기예금의 만기 금액 + 그날 만기된 적금의 만기 금액."""

    no: int
    joined_on: dt.date
    matures_on: dt.date
    rate: Decimal
    rate_month: dt.date
    provisional: bool
    principal: Decimal
    from_deposit: Decimal
    from_installment: Decimal
    interest: Decimal
    tax: Decimal
    after_tax: Decimal


@dataclass(frozen=True, slots=True)
class OpenDeposit:
    no: int
    joined_on: dt.date
    matures_on: dt.date
    rate: Decimal
    rate_month: dt.date
    provisional: bool
    principal: Decimal


@dataclass(frozen=True, slots=True)
class LadderRow:
    """표의 행. 평가 칸(`installment_value`·`deposit_value`·`balance`)은 **그 사건 뒤**의 값이다.
    해당이 없는 칸은 `None`이다.

    `contract_no`는 그 행의 계약 번호다 — 적금 행(납입·적금 만기)은 적금, 정기예금 행(만기·가입)은
    정기예금의 번호다.
    """

    date: dt.date
    kind: RowKind
    #: 그때까지의 총 납입 원금(새 돈만).
    contributed: Decimal
    installment_value: Decimal
    deposit_value: Decimal
    balance: Decimal
    profit: Decimal
    return_rate: Decimal
    provisional: bool
    contract_no: int | None = None
    #: 납입 행만 — 회차 1..12.
    installment_no: int | None = None
    #: 납입액 · 만기 금액 · 정기예금 원금.
    amount: Decimal | None = None
    rate: Decimal | None = None
    rate_month: dt.date | None = None
    #: 만기 행만.
    interest: Decimal | None = None
    tax: Decimal | None = None
    after_tax: Decimal | None = None
    #: 정기예금 가입 행만 — 원금의 구성.
    from_deposit: Decimal | None = None
    from_installment: Decimal | None = None


@dataclass(frozen=True, slots=True)
class LadderSummary:
    contributed: Decimal
    #: 낸 회차 수 — 총 납입 원금 = 월 납입액 × 이 값.
    installments: int
    #: 만기된 계약(적금 + 정기예금)의 이자·세금·세후 이자 합. 세후 이자는 적금·정기예금으로도 나눠
    #: 둔다.
    interest_total: Decimal
    tax_total: Decimal
    after_tax_total: Decimal
    installment_after_tax: Decimal
    deposit_after_tax: Decimal
    #: 기준일 평가(경과 이자 포함). 멈췄으면 그날 받은 만기 금액이다.
    installment_value: Decimal
    deposit_value: Decimal
    balance: Decimal
    profit: Decimal
    return_rate: Decimal
    #: 계산 끝. 멈췄으면 그 만기일이다.
    as_of: dt.date
    is_final: bool
    #: 잠정 금리로 가입한 첫 계약의 가입일. 없으면 `None`.
    provisional_from: dt.date | None
    stopped: Stopped | None
    current_installment: OpenInstallment | None
    current_deposit: OpenDeposit | None
    #: 013 — 기준일에 진행 중인 적금·정기예금의 경과 이자에 대한 이자 소득세 합. 평가액
    #: (`installment_value`·`deposit_value`)에서 이미 뺀 그 값이다(비교 표의 비용 — 이미 반영된 몫,
    #: research R13-3). 멈추면 0.
    open_tax: Decimal = Decimal(0)


@dataclass(frozen=True, slots=True)
class LadderOutcome:
    #: 만기된 적금·정기예금(오름차순). 진행 중인 것은 `summary.current_*`이다.
    contracts: list[InstallmentContract]
    deposits: list[LadderDeposit]
    #: 최신순. 같은 날의 행은 나중 사건이 위다 — 새 적금 첫 회 → 정기예금 가입 → 정기예금 만기 →
    #: 적금 만기.
    rows: list[LadderRow]
    summary: LadderSummary


def _trunc(value: Decimal) -> Decimal:
    """0 쪽으로 원 미만을 버린다. `-0`을 내지 않는다."""
    out = value.to_integral_value(rounding=ROUND_DOWN)
    return _ZERO if out == 0 else out


@dataclass(slots=True)
class _Saving:
    no: int
    joined: dt.date
    matures: dt.date
    rate: ResolvedRate
    dates: list[dt.date]
    paid: int = 0


@dataclass(slots=True)
class _Deposit:
    no: int
    joined: dt.date
    matures: dt.date
    rate: ResolvedRate
    principal: Decimal
    from_deposit: Decimal
    from_installment: Decimal


@dataclass(slots=True)
class _Totals:
    contributed: Decimal = _ZERO
    installments: int = 0
    #: 멈춘 날 받은 적금·정기예금 만기 금액.
    stopped_values: tuple[Decimal, Decimal] = (_ZERO, _ZERO)


def _new_saving(no: int, joined: dt.date, rate: ResolvedRate) -> _Saving:
    """회차일은 가입일의 i개월 뒤 같은 날(없는 달은 말일, i = 0..11), 만기일은 1년 뒤다(FR-024)."""
    return _Saving(no=no, joined=joined, matures=add_one_year(joined), rate=rate,
                   dates=[months_later(joined, i) for i in range(INSTALLMENTS)])


def _saving_maturity_interest(monthly: Decimal, rate: Decimal) -> Decimal:
    """만기 이자 — trunc(Σᵢ 월 납입액 × 금리 × (12 − i) ÷ 1200). 나눗셈은 한 번이다."""
    months = sum(INSTALLMENTS - i for i in range(INSTALLMENTS))
    with localcontext() as ctx:
        ctx.prec = CALC_PRECISION
        return _trunc(monthly * rate * months / _MONTHS_PER_YEAR_PERCENT)


def _saving_accrued(saving: _Saving, monthly: Decimal, on: dt.date) -> Decimal:
    """그날까지의 경과 이자(세전) — 낸 회차마다 회차 이자 × 경과 ÷ 기간을 더한 뒤 한 번
    버린다(R11-8)."""
    if on >= saving.matures:
        return _saving_maturity_interest(monthly, saving.rate.rate)
    with localcontext() as ctx:
        ctx.prec = CALC_PRECISION
        total = _ZERO
        for i, paid_on in enumerate(saving.dates[:saving.paid]):
            period = (saving.matures - paid_on).days
            elapsed = (on - paid_on).days
            total += monthly * saving.rate.rate * (INSTALLMENTS - i) * elapsed / period
        return _trunc(total / _MONTHS_PER_YEAR_PERCENT)


def _saving_parts(saving: _Saving, monthly: Decimal, on: dt.date,
                  tax_rate: Decimal) -> tuple[Decimal, Decimal]:
    """(평가액, 경과 이자의 세금) — 평가액은 낸 회차 + 경과 이자 − 그 세금이다."""
    accrued = _saving_accrued(saving, monthly, on)
    tax = interest_tax(accrued, tax_rate)
    return monthly * saving.paid + accrued - tax, tax


def _saving_value(saving: _Saving, monthly: Decimal, on: dt.date, tax_rate: Decimal) -> Decimal:
    return _saving_parts(saving, monthly, on, tax_rate)[0]


def _deposit_parts(deposit: _Deposit | None, on: dt.date,
                   tax_rate: Decimal) -> tuple[Decimal, Decimal]:
    """(평가액, 경과 이자의 세금) — 정기예금이 없으면 둘 다 0이다."""
    if deposit is None:
        return _ZERO, _ZERO
    accrued = accrued_interest(deposit.principal, deposit.rate.rate, deposit.joined,
                               deposit.matures, on)
    tax = interest_tax(accrued, tax_rate)
    return deposit.principal + accrued - tax, tax


def _deposit_value(deposit: _Deposit | None, on: dt.date, tax_rate: Decimal) -> Decimal:
    return _deposit_parts(deposit, on, tax_rate)[0]


def _year_before(month: dt.date) -> dt.date:
    return month.replace(year=month.year - 1)


def _next_month(month: dt.date) -> dt.date:
    return month.replace(year=month.year + month.month // 12, month=month.month % 12 + 1)


def startable_from(installment_first: dt.date, deposit_first: dt.date | None) -> dt.date:
    """시작 가능 날짜 = max(적금 첫 달 1일, 정기예금 첫 달 1일의 1년 전)(FR-029). 정기예금은 첫
    만기(시작 + 1년)부터 필요하다.
    정기예금 쪽을 모르면(받지 않았으면) 적금 첫 달이다."""
    if deposit_first is None:
        return installment_first
    return max(installment_first, _year_before(deposit_first))


def simulate_installment_ladder(
    *, monthly: Decimal, start: dt.date, end: dt.date,
    installment_rates: Mapping[dt.date, Decimal], installment_first: dt.date,
    installment_latest: dt.date,
    deposit_rates: Mapping[dt.date, Decimal], deposit_first: dt.date | None,
    deposit_latest: dt.date | None,
    tax_rate: Decimal,
) -> LadderOutcome:
    """시작일부터 계산 끝(오늘, 한국 시간)까지 적금 → 정기예금 사다리를 되풀이한다.

    금리는 달(1일) → 연 금리(%)다. `*_latest`는 마지막 발표 달이고 그 뒤의 달은 미발표다. 계산 끝이
    첫 만기 전이면 정기예금 금리가
    필요 없다(`deposit_first`·`deposit_latest`가 `None`이어도 된다).
    """
    startable = startable_from(installment_first, deposit_first)
    if start < startable:
        raise BeforeFirstMonth(startable)
    if end < start:
        raise ValueError("계산 끝이 시작일보다 이르다")

    saving_rate = rate_resolver(installment_rates, installment_latest)
    deposit_rate: Callable[[dt.date], ResolvedRate] | None = (
        None if deposit_latest is None else rate_resolver(deposit_rates, deposit_latest))

    saving = _new_saving(1, start, saving_rate(start))  # 첫 가입 달이 결측이면 여기서 막힌다
    deposit: _Deposit | None = None
    provisional_from = start if saving.rate.provisional else None
    contracts: list[InstallmentContract] = []
    deposits: list[LadderDeposit] = []
    ascending: list[LadderRow] = []
    state = _Totals()
    stopped: Stopped | None = None

    def row(day: dt.date, kind: RowKind, installment_value: Decimal, deposit_value: Decimal,
            provisional: bool) -> LadderRow:
        """그 순간의 평가로 행을 만든다. 행 고유의 칸(계약·금리·이자)은 호출부가 `replace`로
        채운다."""
        balance = installment_value + deposit_value
        profit = balance - state.contributed
        with localcontext() as ctx:
            ctx.prec = CALC_PRECISION
            rate = quantize_rate(profit / state.contributed) if state.contributed > 0 else _ZERO
        return LadderRow(date=day, kind=kind, contributed=state.contributed,
                         installment_value=installment_value, deposit_value=deposit_value,
                         balance=balance, profit=profit, return_rate=rate,
                         provisional=provisional)

    def pay(day: dt.date) -> None:
        saving.paid += 1
        state.contributed += monthly
        state.installments += 1
        ascending.append(replace(
            row(day, "installment", _saving_value(saving, monthly, day, tax_rate),
                _deposit_value(deposit, day, tax_rate), saving.rate.provisional),
            contract_no=saving.no, installment_no=saving.paid, amount=monthly,
            rate=saving.rate.rate, rate_month=saving.rate.month))

    while True:
        # 계약 기간 안의 사건 — 회차 납입과 매달 1일(그날 다른 사건이 없을 때만, 008과 같다).
        due = [d for d in saving.dates if d <= end]
        firsts: list[dt.date] = []
        month = _next_month(saving.joined.replace(day=1))
        while month < saving.matures and month <= end:
            if month not in due:
                firsts.append(month)
            month = _next_month(month)
        for day in sorted({*due, *firsts}):
            if day in due:
                pay(day)
            else:
                ascending.append(row(
                    day, "month", _saving_value(saving, monthly, day, tax_rate),
                    _deposit_value(deposit, day, tax_rate),
                    saving.rate.provisional or (deposit is not None and deposit.rate.provisional)))

        matures = saving.matures
        if matures > end:
            break

        # 만기일 — 적금 만기 → 정기예금 만기 → 합쳐 정기예금 가입 → 새 적금 첫 회.
        interest = _saving_maturity_interest(monthly, saving.rate.rate)
        tax = interest_tax(interest, tax_rate)
        saving_amount = monthly * saving.paid + interest - tax
        contracts.append(InstallmentContract(
            no=saving.no, joined_on=saving.joined, matures_on=matures, rate=saving.rate.rate,
            rate_month=saving.rate.month, provisional=saving.rate.provisional, monthly=monthly,
            paid=saving.paid, interest=interest, tax=tax, after_tax=interest - tax,
            amount=saving_amount))
        deposit_amount = _ZERO
        if deposit is not None:
            d_interest = maturity_interest(deposit.principal, deposit.rate.rate)
            d_tax = interest_tax(d_interest, tax_rate)
            deposit_amount = deposit.principal + d_interest - d_tax
            deposits.append(LadderDeposit(
                no=deposit.no, joined_on=deposit.joined, matures_on=matures,
                rate=deposit.rate.rate, rate_month=deposit.rate.month,
                provisional=deposit.rate.provisional, principal=deposit.principal,
                from_deposit=deposit.from_deposit, from_installment=deposit.from_installment,
                interest=d_interest, tax=d_tax, after_tax=d_interest - d_tax))
        ascending.append(replace(
            row(matures, "installment_maturity", saving_amount, deposit_amount,
                saving.rate.provisional),
            contract_no=saving.no, amount=saving_amount, rate=saving.rate.rate,
            rate_month=saving.rate.month, interest=interest, tax=tax, after_tax=interest - tax))
        if deposit is not None:
            matured = deposits[-1]
            ascending.append(replace(
                row(matures, "deposit_maturity", saving_amount, deposit_amount,
                    deposit.rate.provisional),
                contract_no=deposit.no, amount=deposit_amount, rate=deposit.rate.rate,
                rate_month=deposit.rate.month, interest=matured.interest, tax=matured.tax,
                after_tax=matured.after_tax))

        if deposit_rate is None:
            raise ValueError(
                "정기예금 금리 없이 첫 만기에 닿았다 — 부르는 쪽이 두 계열을 받아야 한다")
        try:
            next_deposit_rate = deposit_rate(matures)
            next_saving_rate = saving_rate(matures)
        except RateMissing as exc:
            # 그 뒤의 가입 달이 결측이면 그 만기일에서 멈춘다 — 보간하지 않는다(헌법 원칙 V,
            # FR-030).
            stopped = Stopped(date=matures, reason="rate_missing", month=exc.month)
            state.stopped_values = (saving_amount, deposit_amount)
            break

        principal = saving_amount + deposit_amount
        deposit = _Deposit(no=len(deposits) + 1, joined=matures, matures=add_one_year(matures),
                           rate=next_deposit_rate, principal=principal,
                           from_deposit=deposit_amount, from_installment=saving_amount)
        ascending.append(replace(
            row(matures, "deposit_join", _ZERO, principal, next_deposit_rate.provisional),
            contract_no=deposit.no, amount=principal, rate=next_deposit_rate.rate,
            rate_month=next_deposit_rate.month, from_deposit=deposit_amount,
            from_installment=saving_amount))
        if provisional_from is None and (next_deposit_rate.provisional
                                         or next_saving_rate.provisional):
            provisional_from = matures
        saving = _new_saving(saving.no + 1, matures, next_saving_rate)

    open_tax = _ZERO
    if stopped is not None:
        installment_value, deposit_value = state.stopped_values
        as_of = stopped.date
        current_installment: OpenInstallment | None = None
        current_deposit: OpenDeposit | None = None
    else:
        installment_value, installment_tax = _saving_parts(saving, monthly, end, tax_rate)
        deposit_value, deposit_tax = _deposit_parts(deposit, end, tax_rate)
        open_tax = installment_tax + deposit_tax
        as_of = end
        current_installment = OpenInstallment(
            no=saving.no, joined_on=saving.joined, matures_on=saving.matures,
            rate=saving.rate.rate, rate_month=saving.rate.month,
            provisional=saving.rate.provisional, paid=saving.paid)
        current_deposit = None if deposit is None else OpenDeposit(
            no=deposit.no, joined_on=deposit.joined, matures_on=deposit.matures,
            rate=deposit.rate.rate, rate_month=deposit.rate.month,
            provisional=deposit.rate.provisional, principal=deposit.principal)

    balance = installment_value + deposit_value
    profit = balance - state.contributed
    with localcontext() as ctx:
        ctx.prec = CALC_PRECISION
        return_rate = quantize_rate(profit / state.contributed)
    installment_after_tax = sum((c.after_tax for c in contracts), _ZERO)
    deposit_after_tax = sum((d.after_tax for d in deposits), _ZERO)
    summary = LadderSummary(
        contributed=state.contributed, installments=state.installments,
        interest_total=sum((c.interest for c in contracts), _ZERO)
        + sum((d.interest for d in deposits), _ZERO),
        tax_total=sum((c.tax for c in contracts), _ZERO) + sum((d.tax for d in deposits), _ZERO),
        after_tax_total=installment_after_tax + deposit_after_tax,
        installment_after_tax=installment_after_tax, deposit_after_tax=deposit_after_tax,
        installment_value=installment_value, deposit_value=deposit_value, balance=balance,
        profit=profit, return_rate=return_rate, as_of=as_of, is_final=stopped is None,
        provisional_from=provisional_from, stopped=stopped,
        current_installment=current_installment, current_deposit=current_deposit,
        open_tax=open_tax)
    return LadderOutcome(contracts=contracts, deposits=deposits,
                         rows=list(reversed(ascending)), summary=summary)

