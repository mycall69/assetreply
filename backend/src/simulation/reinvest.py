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
    """하루치 시가와 종가. **원주가다.** 매수는 시가, 잔고 평가는 종가다(010 FR-028 — 005는 시가로
    평가했다).

    종가는 필수다 — 없으면 시가로 메우지 않는다. 시가와 종가는 같은 일봉에서 온다(헌법 원칙 V).
    """

    date: dt.date
    open_price: Decimal
    close_price: Decimal


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
    # : 재투자 매수를 배당락일 뒤 몇 번째 거래일에 하는가 (006 FR-058). 0이면 배당락일 당일이다(005
    # FR-008) — : 참조 구현 대조가 그것을 쓴다. 화면은 2다. **기본값을 두지 않는다** — 빠뜨리면
    # 조용히 당일 재투자가 된다.
    reinvest_lag_days: int


@dataclass(frozen=True, slots=True)
class Row:
    """표 한 행 (FR-024).

    `dividend_per_share`·`dividend_yield`는 **배당락 행에만 있다**(FR-026). 월 행에
    0을 넣으면 "배당이 0원"과 "배당이 없음"을 구별할 수 없다.

    006 FR-059 — `dividend_tax`(배당락 행: 세전 배당 × 세율)와 `trade_fee`(매수가 있는 행: 수량 ×
    시가 × 수수료율)도 같은 규약이다. 해당이 없으면 `None`이다.

    006 FR-067 — `dividend_total`(세전 = 배당락일 보유 수 × 주당 배당금)과 `dividend_total_net`(세후
    — 예수금에 실제로 들어온 금액)도 배당락 행에만 있다. 세전 − 세후가 그 행의 세금이다.
    """

    date: dt.date
    #: "month_first" | "dividend" | "reinvest"(006 FR-058) | "day"(012 — 하루하루 상태,
    #: `Outcome.daily`)
    kind: str
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
    dividend_tax: Decimal | None = None
    trade_fee: Decimal | None = None
    dividend_total: Decimal | None = None
    dividend_total_net: Decimal | None = None
    #: 그 행 날짜의 원주가 종가 — 잔고 평가의 가격(010 FR-028). 계산이 만든 행에는 늘 있다. 기본값은
    #: 행을 직접 만드는 기존 테스트(005 `test_stock_series_build`)를 위한 것이고 잔고는 이 값을 쓰지
    #: 않는다.
    close_price: Decimal | None = None


def _fee(bought: int, price: Decimal, fee_rate: Decimal) -> Decimal | None:
    """그 매수의 수수료. 사지 않았으면 `None`이다 — "수수료 0"과 "매수 없음"을 구별한다."""
    return Decimal(bought) * price * fee_rate if bought > 0 else None


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


@dataclass(frozen=True, slots=True)
class Outcome:
    """시뮬레이션 결과 전체.

    `latest`는 **마지막 거래일의 상태**다. 표에는 넣지 않는다 — 행의 종류는 월 첫
    거래일과 배당락일 둘뿐이다(FR-025).

    따로 두는 이유는 보드가 거짓말을 하지 않기 위해서다. 요약을 표의 마지막 행에서
    가져오면 "10월 1일 기준"이라 적어 두고 **그 달 첫 거래일의 수치**를 보여주게 된다.
    사용자가 묻는 것은 "지금 얼마가 됐나"이고, 그 답은 마지막 거래일의 값이다.
    """

    rows: list[Row]
    latest: Row | None
    #: 012 — 첫 매수일부터 일봉마다 그날 사건(분할·매수·배당·재투자)을 모두 처리한 뒤의
    #: 상태(오름차순, `kind = "day"`). 일·주·월 표가 쓴다
    #: (research R12-4). **`rows`·`latest`와 따로 둔다** — `rows`는 주식 차트의 재료라 일 행을
    #: 넣으면 차트가 바뀐다(012 FR-007). 매수일에만
    #: `bought_shares`·`trade_fee`가 있다(그날의 월 행과 같다). 기본값이 빈 튜플인 이유: 결과를
    #: 손으로 만드는 테스트가 있다.
    daily: tuple[Row, ...] = ()


