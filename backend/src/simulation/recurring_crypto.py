"""가상자산 적립식 (011 T037) — FR-017~FR-019, research R11-6.

**순수 함수 모듈이다.** `repository`·`api`·`db`·`ingestion`을 임포트하지 않는다(헌법 원칙 IV).
일시금(`crypto_hold.py`)은 고치지 않는다 — 매수 한 번·예수금 고정을 전제로 한다(007 R7-7). 계산
부품(`buy_fraction`·`quantize_rate`)과 1일 결측 판정은 함께 쓴다.

- 납입마다 그날 시가로 **매수 대기금 전액**을 써서 산다. 수량은 소수 8자리에서 버린다(수수료 포함 —
  007 FR-026). 남은 돈은 매수 대기금에 남아 다음 납입에 쓰인다 — 버리면 원금이 조금씩 사라진다
- 잔고 = 보유 수량 × 그날 시가(007 규칙 그대로). 총자산 = 잔고 + 매수 대기금
- 행은 납입 행과 그 달 첫 일봉 행(그날 납입이 없을 때만)이다
  - 그 달 첫 일봉이 1일이 아니면 그 행이 1일을 싣는다(007 FR-030과 같은 뜻 — 납입 행이어도 같다)
  - 결측일을 채우지 않는다(헌법 원칙 V)
- 일봉마다의 평가(`daily`)는 차트가 쓴다 — 표는 행만 쓴다(007 일시금과 같다)

행의 `profit`·`return_rate`는 **코인 통화 기준**(넣은 코인 통화 금액의 합 대비)이다. 외화 시세
코인은 서비스가 그 행의 매매기준율과 원화 분모(`basis_krw`)로 다시 평가한다 — 주식 적립식과 같은
방식이다.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from decimal import Decimal, localcontext
from typing import Literal

from src.simulation.contribution_schedule import Contribution, FxKind
from src.simulation.crypto_hold import DayOpen, _missing_first_day
from src.simulation.money import CALC_PRECISION, buy_fraction, quantize_rate

_ZERO = Decimal("0")

#: `day`는 표 행이 아니다 — 일봉마다의 평가(차트·보드)다.
RowKind = Literal["contribution", "month_first", "day"]


@dataclass(frozen=True, slots=True)
class RecurringCryptoRow:
    """표 한 행. 해당이 없는 칸은 `None`이다 — "수수료 0"과 "매수 없음"을 구별한다."""

    date: dt.date
    kind: RowKind
    open_price: Decimal
    bought_quantity: Decimal
    held_quantity: Decimal
    #: 매수 대기금(코인 통화).
    pending: Decimal
    #: 그때까지 넣은 금액의 합(코인 통화)과 원화 분모, 넣은 예정일 수.
    contributed: Decimal
    basis_krw: Decimal
    contributions: int
    #: 잔고 = 보유 × 그날 시가.
    balance: Decimal
    #: 총자산 = 잔고 + 매수 대기금.
    total: Decimal
    #: 코인 통화 기준 — 총자산 − 넣은 금액의 합, 그 비율.
    profit: Decimal
    return_rate: Decimal
    #: 납입 행만 — 그 행의 납입액(코인 통화 — 모인 예정일만큼)과 그 행으로 미뤄진 원래 예정일(그날
    #: 예정분 제외).
    contribution: Decimal | None = None
    deferred: tuple[dt.date, ...] = ()
    #: 납입 행의 환전·평가 환율(`Contribution`에서 그대로).
    fx_rate: Decimal | None = None
    fx_rate_date: dt.date | None = None
    fx_kind: FxKind | None = None
    #: 매수가 있는 행의 수수료(코인 통화).
    trade_fee: Decimal | None = None
    #: 그 달 1일 일봉이 출처에 없어 다른 날이 그 달의 첫 행이면 그 1일(007 FR-030).
    first_day_missing: dt.date | None = None


@dataclass(frozen=True, slots=True)
class RecurringCryptoOutcome:
    """결과 전체. `rows`는 최신순 표 행이고, `latest`는 마지막 일봉의 평가다 — 보드는 이것을
    쓴다."""

    rows: list[RecurringCryptoRow]
    latest: RecurringCryptoRow | None
    #: 일봉마다의 평가(오름차순, 첫 납입일부터).
    daily: list[RecurringCryptoRow] = field(default_factory=list)
    #: 매수 수수료의 합(코인 통화). 원화 합은 서비스가 행마다 그 행의 환율로 바꿔 더한다.
    buy_fee_total: Decimal = _ZERO


@dataclass(slots=True)
class _State:
    held: Decimal = _ZERO
    pending: Decimal = _ZERO
    contributed: Decimal = _ZERO
    basis_krw: Decimal = _ZERO
    contributions: int = 0


def _row(bar: DayOpen, kind: RowKind, s: _State) -> RecurringCryptoRow:
    """그 순간의 상태로 행을 만든다. 행 고유의 칸(납입·매수·결측)은 호출부가 `replace`로 채운다."""
    with localcontext() as ctx:
        ctx.prec = CALC_PRECISION
        balance = s.held * bar.open_price
        total = balance + s.pending
        profit = total - s.contributed
        rate = quantize_rate(profit / s.contributed) if s.contributed > 0 else _ZERO
    return RecurringCryptoRow(
        date=bar.date, kind=kind, open_price=bar.open_price, bought_quantity=_ZERO,
        held_quantity=s.held, pending=s.pending, contributed=s.contributed,
        basis_krw=s.basis_krw, contributions=s.contributions, balance=balance, total=total,
        profit=profit, return_rate=rate)


def simulate_recurring_crypto(bars: Sequence[DayOpen], contributions: Sequence[Contribution], *,
                              fee_rate: Decimal,
                              first_available: dt.date | None) -> RecurringCryptoOutcome:
    """일봉 시가와 납입에서 표 행과 일봉마다의 평가를 만든다. 일봉이 없는 날은 행이 없다(헌법 원칙
    V).

    `bars`는 시작 월 1일부터다 — 그 달의 첫 일봉을 알아야 1일 결측을 판정한다. 첫 납입 전의 일봉은
    행도 평가도 만들지 않는다(넣은 돈이 없다). `first_available`은 출처의 첫 일봉이다 — 그 앞의
    1일은 결측이 아니라 없던 날이다.
    """
    ordered = sorted(bars, key=lambda b: b.date)
    by_contribution = {c.on: c for c in contributions}
    month_seen: set[tuple[int, int]] = set()

    s = _State()
    events: list[RecurringCryptoRow] = []
    daily: list[RecurringCryptoRow] = []
    buy_fees = _ZERO
    started = False

    for bar in ordered:
        month = (bar.date.year, bar.date.month)
        first_of_month = month not in month_seen
        month_seen.add(month)
        missing = _missing_first_day(bar.date, first_available) if first_of_month else None

        paid = by_contribution.get(bar.date)
        if paid is not None:
            started = True
            s.pending += paid.amount
            s.contributed += paid.amount
            s.basis_krw += paid.basis_krw
            s.contributions += len(paid.scheduled)
            bought = buy_fraction(s.pending, bar.open_price, fee_rate)
            fee: Decimal | None = None
            if bought > 0:
                with localcontext() as ctx:
                    ctx.prec = CALC_PRECISION
                    cost = bought * bar.open_price
                    fee = cost * fee_rate
                    s.pending = s.pending - cost - fee
                s.held += bought
                buy_fees += fee
            events.append(replace(
                _row(bar, "contribution", s), bought_quantity=bought, trade_fee=fee,
                contribution=paid.amount,
                deferred=tuple(d for d in paid.scheduled if d != bar.date),
                fx_rate=paid.fx_rate, fx_rate_date=paid.fx_rate_date, fx_kind=paid.fx_kind,
                first_day_missing=missing))

        if not started:
            continue

        # 그 달 첫 일봉 — 그날 납입 행이 그날의 상태를 이미 보이면 두지 않는다.
        if first_of_month and paid is None:
            events.append(replace(_row(bar, "month_first", s), first_day_missing=missing))
        daily.append(_row(bar, "day", s))

    events.reverse()
    return RecurringCryptoOutcome(rows=events, latest=daily[-1] if daily else None, daily=daily,
                                  buy_fee_total=buy_fees)
