"""주식 적립식 (011 T024) — FR-006~FR-011, FR-014, research R11-4, 분석 B1.

**순수 함수 모듈이다.** `repository`·`api`·`db`·`ingestion`을 임포트하지 않는다(헌법 원칙 IV).
일시금(`reinvest.py`)은 고치지 않는다 — 참조 구현 대조가 그 모듈을 고정한다. 계산
부품(`buy_quantity`·`spend_for`·`apply_split`·`quantize_rate`)은 함께 쓴다.

**원주가로 계산한다**(005 FR-011). 매수는 시가, 잔고 평가는 종가다(010 FR-028).

**돈의 칸이 둘이다.**
- **매수 대기금**: 납입과 재투자일에 옮겨 온 배당이다. 매수는 늘 이 칸만 쓴다. 1주 + 수수료에 못
  미치면 사지 않고 모으고, 남은 돈은 다음 매수에
  쓴다 — 버리면 원금이 조금씩 사라진다(FR-007).
- **배당 현금**: 아직 매수 대기금에 들어가지 않은 세후 배당이다. 배당은 늘 배당락일에 여기로
  들어온다.
  - 재투자 켬이면 그 배당의 금액만 재투자일(배당락일 뒤 `reinvest_lag_days`번째 거래일)에 매수
    대기금으로 옮긴다.
  - 재투자 끔이면 옮기지 않는다.
  - 재투자일 전의 정기 매수는 그 배당을 쓰지 않는다(분석 B1, 사용자 결정 2026-10-06). 배당락일에
    매수 대기금에 넣으면 매일·매주 적립의 다음 매수가
    재투자일보다 먼저 배당을 써 버려 재투자 시점이 조용히 바뀐다. 재투자를 껐는데 섞이면 재투자와
    같아진다(FR-008).

**하루의 순서**: (0) 분할 → (1) 납입과 매수 → (2) 배당(그날 아침 보유 수 — 그날 산 주식에는 붙지
않는다) → (3) 재투자일이면 옮기고 산다 → (4) 그 달 첫 거래일 행(그날 납입이 없을 때만). 같은 날의
사건은 행이 따로다. 표는 최신순이고, 같은 날 안에서도 나중 사건이 위다.

총자산 = 잔고(보유 × 종가) + 매수 대기금 + 배당 현금이다. 행의 `profit`·`return_rate`는 **종목 통화
기준**(납입한 종목 통화 금액의 합 대비)이다. 해외 종목은 서비스가 그 행의 매매기준율과 원화
분모(`basis_krw`)로 다시 평가한다 — 일시금(`_evaluate`)과 같은 방식이다.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Sequence
from dataclasses import dataclass, replace
from decimal import Decimal
from typing import Literal

from src.simulation.contribution_schedule import Contribution, FxKind
from src.simulation.money import apply_split, buy_quantity, quantize_rate, spend_for
from src.simulation.reinvest import DayBar, DividendOn, SplitOn

_ZERO = Decimal("0")

#: `day`는 표 행이 아니다 — 일봉마다의 상태(012 `RecurringOutcome.daily`)다.
RowKind = Literal["contribution", "dividend", "reinvest", "month_first", "latest", "day"]


@dataclass(frozen=True, slots=True)
class RecurringCondition:
    """적립식 조건. 수수료율·배당 소득세율은 설정, 재투자 여부는 사용자가 고른 값이다."""

    fee_rate: Decimal
    tax_rate: Decimal
    reinvest: bool
    #: 재투자 매수는 배당락일 뒤 몇 번째 거래일인가(006 FR-058 — 화면은 2). **기본값을 두지 않는다**
    #: — 빠뜨리면 조용히 당일 재투자가 된다.
    reinvest_lag_days: int


@dataclass(frozen=True, slots=True)
class RecurringRow:
    """표 한 행. 해당이 없는 칸은 `None`이다 — "수수료 0"과 "매수 없음", "배당 0"과 "배당 없음"을
    구별한다."""

    date: dt.date
    kind: RowKind
    open_price: Decimal
    close_price: Decimal
    bought_shares: int
    held_shares: int
    #: 매수 대기금(종목 통화).
    pending: Decimal
    #: 배당 현금(종목 통화).
    dividend_cash: Decimal
    #: 그때까지 넣은 금액의 합(종목 통화)과 원화 분모, 넣은 예정일 수.
    contributed: Decimal
    basis_krw: Decimal
    contributions: int
    #: 잔고 = 보유 × 종가.
    balance: Decimal
    #: 총자산 = 잔고 + 매수 대기금 + 배당 현금.
    total: Decimal
    #: 종목 통화 기준 — 총자산 − 넣은 금액의 합, 그 비율. 해외 종목은 서비스가 원화로 다시 평가한다.
    profit: Decimal
    return_rate: Decimal
    #: 납입 행만 — 그 행의 납입액(종목 통화 — 모인 예정일만큼)과 그 행으로 미뤄진 원래 예정일(그날
    #: 예정분 제외).
    contribution: Decimal | None = None
    deferred: tuple[dt.date, ...] = ()
    #: 납입 행의 환전·평가 환율(`Contribution`에서 그대로).
    fx_rate: Decimal | None = None
    fx_rate_date: dt.date | None = None
    fx_kind: FxKind | None = None
    #: 매수가 있는 행의 수수료(종목 통화).
    trade_fee: Decimal | None = None
    #: 배당 행만.
    dividend_per_share: Decimal | None = None
    dividend_total: Decimal | None = None
    dividend_tax: Decimal | None = None
    dividend_total_net: Decimal | None = None


@dataclass(frozen=True, slots=True)
class RecurringOutcome:
    """결과 전체. `rows`는 최신순이고 `latest`는 마지막 거래일의 평가다 — 보드는 이것을 쓴다(표의
    마지막 행이 아니다)."""

    rows: list[RecurringRow]
    latest: RecurringRow | None
    #: 매수 수수료의 합(종목 통화). 원화 합은 서비스가 행마다 그 행의 환율로 바꿔 더한다.
    buy_fee_total: Decimal
    #: 012 — 첫 납입일부터 일봉마다 그날 사건을 모두 처리한 뒤의 상태(오름차순, `kind = "day"`).
    #: 일·주·월 표가 쓴다(research R12-4).
    #: `rows`·`latest`와 따로 둔다 — 차트·보드의 재료가 바뀌지 않는다.
    daily: tuple[RecurringRow, ...] = ()


@dataclass(slots=True)
class _State:
    held: int = 0
    pending: Decimal = _ZERO
    dividend_cash: Decimal = _ZERO
    contributed: Decimal = _ZERO
    basis_krw: Decimal = _ZERO
    contributions: int = 0


def _fee(bought: int, price: Decimal, fee_rate: Decimal) -> Decimal | None:
    return Decimal(bought) * price * fee_rate if bought > 0 else None


def _row(bar: DayBar, kind: RowKind, s: _State, *, bought: int = 0,
         fee_rate: Decimal) -> RecurringRow:
    """그 순간의 상태로 행을 만든다. 행 고유의 칸(납입·배당)은 호출부가 `dataclasses.replace`로
    채운다."""
    balance = Decimal(s.held) * bar.close_price
    total = balance + s.pending + s.dividend_cash
    profit = total - s.contributed
    rate = quantize_rate(profit / s.contributed) if s.contributed > 0 else _ZERO
    return RecurringRow(
        date=bar.date, kind=kind, open_price=bar.open_price, close_price=bar.close_price,
        bought_shares=bought, held_shares=s.held, pending=s.pending, dividend_cash=s.dividend_cash,
        contributed=s.contributed, basis_krw=s.basis_krw, contributions=s.contributions,
        balance=balance, total=total, profit=profit, return_rate=rate,
        trade_fee=_fee(bought, bar.open_price, fee_rate))


def _buy(s: _State, bar: DayBar, fee_rate: Decimal) -> int:
    """매수 대기금 **전액**으로 그날 시가에 살 수 있는 최대 정수 주식을 산다(수수료 포함)."""
    bought = buy_quantity(s.pending, bar.open_price, fee_rate)
    if bought > 0:
        s.held += bought
        s.pending -= spend_for(bought, bar.open_price, fee_rate)
    return bought


def simulate_recurring_stock(bars: Sequence[DayBar], dividends: Sequence[DividendOn],
                             splits: Sequence[SplitOn], contributions: Sequence[Contribution],
                             condition: RecurringCondition) -> RecurringOutcome:
    """일봉·배당·분할·납입에서 표 행을 만든다. 시세가 없는 날은 행을 만들지 않는다(헌법 원칙 V)."""
    ordered = sorted(bars, key=lambda b: b.date)
    by_contribution = {c.on: c for c in contributions}
    by_dividend: dict[dt.date, Decimal] = {}
    for d in dividends:
        # 같은 날 여러 배당은 합산해 하나로 다룬다(005 spec Assumptions와 같다).
        by_dividend[d.date] = by_dividend.get(d.date, _ZERO) + d.amount_per_share
    # 분할 적용일이 거래일 목록에 없어도 사라지지 않게 날짜 순으로 "지나간 분할"을
    # 적용한다(reinvest.py와 같은 이유).
    pending_splits = sorted(splits, key=lambda s: s.date)
    next_split = 0
    month_seen: set[tuple[int, int]] = set()
    # 재투자일(거래일 순번) → 그날 매수 대기금으로 옮길 배당 금액. 배당마다 자기 재투자일이 있다.
    reinvest_due: dict[int, Decimal] = {}
    lag = condition.reinvest_lag_days
    fee_rate = condition.fee_rate

    s = _State()
    events: list[RecurringRow] = []
    daily: list[RecurringRow] = []
    buy_fees = _ZERO
    started = False

    for index, bar in enumerate(ordered):
        while next_split < len(pending_splits) and pending_splits[next_split].date <= bar.date:
            split = pending_splits[next_split]
            s.held = apply_split(s.held, split.numerator, split.denominator)
            next_split += 1

        held_at_open = s.held
        month = (bar.date.year, bar.date.month)
        first_of_month = month not in month_seen
        month_seen.add(month)

        # (1) 납입과 매수 — 매수 대기금만 쓴다.
        paid = by_contribution.get(bar.date)
        if paid is not None:
            started = True
            s.pending += paid.amount
            s.contributed += paid.amount
            s.basis_krw += paid.basis_krw
            s.contributions += len(paid.scheduled)
            bought = _buy(s, bar, fee_rate)
            fee = _fee(bought, bar.open_price, fee_rate)
            if fee is not None:
                buy_fees += fee
            events.append(replace(
                _row(bar, "contribution", s, bought=bought, fee_rate=fee_rate),
                contribution=paid.amount,
                deferred=tuple(d for d in paid.scheduled if d != bar.date),
                fx_rate=paid.fx_rate, fx_rate_date=paid.fx_rate_date, fx_kind=paid.fx_kind))

        if not started:
            continue

        # (2) 배당 — 그날 아침 보유 수에 붙는다. 세후 배당은 배당 현금으로(매수에 쓰이지 않는다).
        per_share = by_dividend.get(bar.date)
        if per_share is not None and per_share > 0 and held_at_open > 0:
            gross = Decimal(held_at_open) * per_share
            tax = gross * condition.tax_rate
            net = gross - tax
            s.dividend_cash += net
            if condition.reinvest:
                due = index + lag
                if due < len(ordered):
                    reinvest_due[due] = reinvest_due.get(due, _ZERO) + net
                # 재투자일이 계산 끝 뒤면 옮기지 않는다 — 배당 현금으로 남는다(일시금과 같다).
            events.append(replace(
                _row(bar, "dividend", s, fee_rate=fee_rate), dividend_per_share=per_share,
                dividend_total=gross, dividend_tax=tax, dividend_total_net=net))

        # (3) 재투자일 — 그 배당 금액을 매수 대기금으로 옮기고 매수 대기금 전액으로 산다.
        # 사지 못해도 옮긴 사실을 행으로 남긴다.
        moving = reinvest_due.pop(index, None)
        if moving is not None:
            s.dividend_cash -= moving
            s.pending += moving
            bought = _buy(s, bar, fee_rate)
            fee = _fee(bought, bar.open_price, fee_rate)
            if fee is not None:
                buy_fees += fee
            events.append(_row(bar, "reinvest", s, bought=bought, fee_rate=fee_rate))

        # (4) 그 달 첫 거래일 — 그날 납입 행이 그날의 상태를 이미 보이면 두지 않는다.
        if first_of_month and paid is None:
            events.append(_row(bar, "month_first", s, fee_rate=fee_rate))

        # (5) 012 — 그날의 상태. 그날 마지막 사건 행·그 달 첫 거래일 행과 같은 시점이다.
        daily.append(_row(bar, "day", s, fee_rate=fee_rate))

    latest = _row(ordered[-1], "latest", s, fee_rate=fee_rate) if ordered and started else None
    events.reverse()
    return RecurringOutcome(rows=events, latest=latest, buy_fee_total=buy_fees, daily=tuple(daily))