def simulate(
    bars: list[DayBar],
    dividends: list[DividendOn],
    splits: list[SplitOn],
    condition: Condition,
) -> list[Row]:
    """표 행만 돌려주는 얇은 겉면. 계산은 `simulate_detailed`가 한다."""
    return simulate_detailed(bars, dividends, splits, condition).rows


def simulate_detailed(
    bars: list[DayBar],
    dividends: list[DividendOn],
    splits: list[SplitOn],
    condition: Condition,
) -> Outcome:
    """일별 시세·배당·분할과 조건에서 표 행을 만든다. **최신순으로 돌려준다.**

    시세가 없는 날은 행을 만들지 않는다 — 없는 값을 만들어 채우지 않는다
    (헌법 원칙 V, FR-042).

    같은 날 배당과 분할이 겹치면 **분할을 먼저 적용하고 배당을 계산한다**. 배당은
    분할 후 주식 수에 붙는다 (spec Assumptions).
    """
    ordered = sorted(bars, key=lambda b: b.date)
    # **적용일로 맵을 만들지 않는다.** 분할 적용일이 우리가 가진 거래일 목록에
    # 없으면(휴일이거나 그 날짜를 받지 못했으면) 분할이 조용히 사라지고, 보유 주식이
    # 배수로 틀리는데 오류가 나지 않는다. 날짜 순으로 훑으며 "지나간 분할"을 적용한다.
    pending_splits = sorted(splits, key=lambda s: s.date)
    next_split = 0
    by_dividend: dict[dt.date, Decimal] = {}
    for d in dividends:
        # 같은 날 여러 배당은 합산해 하나로 다룬다 (spec Assumptions).
        by_dividend[d.date] = by_dividend.get(d.date, _ZERO) + d.amount_per_share

    month_firsts = _month_first_dates(ordered, condition.start)

    held = 0
    cash = _ZERO
    invested = False
    rows: list[Row] = []
    daily: list[Row] = []
    # 006 FR-058 — 재투자 매수가 걸린 거래일의 순번. **거래일로 센다** — 달력일로 세면 휴장일에
    # 매수가 걸려 시가가 없고 매수가 조용히 사라진다. 기간 밖이면 걸지 않는다(예수금으로 남는다).
    reinvest_due: set[int] = set()
    lag = condition.reinvest_lag_days

    for index, bar in enumerate(ordered):
        if bar.date < condition.start.replace(day=1):
            continue

        # (0) 이 거래일까지의 분할을 먼저 적용한다. 배당은 분할 후 주식 수에 붙는다.
        while (next_split < len(pending_splits)
               and pending_splits[next_split].date <= bar.date):
            split = pending_splits[next_split]
            held = apply_split(held, split.numerator, split.denominator)
            next_split += 1

        # **배당은 그날 시작 시점의 보유 수에 붙는다.** 배당락일은 배당 권리 없이
        # 거래가 시작되는 날이므로, 그날 산 주식에는 배당이 붙지 않는다. 매수 뒤의
        # 수로 계산하면 처음부터 있던 주식처럼 배당이 붙어 **시작 월이 배당 달인
        # 조건에서 수익이 부풀려진다** — 값은 그럴듯하고 오류도 나지 않는다.
        # 참조 구현의 `sharesAtDiv`가 같은 자리다.
        held_at_open = held

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

        # (2) 배당 — **분할은 반영하고 그날의 매수는 반영하지 않은** 보유 수다. 세후 배당은
        # 배당락일에 예수금에 들어온다(006 FR-058). 세금은 행에 남긴다(006 FR-059).
        per_share = by_dividend.get(bar.date)
        if per_share is not None and per_share > 0 and invested:
            gross = Decimal(held_at_open) * per_share
            tax = gross * condition.tax_rate
            # 세후는 세전 − 세금이다. 따로 곱하면 세 숫자(세전·세금·세후)가 서로를 설명하지 못할 수
            # 있다(FR-067).
            net = gross - tax
            cash += net

            bought_reinvest = 0
            if condition.reinvest and lag == 0:
                # 예수금 **전액**으로 그날 시가에 정수 매수한다 (005 FR-008 — 지연 0).
                bought_reinvest = buy_quantity(
                    cash, bar.open_price, condition.fee_rate)
                if bought_reinvest > 0:
                    held += bought_reinvest
                    cash -= spend_for(
                        bought_reinvest, bar.open_price, condition.fee_rate)
            elif condition.reinvest and index + lag < len(ordered):
                reinvest_due.add(index + lag)

            rows.append(_row(
                bar, "dividend", bought_reinvest, held, cash, condition,
                dividend_per_share=per_share, dividend_tax=tax,
                trade_fee=_fee(bought_reinvest, bar.open_price, condition.fee_rate),
                dividend_total=gross, dividend_total_net=net))

        # (3) 걸어 둔 재투자 — 배당락일 뒤 `lag`번째 거래일의 시가로 예수금 **전액**을 쓴다(006
        # FR-058). 월 스냅샷보다 먼저 한다 — 그날의 월 행이 재투자 뒤의 보유 수를 보이도록.
        if index in reinvest_due:
            reinvest_due.discard(index)
            bought_later = buy_quantity(cash, bar.open_price, condition.fee_rate)
            if bought_later > 0:
                held += bought_later
                cash -= spend_for(bought_later, bar.open_price, condition.fee_rate)
                rows.append(_row(
                    bar, "reinvest", bought_later, held, cash, condition,
                    trade_fee=_fee(bought_later, bar.open_price, condition.fee_rate)))

        # (4) 월 첫 거래일 스냅샷 (FR-025). 초기 매수가 있었으면 그 수수료를 남긴다(006 FR-059).
        if is_month_first:
            rows.append(_row(
                bar, "month_first", bought_initial, held, cash, condition,
                trade_fee=_fee(bought_initial, bar.open_price, condition.fee_rate)))

        # (5) 012 — 그날의 상태. 월 행과 같은 시점(그날 사건을 모두 처리한 뒤)이라 월 행이 있는 날은
        # 값이 같다.
        if invested:
            daily.append(_row(
                bar, "day", bought_initial, held, cash, condition,
                trade_fee=_fee(bought_initial, bar.open_price, condition.fee_rate)))

    rows.sort(key=lambda r: r.date, reverse=True)

    # 마지막 거래일의 상태. **매수가 아니라 평가다** — 그날 산 주식이 없으므로 0이다.
    latest = (
        _row(ordered[-1], "latest", 0, held, cash, condition)
        if ordered and invested else None
    )
    return Outcome(rows=rows, latest=latest, daily=tuple(daily))


