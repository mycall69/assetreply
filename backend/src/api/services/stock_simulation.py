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
from dataclasses import dataclass, replace
from decimal import Decimal, InvalidOperation

from sqlalchemy.ext.asyncio import AsyncSession

from src.api.errors import InvalidQuery
from src.api.services.stock_fx import (
    InitialExchange,
    build_exchange,
    cash_buy_spread,
    load_rates,
)
from src.db.models import Stock
from src.ingestion.yahoo.errors import StockSymbolNotFound
from src.repository import stock_price as price_repo
from src.repository.stock import find_stock
from src.repository.stock_setting import Settings as StockSettings
from src.repository.stock_setting import get_settings
from src.simulation.fx_convert import (  # noqa: E501
    RateLookup,
    resolve_rate,
    to_foreign,
    to_principal,
)
from src.simulation.money import quantize_rate
from src.simulation.reinvest import (
    Condition,
    DayBar,
    DividendOn,
    Row,
    SplitOn,
    simulate,
)


@dataclass(frozen=True, slots=True)
class ConvertedRow:
    """원금 통화로 환산된 행 (FR-041a).

    `fx_rate`·`fx_rate_date`는 **그 행의 평가 환산에 쓴** 매매기준율과 날짜다.
    기준일과 날짜가 다를 수 있다 — 주식 거래일과 환율 고시일은 일치하지 않는다
    (FR-041c).
    """

    row: Row
    fx_rate: Decimal | None = None
    fx_rate_date: dt.date | None = None


@dataclass(frozen=True, slots=True)
class SimulationResult:
    """시뮬레이션 전체 결과. 페이지는 호출부가 자른다.

    `as_of`는 계산이 **어느 날짜까지**인지다. 시세가 끊기면 오늘이 아니다 (FR-014a).
    `is_final`은 항상 명시한다 — "확인했고 아니다"와 "확인하지 않았다"가 구별되어야
    한다.
    """

    rows: list[ConvertedRow]
    as_of: dt.date | None
    is_final: bool
    exchange: InitialExchange | None = None
    #: 구간 안에서 **실제로 시세가 있는 날짜**. 차트의 결측 구간 판정에 쓴다.
    #: 행 날짜(월 첫 거래일·배당락일)로는 판정할 수 없다 — 그 사이의 거래일이
    #: 전부 비어 보여 멀쩡한 구간이 미수집으로 끊긴다 (FR-034).
    quote_dates: frozenset[dt.date] = frozenset()


#: 원금으로 고를 수 있는 통화 (FR-003).
PRINCIPAL_CURRENCIES = ("KRW", "USD", "JPY", "EUR")


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


def check_principal_currency(code: str) -> None:
    """원금 통화를 검증한다 (FR-003).

    표와 차트가 같은 규칙을 써야 한다 — 한쪽만 통화를 거르면 같은 조건이 한 화면에서
    거절되고 다른 화면에서 통과한다.
    """
    if code not in PRINCIPAL_CURRENCIES:
        raise InvalidQuery(
            f"원금 통화는 {' · '.join(PRINCIPAL_CURRENCIES)} 중 하나여야 합니다: "
            f"{code}")


class BeforeListing(Exception):
    """투자 시작 날짜가 종목의 상장 이전이다 (FR-005).

    **조용히 첫 거래일로 옮기지 않는다.** 옮기면 사용자는 자신이 고른 날짜부터
    계산됐다고 믿는다.
    """


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
    listed_on: dt.date | None = None,
    principal_currency: str | None = None,
    lookup: RateLookup | None = None,
    spread: Decimal | None = None,
) -> SimulationResult:
    """시세를 읽어 순수 함수에 넘기고 결과를 돌려준다.

    시세가 중간에 끊기면(상장폐지·거래정지) **마지막 고시일까지만** 계산한다. 마지막
    시세를 오늘까지 이어 그리면 없는 값을 만들어내는 것이라 헌법 원칙 V 위반이다
    (FR-014a).
    """
    # **상장일과 "우리가 받아 둔 첫 시세"는 다르다.** 전자를 알면 그것을 쓰고,
    # 모르면 후자를 근거로 삼는다. 후자만 쓰면 월초가 휴일인 정상적인 시작일
    # (예: 8월 1일 일요일, 첫 거래일 8월 2일)까지 거절한다.
    earliest = listed_on or await price_repo.first_quote_date(session, stock_id)
    if earliest is None:
        raise NoPriceData("그 종목의 시세를 얻을 수 없습니다.")
    if start < earliest:
        raise BeforeListing(
            f"{earliest.isoformat()}부터 시세가 있습니다. 그 이전은 계산할 수 없습니다.")

    bars_rows = await price_repo.prices(session, stock_id, start, end)
    if not bars_rows:
        raise NoPriceData("요청한 구간에 시세가 없습니다.")

    dividend_rows = await price_repo.dividends(session, stock_id, start, end)
    split_rows = await price_repo.splits(session, stock_id, start, end)

    # **환전은 실제로 매수가 일어나는 첫 거래일에 한다.** 투자 시작 날짜가 아니다 —
    # 돈은 살 때 바꾸며, 시작 날짜가 휴일이면 그날의 환율도 없다.
    exchange: InitialExchange | None = None
    if lookup is not None and spread is not None:
        exchange = build_exchange(
            lookup, bars_rows[0].quote_date, spread, currency)

    # 원금 통화와 종목 통화가 다르면 **환전된 금액**으로 시뮬레이션한다. 시뮬레이터는
    # 종목 통화 세계에서만 돌고, 환산은 그 결과를 원금 통화로 되돌리는 일이다.
    working_principal = (
        to_foreign(principal, exchange.rate, currency)
        if exchange is not None else principal
    )
    principal_currency = principal_currency or currency

    rows = simulate(
        [DayBar(r.quote_date, r.open_raw) for r in bars_rows],
        [DividendOn(d.ex_date, d.amount_per_share) for d in dividend_rows],
        [SplitOn(s.effective_date, s.numerator, s.denominator) for s in split_rows],
        Condition(
            start=start, principal=working_principal, currency=currency,
            reinvest=reinvest, fee_rate=fee_rate, tax_rate=tax_rate),
    )

    as_of = bars_rows[-1].quote_date
    # 요청 끝(보통 어제)까지 시세가 있으면 최종이다. 끊겼으면 그 사실이 드러나야 한다.
    is_final = as_of >= end

    quote_dates = frozenset(r.quote_date for r in bars_rows)

    if lookup is None or exchange is None:
        # 원금 통화와 종목 통화가 같다. 환전도 환산도 없다 (FR-023).
        return SimulationResult(
            rows=[ConvertedRow(r) for r in rows], as_of=as_of, is_final=is_final,
            quote_dates=quote_dates)

    return SimulationResult(
        rows=[_convert(r, lookup, principal_currency, principal) for r in rows],
        as_of=as_of, is_final=is_final, exchange=exchange, quote_dates=quote_dates)


