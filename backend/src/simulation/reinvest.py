"""배당 재투자 시뮬레이션 (T034, T035) — 005 FR-006~014, 헌법 원칙 IV·VI.

**순수 함수 모듈이다.** `repository`·`api`·`db`·`ingestion`을 임포트하지 않는다. 이
경계가 원칙 VI 이식의 안전장치이기도 하다 — 참조 구현(Google Apps Script)과 같은
입력을 넣어 같은 출력이 나오는지 **단위 테스트로** 확인할 수 있고, 정밀도 차이가 다른
실패에 묻히지 않는다.

**원주가로 계산한다**(FR-011). 수정주가는 배당·분할을 소급 반영한 값이라 거기에 배당을
또 더하면 같은 배당이 두 번 들어간다. 값은 그럴듯하고 차트도 매끄러워 알아챌 신호가
없다. 수정주가를 가리키는 이름이 이 파일에 등장하면 안 되며, `test_no_adjusted_price`가
그것을 정적으로 막는다.

**잔고는 예수금을 포함하지 않는다**(FR-013). 총자산 = 잔고 + 예수금이다. 정수 매수라
예수금은 거의 항상 남으므로, 총자산에서 빼먹으면 **모든 행에서 조금씩 틀린다**.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from decimal import Decimal

from src.simulation.money import apply_split, buy_quantity, quantize_rate, spend_for

_ZERO = Decimal("0")


@dataclass(frozen=True, slots=True)
class DayBar:
    """하루치 시가. **원주가다.**"""

    date: dt.date
    open_price: Decimal


@dataclass(frozen=True, slots=True)
class DividendOn:
    """배당락일과 **세전** 주당 배당금. 세율은 조건에서 받는다."""

    date: dt.date
    amount_per_share: Decimal


@dataclass(frozen=True, slots=True)
class SplitOn:
    """분할·병합. 제공처가 준 그대로 적용한다 (FR-010a)."""

    date: dt.date
    numerator: int
    denominator: int


@dataclass(frozen=True, slots=True)
class Condition:
    """시뮬레이션 조건. 모두 사용자가 고르거나 설정에서 온 값이다."""

    start: dt.date
    principal: Decimal
    currency: str
    reinvest: bool
    fee_rate: Decimal
    tax_rate: Decimal


@dataclass(frozen=True, slots=True)
class Row:
    """표 한 행 (FR-024).

    `dividend_per_share`·`dividend_yield`는 **배당락 행에만 있다**(FR-026). 월 행에
    0을 넣으면 "배당이 0원"과 "배당이 없음"을 구별할 수 없다.
    """

    date: dt.date
    kind: str  # "month_first" | "dividend"
    open_price: Decimal
    bought_shares: int
    held_shares: int
    cash: Decimal
    principal: Decimal
    balance: Decimal
    profit: Decimal
    return_rate: Decimal
    dividend_per_share: Decimal | None = None
    dividend_yield: Decimal | None = None


def _month_first_dates(bars: list[DayBar], start: dt.date) -> set[dt.date]:
    """각 달의 첫 거래일. 시작 월 이전은 제외한다.

    달력상의 1일이 아니라 **실제 거래일**이다(FR-028). 휴장일을 기준으로 삼으면 그
    날짜의 시세가 없어 행을 만들 수 없다.
    """
    firsts: dict[tuple[int, int], dt.date] = {}
    start_key = (start.year, start.month)
    for bar in bars:
        key = (bar.date.year, bar.date.month)
        if key < start_key:
            continue
        if key not in firsts:
            firsts[key] = bar.date
    return set(firsts.values())


def simulate(
    bars: list[DayBar],
    dividends: list[DividendOn],
    splits: list[SplitOn],
    condition: Condition,
) -> list[Row]:
    """일별 시세·배당·분할과 조건에서 표 행을 만든다. **최신순으로 돌려준다.**

    시세가 없는 날은 행을 만들지 않는다 — 없는 값을 만들어 채우지 않는다
    (헌법 원칙 V, FR-042).

    같은 날 배당과 분할이 겹치면 **분할을 먼저 적용하고 배당을 계산한다**. 배당은
    분할 후 주식 수에 붙는다 (spec Assumptions).
    """
    ordered = sorted(bars, key=lambda b: b.date)
    by_split = {s.date: s for s in splits}
    by_dividend: dict[dt.date, Decimal] = {}
    for d in dividends:
        # 같은 날 여러 배당은 합산해 하나로 다룬다 (spec Assumptions).
        by_dividend[d.date] = by_dividend.get(d.date, _ZERO) + d.amount_per_share

    month_firsts = _month_first_dates(ordered, condition.start)

    held = 0
    cash = _ZERO
    invested = False
    rows: list[Row] = []

    for bar in ordered:
        if bar.date < condition.start.replace(day=1):
            continue

        # (0) 분할을 먼저 적용한다. 배당은 분할 후 주식 수에 붙는다.
        split = by_split.get(bar.date)
        if split is not None:
            held = apply_split(held, split.numerator, split.denominator)

        is_month_first = bar.date in month_firsts

        # (1) 초기 1회 매수 (FR-006). 시작 월의 첫 거래일에만 일어난다.
        bought_initial = 0
        if is_month_first and not invested:
            cash += condition.principal
            invested = True
            bought_initial = buy_quantity(cash, bar.open_price, condition.fee_rate)
            if bought_initial > 0:
                held += bought_initial
                cash -= spend_for(bought_initial, bar.open_price, condition.fee_rate)

        # (2) 배당 — 하루 시작 시점 보유 수가 아니라 **분할·초기 매수 반영 후**의 수다.
        per_share = by_dividend.get(bar.date)
        if per_share is not None and per_share > 0 and invested:
            net = Decimal(held) * per_share * (Decimal("1") - condition.tax_rate)
            cash += net

            bought_reinvest = 0
            if condition.reinvest:
                # 예수금 **전액**으로 그날 시가에 정수 매수한다 (FR-008).
                bought_reinvest = buy_quantity(
                    cash, bar.open_price, condition.fee_rate)
                if bought_reinvest > 0:
                    held += bought_reinvest
                    cash -= spend_for(
                        bought_reinvest, bar.open_price, condition.fee_rate)

            rows.append(_row(
                bar, "dividend", bought_reinvest, held, cash, condition,
                dividend_per_share=per_share))

        # (3) 월 첫 거래일 스냅샷 (FR-025).
        if is_month_first:
            rows.append(_row(bar, "month_first", bought_initial, held, cash, condition))

    rows.sort(key=lambda r: r.date, reverse=True)
    return rows


def _row(
    bar: DayBar,
    kind: str,
    bought: int,
    held: int,
    cash: Decimal,
    condition: Condition,
    *,
    dividend_per_share: Decimal | None = None,
) -> Row:
    """한 행을 만든다.

    **총자산 = 잔고 + 예수금**이다. 예수금을 빼먹으면 수익률이 실제보다 낮게 나오고,
    정수 매수라 예수금이 거의 항상 남아 모든 행에서 조금씩 틀린다 (FR-013).
    """
    balance = Decimal(held) * bar.open_price
    profit = balance + cash - condition.principal
    rate = (
        quantize_rate(profit / condition.principal)
        if condition.principal > 0 else _ZERO
    )
    yield_rate = (
        quantize_rate(dividend_per_share / bar.open_price)
        if dividend_per_share is not None and bar.open_price > 0 else None
    )
    return Row(
        date=bar.date,
        kind=kind,
        open_price=bar.open_price,
        bought_shares=bought,
        held_shares=held,
        cash=cash,
        principal=condition.principal,
        balance=balance,
        profit=profit,
        return_rate=rate,
        dividend_per_share=dividend_per_share,
        dividend_yield=yield_rate,
    )