def _row(
    bar: DayBar,
    kind: str,
    bought: int,
    held: int,
    cash: Decimal,
    condition: Condition,
    *,
    dividend_per_share: Decimal | None = None,
    dividend_tax: Decimal | None = None,
    trade_fee: Decimal | None = None,
    dividend_total: Decimal | None = None,
    dividend_total_net: Decimal | None = None,
) -> Row:
    """한 행을 만든다.

    **총자산 = 잔고 + 예수금**이다. 예수금을 빼먹으면 수익률이 실제보다 낮게 나오고,
    정수 매수라 예수금이 거의 항상 남아 모든 행에서 조금씩 틀린다 (FR-013).

    잔고 = 보유 주식 × 그 날 **종가**다(010 FR-028이 005 FR-013의 시가 평가를 대체). 배당율은 그대로
    시가로 나눈다 — 매수 가격 기준의 비율이다.
    """
    balance = Decimal(held) * bar.close_price
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
        close_price=bar.close_price,
        bought_shares=bought,
        held_shares=held,
        cash=cash,
        principal=condition.principal,
        balance=balance,
        profit=profit,
        return_rate=rate,
        dividend_per_share=dividend_per_share,
        dividend_yield=yield_rate,
        dividend_tax=dividend_tax,
        trade_fee=trade_fee,
        dividend_total=dividend_total,
        dividend_total_net=dividend_total_net,
    )
