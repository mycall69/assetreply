"""시뮬레이션 조회·조합 (T036) — 005 FR-005, FR-013, FR-014a, FR-029.

**계산을 직접 하지 않는다.** 재투자 시뮬레이션은 `simulation/reinvest.py`의 순수
함수를 호출만 한다 (헌법 원칙 IV). 여기서 직접 계산하면 참조 구현과의 대조가 통합
테스트가 되고, 정밀도 차이가 다른 실패에 묻힌다.

**결과를 저장하지 않는다.** 결과는 시세·배당·분할·설정·환율의 함수이고 그중 설정과
환율이 바뀐다. 저장하면 갱신 시점을 관리해야 하고, 그 관리가 틀리면 **조용히 낡은
값을 보여준다** (research R5-9).
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field, replace
from decimal import Decimal, InvalidOperation
from functools import partial

from sqlalchemy.ext.asyncio import AsyncSession

from src.api.errors import CurrencyPairNotAllowed, InvalidQuery, UnknownStock
from src.api.services.stock_fx import (
    FxUnavailable,
    InitialExchange,
    build_exchange,
    cash_buy_spread,
    fx_currency_for,
    load_rates,
)
from src.api.services.stock_selection import listing_for, register_from_price_symbol
from src.api.services.table_rows import TablePage, group_events, table_page
from src.config.settings import load_settings
from src.db.models import Stock
from src.repository import stock_price as price_repo
from src.repository.stock import find_stock, find_us_stock
from src.repository.stock_setting import SaleTaxSettings, get_sale_tax, get_settings
from src.repository.stock_setting import Settings as StockSettings
from src.search.price_symbol import US_MARKETS
from src.simulation.fx_convert import (  # noqa: E501
    RateLookup,
    evaluate_krw,
    resolve_rate,
    to_foreign,
    to_principal,
)
from src.simulation.period_table import PeriodUnit
from src.simulation.quote_finality import is_final as quote_is_final
from src.simulation.reinvest import (
    Condition,
    DayBar,
    DividendOn,
    Row,
    SplitOn,
    simulate_detailed,
)


@dataclass(frozen=True, slots=True)
class ConvertedRow:
    """KRW로 평가한 행 (005 FR-041a, 006 FR-066, FR-068).

    006 — 행의 금액(예수금·세금·수수료·잔고·배당금 총액)은 **종목 통화로 남는다.** 바뀌는 것은
    `principal`(입력한 원금), `profit`·`return_rate`(KRW 기준)와 `balance_krw`다. 005처럼 행 전체를
    원금 통화로 바꾸면 같은 행의 예수금과 세금·수수료가 사용자가 실제로 쓴 통화와 달라진다.

    `fx_rate`·`fx_rate_date`는 **그 행의 평가에 쓴** 매매기준율과 날짜다. 기준일과 날짜가 다를 수
    있다 — 주식 거래일과 환율 고시일은 일치하지 않는다 (FR-041c).
    """

    row: Row
    fx_rate: Decimal | None = None
    fx_rate_date: dt.date | None = None
    #: 잔고의 KRW 평가 — 그 행의 매매기준율. 해외 종목에만 있다 (006 FR-066).
    balance_krw: Decimal | None = None


@dataclass(frozen=True, slots=True)
class SimulationResult:
    """시뮬레이션 전체 결과. 페이지는 호출부가 자른다.

    `as_of`는 계산이 **어느 날짜까지**인지다. 시세가 끊기면 오늘이 아니다 (FR-014a).
    `is_final`은 항상 명시한다 — "확인했고 아니다"와 "확인하지 않았다"가 구별되어야
    한다.
    """

    rows: list[ConvertedRow]
    #: **마지막 거래일의 상태.** 요약은 여기서 가져온다 — 표의 마지막 행에서 가져오면
    #: "어제 기준"이라 적어 두고 그 달 첫 거래일의 수치를 보여주게 된다.
    latest: ConvertedRow | None
    as_of: dt.date | None
    is_final: bool
    exchange: InitialExchange | None = None
    #: 구간 안에서 **실제로 시세가 있는 날짜**. 차트의 결측 구간 판정에 쓴다.
    #: 행 날짜(월 첫 거래일·배당락일)로는 판정할 수 없다 — 그 사이의 거래일이
    #: 전부 비어 보여 멀쩡한 구간이 미수집으로 끊긴다 (FR-034).
    quote_dates: frozenset[dt.date] = frozenset()
    #: 원금의 KRW 값 — 원금 통화가 KRW가 아닐 때만 있다. **첫 매수일의 매매기준율**로 정한다(006
    #: FR-068, research R6-25). 행마다 바꾸면 원금이 움직여 수익률이 환율만으로 움직인다.
    principal_krw: Decimal | None = None
    #: 구간 안의 분할 기록(010 FR-008) — 시뮬레이터가 주식 수를 조정한 효력일과 비율. 차트가 원주가
    #: 선이 꺾이는 까닭을 표식으로 밝힌다. 기본값이 빈 묶음인 이유: 결과를 직접 만드는 곳(단위
    #: 테스트)이 있다.
    splits: tuple[SplitOn, ...] = ()
    #: 날짜별 원주가 종가(010 반복 1) — 차트의 수정 종가(`simulation/split_adjust`)가
    #: 쓴다. 표는 쓰지 않는다(시작가 그대로).
    closes: Mapping[dt.date, Decimal] = field(default_factory=dict)
    #: 012 — 하루하루 상태(첫 매수일부터, 오름차순). 일·주·월 표의 기간 행이 쓴다. **바꾸지 않은
    #: 행이다** — 원화 평가는 쪽에 들어간 행만
    #: `convert`로 한다(research R12-7). 차트·보드는 쓰지 않는다(`rows`·`latest` 그대로 — FR-007).
    daily: tuple[Row, ...] = ()
    #: 행을 이 결과와 같은 규칙으로 평가하는 함수 — 국내 종목은 그대로 감싼다.
    convert: Callable[[Row], ConvertedRow] = ConvertedRow


#: 원금으로 고를 수 있는 통화 (005 FR-003). 006 FR-050d — **EUR을 뺀다.** 지원 시장(국내·미국·
#: 일본) 중 유로로 거래되는 곳이 없어 어느 종목과도 조합이 되지 않는다.
PRINCIPAL_CURRENCIES = ("KRW", "USD", "JPY")

# : 재투자 매수는 배당락일 뒤 이 번째 거래일의 시가로 한다 (006 FR-058, 사용자 결정 2026-10-03).
# 시뮬레이터는 : 이 값을 매개변수로 받는다 — 참조 구현 대조는 0(당일)으로 돌린다(research R6-22).
REINVEST_LAG_TRADING_DAYS = 2
#: 형식으로 받아들이는 통화. EUR은 알지만 고를 수 없다 — 005 이력의 유로 원금 항목은 "모르는
#: 통화"가 아니라 "막힌 조합"으로 답해야 사용자가 할 일을 안다(FR-050c).
_KNOWN_CURRENCIES = ("KRW", "USD", "JPY", "EUR")


def parse_principal(raw: str) -> Decimal:
    """원금을 `Decimal`로 읽는다.

    문자열로 받는 이유는 응답과 같다 — 경계에서 정밀도를 잃지 않는다. 숫자가 아니면
    **조용히 0으로 떨어뜨리지 않는다.** 0이면 수익률이 0으로 나오는데 오류가 없다.
    """
    try:
        amount = Decimal(raw)
    except (InvalidOperation, ValueError) as exc:
        raise InvalidQuery(f"원금이 숫자가 아닙니다: {raw}") from exc
    if amount <= 0:
        raise InvalidQuery("원금은 0보다 커야 합니다.")
    return amount


def allowed_principals(stock_currency: str) -> list[str]:
    """그 종목에 고를 수 있는 원금 통화 — **원화와 종목 통화**뿐이다 (006 FR-050)."""
    return list(dict.fromkeys(("KRW", stock_currency)))


def check_principal_currency(code: str, stock_currency: str | None = None) -> None:
    """원금 통화를 검증한다 (005 FR-003, 006 FR-050·050a, research R6-11).

    표와 차트가 같은 규칙을 써야 한다 — 한쪽만 통화를 거르면 같은 조건이 한 화면에서
    거절되고 다른 화면에서 통과한다. 006 — **어느 경로로 들어온 요청이든** 이 함수를 지난다
    (이력 재실행, 직접 요청). 화면만 막으면 막았다고 믿는 동안 틀린 숫자가 계속 나온다.

    `stock_currency`가 없으면 형식만 본다(종목을 찾기 전). 있으면 조합을 본다 — 원화도 종목
    통화도 아니면 `currency_pair_not_allowed`다.
    """
    if code not in _KNOWN_CURRENCIES:
        raise InvalidQuery(
            f"원금 통화는 {' · '.join(PRINCIPAL_CURRENCIES)} 중 하나여야 합니다: "
            f"{code}")
    if stock_currency is None:
        return
    allowed = allowed_principals(stock_currency)
    if code not in allowed:
        what = "원화" if allowed == ["KRW"] else f"KRW 또는 종목 통화({stock_currency})"
        raise CurrencyPairNotAllowed(
            f"원금 통화는 {what}여야 합니다: {code}", allowed)


class BeforeListing(Exception):
    """투자 시작 날짜가 종목의 시작 가능 날짜 이전이다 (FR-005, 006 FR-005a).

    **조용히 첫 거래일로 옮기지 않는다.** 옮기면 사용자는 자신이 고른 날짜부터
    계산됐다고 믿는다. 006 — 시작 가능 날짜와 그 근거를 함께 든다. 화면이 그 날짜로
    옮기는 수단을 그린다.

    - `listing`: 목록의 상장일보다 이르다. 시세를 받기 전에 낸다
    - `price_start`: 시세 출처가 그보다 늦게 시작한다
    """

    def __init__(self, startable_from: dt.date, basis: str) -> None:
        super().__init__(_before_listing_message(startable_from))
        self.startable_from = startable_from
        self.basis = basis


async def reaches_end(session: AsyncSession, stock_id: int, as_of: dt.date, end: dt.date) -> bool:
    """마지막 일봉(`as_of`)이 계산 끝(`end`)까지의 결과로 볼 수 있는가(FR-014a·FR-014b).

    계산 끝이 휴장·주말이면 마지막 일봉이 그보다 이르러도 최종이다 — 시세가 빠진 것이 아니다(버그
    stock-holiday-stale-warning). 같은 시장의 다른 종목이 그 뒤에 거래했으면 이 종목만 끊긴 것이다.
    일시금과 적립식이 이 함수 하나를 쓴다 — 보드·표의 경고가 갈라지지 않는다.
    """
    if as_of >= end:
        return True
    market_last = await price_repo.market_last_quote_date(session, stock_id, end)
    return quote_is_final(as_of, end, market_last=market_last,
                          tolerance_weekdays=load_settings().stock_holiday_tolerance_weekdays)


class NoPriceData(Exception):
    """시세를 얻을 수 없다 (FR-004).

    **빈 표를 보여주지 않는다.** 사용자는 그 종목의 성과가 0이라고 읽는다.
    """


async def run_simulation(
    session: AsyncSession,
    stock_id: int,
    *,
    start: dt.date,
    end: dt.date,
    principal: Decimal,
    currency: str,
    reinvest: bool,
    fee_rate: Decimal,
    tax_rate: Decimal,
    lookup: RateLookup | None = None,
    spread: Decimal | None = None,
) -> SimulationResult:
    """시세를 읽어 순수 함수에 넘기고 결과를 돌려준다.

    시세가 중간에 끊기면(상장폐지·거래정지) **마지막 고시일까지만** 계산한다. 마지막
    시세를 오늘까지 이어 그리면 없는 값을 만들어내는 것이라 헌법 원칙 V 위반이다
    (FR-014a).
    """
    bars_rows = await price_repo.prices(session, stock_id, start, end)
    if not bars_rows:
        raise NoPriceData("요청한 구간에 시세가 없습니다.")
    await _require_start_month_bar(session, stock_id, start, bars_rows[0].quote_date)

    dividend_rows = await price_repo.dividends(session, stock_id, start, end)
    split_rows = await price_repo.splits(session, stock_id, start, end)
    # 시뮬레이터가 주식 수를 조정한 기록 그대로 결과에도 싣는다 — 차트의 분할 표식(010 FR-008)이
    # 같은 기록을 본다.
    splits = tuple(SplitOn(s.effective_date, s.numerator, s.denominator) for s in split_rows)

    # **환전은 실제로 매수가 일어나는 첫 거래일에 한다.** 투자 시작 날짜가 아니다 —
    # 돈은 살 때 바꾸며, 시작 날짜가 휴일이면 그날의 환율도 없다. 006 FR-068 — 외화 원금의 KRW
    # 원금도 같은 날의 매매기준율로 정한다(평가이지 환전이 아니다).
    first_day = bars_rows[0].quote_date
    exchange: InitialExchange | None = None
    principal_krw: Decimal | None = None
    if lookup is not None and spread is not None:
        exchange = build_exchange(lookup, first_day, spread, currency)
    elif lookup is not None:
        principal_krw = _krw_principal(lookup, first_day, principal, currency)

    # 원화 원금이면 **환전된 금액**으로 시뮬레이션한다. 시뮬레이터는 종목 통화 세계에서만 돈다.
    working_principal = (
        to_foreign(principal, exchange.rate, currency)
        if exchange is not None else principal
    )

    outcome = simulate_detailed(
        # 010 FR-028 — 잔고는 같은 일봉의 원주가 종가로 평가한다(매수는 시가).
        [DayBar(r.quote_date, r.open_raw, r.close_raw) for r in bars_rows],
        [DividendOn(d.ex_date, d.amount_per_share) for d in dividend_rows],
        list(splits),
        Condition(
            start=start, principal=working_principal, currency=currency,
            reinvest=reinvest, fee_rate=fee_rate, tax_rate=tax_rate,
            reinvest_lag_days=REINVEST_LAG_TRADING_DAYS),
    )
    rows = outcome.rows

    as_of = bars_rows[-1].quote_date
    # 요청 끝(보통 어제)까지 시세가 있으면 최종이다. 끊겼으면 그 사실이 드러나야 한다 — 다만 계산
    # 끝이 휴장·주말이면 끊긴 것이 아니다(버그 stock-holiday-stale-warning).
    is_final = await reaches_end(session, stock_id, as_of, end)

    quote_dates = frozenset(r.quote_date for r in bars_rows)
    closes = {r.quote_date: r.close_raw for r in bars_rows}

    if lookup is None:
        # 국내 종목이다. 모두 KRW라 평가할 것이 없다 (FR-023).
        return SimulationResult(
            rows=[ConvertedRow(r) for r in rows],
            latest=ConvertedRow(outcome.latest) if outcome.latest else None,
            as_of=as_of, is_final=is_final, quote_dates=quote_dates, splits=splits,
            closes=closes, daily=outcome.daily)

    evaluate = partial(_evaluate, lookup=lookup, principal=principal,
                       basis=principal_krw if principal_krw is not None else principal)
    return SimulationResult(
        rows=[evaluate(r) for r in rows],
        latest=evaluate(outcome.latest) if outcome.latest else None,
        as_of=as_of, is_final=is_final, exchange=exchange, quote_dates=quote_dates,
        principal_krw=principal_krw, splits=splits, closes=closes, daily=outcome.daily,
        convert=evaluate)


def _krw_principal(
    lookup: RateLookup, first_day: dt.date, principal: Decimal, currency: str
) -> Decimal:
    """외화 원금의 KRW 값 — 첫 매수일의 매매기준율 (006 FR-068, research R6-25).

    그 날 이전의 환율이 하나도 없으면 **원금 통화 기준으로 떨어지지 않는다** — 그러면 이 실행만
    달러 기준 수익률이 되어, 이력 비교에서 원화 원금 실행과 다른 기준의 수익률이 나란히 놓인다.
    """
    resolved = resolve_rate(lookup, first_day)
    if resolved is None:
        raise FxUnavailable(
            f"{first_day.isoformat()} 이전의 {currency} 환율이 없어 "
            "원금을 KRW로 평가할 수 없습니다.")
    return to_principal(principal, resolved[0], "KRW")


def _evaluate(
    row: Row,
    *,
    lookup: RateLookup,
    principal: Decimal,
    basis: Decimal,
) -> ConvertedRow:
    """행을 **그 기준일의 매매기준율로** KRW 평가한다 (005 FR-041a·041b, 006 FR-066, FR-068).

    초기 환전 환율 하나로 전 구간을 평가하면 그 뒤의 환율 변동이 통째로 사라진다 — 주가는
    올랐는데 환율이 내려 실제로는 손실인 구간이 이익으로 보인다. 평가에는 **매매기준율**을 쓴다 —
    현금 살 때 환율과 우대는 실제로 돈을 바꾸는 초기 환전에만 적용된다.

    006 — 행의 금액은 종목 통화로 둔다. 투자 수익 = (잔고 + 예수금) × 그 행의 매매기준율 − KRW
    원금(`basis`), 수익율 = 투자 수익 ÷ KRW 원금. `principal`은 입력한 원금 그대로다 — 시뮬레이터
    안의 원금은 환전된 종목 통화 금액이다.
    """
    resolved = resolve_rate(lookup, row.date)
    if resolved is None:
        # 첫 매수일의 환율을 이미 확인했으므로 오지 않는다. 와도 종목 통화 수익을 KRW로 내보내지
        # 않는다.
        raise FxUnavailable(f"{row.date.isoformat()} 이전의 환율이 없어 KRW로 평가할 수 없습니다.")
    rate, used = resolved
    krw = evaluate_krw(row.balance, row.cash, rate, basis)
    evaluated = replace(
        row, principal=principal, profit=krw.profit, return_rate=krw.return_rate)
    return ConvertedRow(evaluated, fx_rate=rate, fx_rate_date=used, balance_krw=krw.balance_krw)


def table(result: SimulationResult, *, unit: PeriodUnit, end: dt.date, before: dt.date | None,
          limit: int) -> TablePage[ConvertedRow]:
    """일자별 표의 한 쪽 (012 FR-003~FR-005 — 005 FR-029의 커서 쪽을 대체).

    사건 행은 첫 매수(`buy` — 시작 월의 월 행, 수수료가 있다)·배당락·재투자다. 그 밖의 월 행(그 달
    첫 거래일)은 표에 없다 — 주식 차트의 재료로만 남는다
    (FR-008). 같은 날의 행은 처리 차례(배당락 → 재투자 → 그날 스냅숏)로 놓여 마지막 행이 그날의
    상태를 보인다.
    """
    months = [c.row.date for c in result.rows if c.row.kind == "month_first"]
    bought_on = min(months) if months else None
    items: list[tuple[dt.date, str, ConvertedRow]] = []
    for converted in result.rows:
        kind = converted.row.kind
        if kind in {"dividend", "reinvest"}:
            items.append((converted.row.date, kind, converted))
        elif kind == "month_first" and converted.row.date == bought_on:
            items.append((converted.row.date, "buy", converted))
    by_day = {row.date: row for row in result.daily}
    return table_page(
        unit=unit, end=end, before=before, limit=limit, quote_days=list(by_day),
        events=group_events(items), end_of_day_last=True,
        day_state=lambda day: result.convert(by_day[day]))


@dataclass(frozen=True, slots=True)
class Prepared:
    """조회에 필요한 것을 한 번에 모아 둔 결과.

    표와 차트가 **같은 함수를 같은 입력으로** 부르게 하려고 둔다. 각 라우트가 따로
    조립하면 한쪽만 설정이나 환율 적용을 빠뜨려도 오류 없이 다른 숫자가 나온다
    (SC-032).
    """

    stock: Stock
    settings: StockSettings
    result: SimulationResult
    #: 그 종목에 적용한 배당 소득세 — 국내 또는 해외 (006 FR-055). 응답의 조건에 싣는다.
    dividend_tax_rate: Decimal
    #: 011 FR-037 — 보드의 매도 세금 설정(기준일에 모두 판다고 가정할 때). 표·차트에는 쓰지 않는다.
    sale_tax: SaleTaxSettings


async def require_stock(session: AsyncSession, market: str, symbol: str) -> Stock:
    """종목을 찾는다. 없으면 검색용 목록으로 등록을 시도하고, 그래도 없으면 404로 올린다.

    **빈 결과를 돌려주지 않는다.** 사용자는 그 종목의 성과가 0이라고 읽는다.

    006 FR-030b — 이력(브라우저)은 DB와 따로 살아, 이력에서 다시 실행한 종목이 아직 등록되지 않았을
    수 있다. 국내 종목은 목록으로 등록한 뒤 진행한다. 일본이거나 목록에서 찾지 못하면 "검색에서 다시
    고르세요"로 답한다 — 시세 출처가 모르는 것(`price_symbol_unknown`)과 다른 사유다(FR-032).
    """
    stock = await find_stock(session, market, symbol)
    if stock is None and market in US_MARKETS:
        # FR-030a — 다른 거래소로 등록된 같은 티커가 같은 종목이다(005 이력 ↔ 006 목록).
        stock = await find_us_stock(session, symbol)
    if stock is None:
        stock = await register_from_price_symbol(session, market, symbol)
    if stock is None:
        raise UnknownStock(
            f"목록에서 찾을 수 없는 종목입니다: {market}:{symbol}. 검색에서 다시 고르세요.")
    return stock


def _before_listing_message(earliest: dt.date) -> str:
    return f"{earliest.isoformat()}부터 시세가 있습니다. 그 이전은 계산할 수 없습니다."


def start_month(start: dt.date) -> dt.date:
    """시작 월의 1일. 수집 후 판정이 시작일 앞부분의 일봉까지 보려면 여기부터 받아야 한다."""
    return start.replace(day=1)


def _month_end(day: dt.date) -> dt.date:
    following = (day.replace(day=28) + dt.timedelta(days=4)).replace(day=1)
    return following - dt.timedelta(days=1)


async def _require_start_month_bar(
    session: AsyncSession, stock_id: int, start: dt.date, first_bar: dt.date
) -> None:
    """**수집 후** 판정 — 시작 월에 일봉이 하나도 없으면 막는다 (006 FR-005, research R6-8).

    "첫 일봉 > 시작일"로 판정하면 휴일 시작(2020-01-01 → 01-02)을 거절한다 — 005가 실제
    경로에서 겪은 결함이다. 한 달 안에 일봉이 하나도 없는 경우는 휴장으로 설명되지 않는다.
    시작일 **앞**의 일봉도 본다 — 월말 휴일 시작(12-31)의 첫 매수가 다음 달인 것은 휴장
    때문이지 시세 시작 때문이 아니다.
    """
    if (first_bar.year, first_bar.month) == (start.year, start.month):
        return
    month = await price_repo.prices(session, stock_id, start_month(start), _month_end(start))
    if not month:
        # 첫 매수가 시세 시작일로 **몰래 밀리지 않게** 막고 실제 시작일을 알린다 (SC-013a).
        raise BeforeListing(first_bar, "price_start")


async def require_start_available(
    session: AsyncSession, stock: Stock, start: dt.date
) -> None:
    """**수집 전** 판정 — 하한보다 이른 시작일을 막는다 (FR-005, 006 FR-005a).

    **수집을 시작하기 전에 판정한다.** 뒤로 미루면 상장 수십 년 전부터의 구간이
    미수집으로 보여 수집이 시작되고, 사용자는 받을 수 없는 데이터를 기다린다.

    하한은 둘이다 — 검색용 목록의 상장일(`listing`)과 시세 출처가 준 시세 시작일
    (`price_start`). 둘 다 "그보다 앞에는 일봉이 없다"는 확실한 근거다. **받아 둔 첫
    시세는 근거가 아니다**(research R6-8): 늦은 시작일로 한 번 받으면 그 날짜가 첫 시세가
    되어, 더 이른 시작일을 받으러 가지도 않고 거절한다. 휴일 시작도 거절한다.
    """
    listing = await listing_for(session, stock.market, stock.symbol)
    if listing is not None and listing.listed_on is not None and start < listing.listed_on:
        raise BeforeListing(listing.listed_on, "listing")
    if stock.first_available_date is not None and start < stock.first_available_date:
        raise BeforeListing(stock.first_available_date, "price_start")


async def prepare(
    session: AsyncSession,
    *,
    market: str,
    symbol: str,
    start: dt.date,
    end: dt.date,
    principal: Decimal,
    principal_currency: str,
    reinvest: bool,
) -> Prepared:
    """종목·설정·환율을 읽어 시뮬레이션을 돌린다."""
    stock = await require_stock(session, market, symbol)
    # 계산하는 곳에서도 한 번 더 본다 — 라우트가 빠뜨려도 막힌 조합이 계산되지 않는다(FR-051).
    check_principal_currency(principal_currency, stock.currency)
    settings = await get_settings(session)
    # 006 FR-055 — 종목의 시장으로 국내·해외 세율을 고른다.
    tax_rate = settings.dividend_tax_rate_for(stock.market)

    # 006 FR-068 — 해외 종목이면 원금 통화와 관계없이 KRW로 평가하므로 환율을 읽는다. 환전(현금
    # 살 때 환율과 우대)은 원화 원금에만 있다(FR-052). 국내 종목은 모두 KRW다 (FR-023).
    lookup = None
    spread = None
    currency = fx_currency_for(stock.currency)
    if currency is not None:
        lookup = await load_rates(session, currency, start, end)
        if principal_currency == "KRW":
            spread = await cash_buy_spread(session, currency)

    result = await run_simulation(
        session, int(stock.id),
        start=start, end=end, principal=principal,
        currency=stock.currency, reinvest=reinvest,
        fee_rate=settings.trade_fee_rate, tax_rate=tax_rate,
        lookup=lookup, spread=spread)

    return Prepared(stock=stock, settings=settings, result=result, dividend_tax_rate=tax_rate,
                    sale_tax=await get_sale_tax(session))