def _convert(
    row: Row,
    lookup: RateLookup,
    principal_currency: str,
    original_principal: Decimal,
) -> ConvertedRow:
    """행의 금액을 **그 기준일의 환율로** 원금 통화로 바꾼다 (FR-041a).

    초기 환전 환율 하나로 전 구간을 환산하면 그 뒤의 환율 변동이 통째로 사라진다 —
    주가는 올랐는데 환율이 내려 실제로는 손실인 구간이 이익으로 보인다.

    평가 환산에는 **매매기준율**을 쓴다. 현금 살 때 환율과 우대는 실제로 돈을 바꾸는
    초기 환전에만 적용된다 (FR-041b).
    """
    resolved = resolve_rate(lookup, row.date)
    if resolved is None:
        # 그 기준일 이전의 환율이 하나도 없다. 값을 만들어내지 않는다.
        return ConvertedRow(row)
    rate, used = resolved

    converted = Row(
        date=row.date,
        kind=row.kind,
        open_price=row.open_price,
        bought_shares=row.bought_shares,
        held_shares=row.held_shares,
        cash=to_principal(row.cash, rate, principal_currency),
        # **원금은 사용자가 낸 그 금액이다.** 시뮬레이터 안의 `principal`은 환전된
        # 종목 통화 금액이라, 그것을 쓰면 원금 통화 잔고에서 종목 통화 원금을 빼게 된다.
        principal=original_principal,
        balance=to_principal(row.balance, rate, principal_currency),
        profit=to_principal(row.balance + row.cash, rate, principal_currency)
        - original_principal,
        return_rate=row.return_rate,
        dividend_per_share=row.dividend_per_share,
        dividend_yield=row.dividend_yield,
    )
    # 수익률은 환산 후 금액으로 다시 낸다 — 환율 변동이 수익률에 들어가야 한다.
    rate_value = (
        quantize_rate(converted.profit / converted.principal)
        if converted.principal > 0 else Decimal("0")
    )
    converted = replace(converted, return_rate=rate_value)
    return ConvertedRow(converted, fx_rate=rate, fx_rate_date=used)


def page(
    rows: list[ConvertedRow], before: dt.date | None, limit: int
) -> tuple[list[ConvertedRow], bool]:
    """커서 방식 페이지 (FR-029).

    004가 정한 것과 같다 — 오프셋을 쓰지 않는다. 수집이 조회 중에 행을 추가해도
    "이 날짜 미만"은 같은 집합이라 같은 행을 두 번 주거나 건너뛰지 않는다.

    `(페이지, 더 있는가)`를 돌려준다.
    """
    candidates = [r for r in rows if before is None or r.row.date < before]
    chunk = candidates[:limit]
    return chunk, len(candidates) > limit


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
    stock = await find_stock(session, market, symbol)
    if stock is None:
        raise StockSymbolNotFound(f"알 수 없는 종목입니다: {market}:{symbol}")

    settings = await get_settings(session)

    # 원금 통화와 종목 통화가 같으면 환전이 없다 (FR-023).
    lookup = None
    spread = None
    if principal_currency != stock.currency:
        lookup = await load_rates(session, stock.currency, start, end)
        spread = await cash_buy_spread(session, stock.currency)

    result = await run_simulation(
        session, int(stock.id),
        start=start, end=end, principal=principal,
        currency=stock.currency, reinvest=reinvest,
        fee_rate=settings.trade_fee_rate, tax_rate=settings.dividend_tax_rate,
        listed_on=stock.first_available_date,
        principal_currency=principal_currency,
        lookup=lookup, spread=spread)

    return Prepared(stock=stock, settings=settings, result=result)
