"""주식 적립식 조회·조합 (011 T025) — FR-002, FR-004, FR-005, FR-010~FR-013, FR-016, research
R11-3~R11-5·R11-7.

**계산을 직접 하지 않는다.** 일정·환전은 `simulation/contribution_schedule`, 계산은
`simulation/recurring_stock`, 원화 평가는 `fx_convert.evaluate_krw`, 매도 비용은
`simulation/stock_sale_cost`의 순수 함수다(헌법 원칙 IV). 여기서는 읽어 넘기고 맞춘다.

**결과를 저장하지 않는다**(005 R5-9) — 시세·배당·분할·설정·환율의 함수다. 일시금과 같은 검증
함수(`require_stock`· `check_principal_currency`·`require_start_available`)와 같은 수집
판정(`collecting_body`)을 쓴다 — 규칙이 갈라지지 않는다(FR-016).

- 시세는 **시작일부터** 읽는다(일시금과 같다). 첫 납입은 시작일 이후 첫 거래일이다(명확화)
- 매일 납입의 예정일은 거래일이다(FR-003). 나머지 주기는 달력에서 정하고 휴장이면 다음 거래일로
  미룬다(FR-004)
- 원화 평가는 행마다 **그 행까지의 원화 분모**로 나눈다(FR-011). 일시금의 원금 하나로 나누면
  수익률이 납입 횟수만큼 부푼다
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from decimal import ROUND_FLOOR, Decimal
from typing import Final

from sqlalchemy.ext.asyncio import AsyncSession

from src.api.errors import InvalidQuery
from src.api.services.stock_fx import (
    FxUnavailable,
    cash_buy_spread,
    fx_currency_for,
    load_rates,
)
from src.api.services.stock_simulation import (
    REINVEST_LAG_TRADING_DAYS,
    NoPriceData,
    _require_start_month_bar,
    check_principal_currency,
    require_stock,
)
from src.db.models import Stock
from src.repository import stock_price as price_repo
from src.repository.stock_setting import SaleTaxSettings, get_sale_tax, get_settings
from src.repository.stock_setting import Settings as StockSettings
from src.simulation.contribution_schedule import (
    FREQUENCIES,
    Contribution,
    ContributionFxMissing,
    Frequency,
    assign,
    fund,
    scheduled_dates,
)
from src.simulation.fx_convert import RateLookup, evaluate_krw, resolve_rate
from src.simulation.money import quantize_rate
from src.simulation.recurring_stock import (
    RecurringCondition,
    RecurringRow,
    simulate_recurring_stock,
)
from src.simulation.reinvest import DayBar, DividendOn, SplitOn
from src.simulation.stock_sale_cost import SaleCost, domestic_sale_cost, foreign_sale_cost

DOMESTIC_MARKET: Final = "KRX"
_ZERO = Decimal("0")
_WON = Decimal("1")


def parse_frequency(raw: str) -> Frequency:
    """주기를 읽는다. **기본값으로 바꾸지 않는다** — 매달로 바꿔 실행하면 사용자가 고른 것과 다른
    일정의 결과가 사유 없이 나온다(FR-002)."""
    for frequency in FREQUENCIES:
        if raw == frequency:
            return frequency
    raise InvalidQuery(f"주기는 {' · '.join(FREQUENCIES)} 중 하나여야 합니다: {raw}")


def parse_amount(raw: str) -> Decimal:
    """한 번 납입액(원금 통화, 문자열). 숫자가 아니거나 0 이하이면 막는다 — 0으로 떨어뜨리면 수익률
    0이 오류 없이 나온다(FR-002)."""
    try:
        value = Decimal(raw)
    except (ArithmeticError, ValueError) as exc:
        raise InvalidQuery(f"한 번 납입액이 숫자가 아닙니다: {raw}") from exc
    if not value.is_finite() or value <= 0:
        raise InvalidQuery("한 번 납입액은 0보다 커야 합니다.")
    return value


def dec(value: Decimal) -> str:
    """금액·비율 문자열. **지수 표기를 내지 않는다** — 빼기로 0이 되면 `Decimal("0E-12")`이고
    `str()`이 그대로 내면 화면이 "0E12"로 보인다 (T030 실측). 0은 "0", 나머지는 고정 소수점이다."""
    return "0" if value == 0 else format(value, "f")


def floor_won(amount: Decimal) -> Decimal:
    return amount.quantize(_WON, rounding=ROUND_FLOOR)


@dataclass(frozen=True, slots=True)
class RecurringView:
    """원화로 평가한 행. 행의 금액(잔고·대기금·배당 현금·수수료)은 **종목 통화로 남는다** — 006
    FR-066과 같다."""

    row: RecurringRow
    #: 원금 통화로 센 그 행의 납입액(납입액 × 모인 예정일 수)과 그때까지의 총 납입 원금.
    contribution: Decimal | None
    contributed: Decimal
    profit: Decimal
    return_rate: Decimal
    total_krw: Decimal
    balance_krw: Decimal | None = None
    #: 평가 환율(매매기준율)과 고시일 — 해외 종목만.
    fx_rate: Decimal | None = None
    fx_rate_date: dt.date | None = None
    #: 원화 원금 납입 행의 환전 환율(현금 살 때 + 우대)과 고시일.
    exchange_rate: Decimal | None = None
    exchange_rate_date: dt.date | None = None


@dataclass(frozen=True, slots=True)
class RecurringResult:
    views: list[RecurringView]
    latest: RecurringView | None
    as_of: dt.date
    is_final: bool
    pending_after_end: int
    quote_dates: frozenset[dt.date]
    splits: tuple[SplitOn, ...]
    buy_fee_total_krw: Decimal
    dividend_tax_total_krw: Decimal
    sale_cost: SaleCost | None = None
    #: 쪽을 나눌 때 같은 날의 행이 갈리지 않게 쓰는 날짜 목록(최신순 행과 같은 순서).
    dates: tuple[dt.date, ...] = field(default=())


@dataclass(frozen=True, slots=True)
class PreparedRecurring:
    stock: Stock
    settings: StockSettings
    sale_tax: SaleTaxSettings
    dividend_tax_rate: Decimal
    result: RecurringResult


def _evaluate(row: RecurringRow, *, lookup: RateLookup | None, contribution: Decimal | None,
              contributed: Decimal) -> RecurringView:
    exchanged = row.fx_kind == "cash_buy_discounted"
    exchange = (row.fx_rate, row.fx_rate_date) if exchanged else (None, None)
    if lookup is None:
        # 원화 종목 — 종목 통화 기준이 곧 원화 기준이다(넣은 금액의 합 = 원화 분모).
        return RecurringView(row=row, contribution=contribution, contributed=contributed,
                             profit=row.profit, return_rate=row.return_rate, total_krw=row.total)
    resolved = resolve_rate(lookup, row.date)
    if resolved is None:
        raise FxUnavailable(f"{row.date.isoformat()} 이전의 환율이 없어 KRW로 평가할 수 없습니다.")
    rate, used = resolved
    krw = evaluate_krw(row.balance, row.pending + row.dividend_cash, rate, row.basis_krw)
    return RecurringView(
        row=row, contribution=contribution, contributed=contributed, profit=krw.profit,
        return_rate=krw.return_rate, total_krw=krw.profit + row.basis_krw,
        balance_krw=krw.balance_krw, fx_rate=rate, fx_rate_date=used,
        exchange_rate=exchange[0], exchange_rate_date=exchange[1])


def _sale_cost(views: list[RecurringView], latest: RecurringView, *, market: str,
               fee_rate: Decimal, sale_tax: SaleTaxSettings) -> SaleCost | None:
    """기준일에 모두 판다고 가정한 비용(010 반복 4와 같은 규칙, 세율은 설정 — FR-013·FR-037)."""
    balance = latest.row.balance
    if market == DOMESTIC_MARKET:
        return domestic_sale_cost(balance, fee_rate=fee_rate, tax_rate=sale_tax.domestic)
    if latest.fx_rate is None:
        return None
    acquisition = sum((Decimal(v.row.bought_shares) * v.row.open_price * v.fx_rate
                       for v in views if v.row.bought_shares > 0 and v.fx_rate is not None), _ZERO)
    buy_fees = sum((v.row.trade_fee * v.fx_rate for v in views
                    if v.row.trade_fee is not None and v.fx_rate is not None), _ZERO)
    return foreign_sale_cost(
        sale_krw=balance * latest.fx_rate, sell_fee_krw=balance * fee_rate * latest.fx_rate,
        acquisition_krw=acquisition, buy_fees_krw=buy_fees, rate=sale_tax.foreign_rate,
        deduction=sale_tax.foreign_deduction)


async def prepare_recurring(
    session: AsyncSession, *, market: str, symbol: str, start: dt.date, end: dt.date,
    amount: Decimal, principal_currency: str, frequency: Frequency, reinvest: bool,
) -> PreparedRecurring:
    """종목·설정·환율·시세를 읽어 적립식을 돌린다."""
    stock = await require_stock(session, market, symbol)
    # 계산하는 곳에서도 한 번 더 본다 — 라우트가 빠뜨려도 막힌 조합이 계산되지 않는다(006 FR-051).
    check_principal_currency(principal_currency, stock.currency)
    settings = await get_settings(session)
    sale_tax = await get_sale_tax(session)
    tax_rate = settings.dividend_tax_rate_for(stock.market)

    lookup: RateLookup | None = None
    spread: Decimal | None = None
    currency = fx_currency_for(stock.currency)
    if currency is not None:
        lookup = await load_rates(session, currency, start, end)
        if principal_currency == "KRW":
            spread = await cash_buy_spread(session, currency)

    stock_id = int(stock.id)
    bars_rows = await price_repo.prices(session, stock_id, start, end)
    if not bars_rows:
        raise NoPriceData("요청한 구간에 시세가 없습니다.")
    await _require_start_month_bar(session, stock_id, start, bars_rows[0].quote_date)
    dividend_rows = await price_repo.dividends(session, stock_id, start, end)
    split_rows = await price_repo.splits(session, stock_id, start, end)
    splits = tuple(SplitOn(s.effective_date, s.numerator, s.denominator) for s in split_rows)

    trading_days = [r.quote_date for r in bars_rows]
    scheduled = scheduled_dates(start, end, frequency,
                                trading_days=trading_days if frequency == "daily" else None)
    assigned, pending_after_end = assign(scheduled, trading_days)
    try:
        contributions: list[Contribution] = fund(
            assigned, amount, principal_currency=principal_currency,
            quote_currency=stock.currency, lookup=lookup, spread=spread)
    except ContributionFxMissing as exc:
        # 그 납입을 빼고 계산하면 총 납입 원금이 조용히 준다(FR-005) — 409로 올린다.
        raise FxUnavailable(str(exc)) from exc

    outcome = simulate_recurring_stock(
        [DayBar(r.quote_date, r.open_raw, r.close_raw) for r in bars_rows],
        [DividendOn(d.ex_date, d.amount_per_share) for d in dividend_rows], list(splits),
        contributions,
        RecurringCondition(fee_rate=settings.trade_fee_rate, tax_rate=tax_rate, reinvest=reinvest,
                           reinvest_lag_days=REINVEST_LAG_TRADING_DAYS))

    counts = {c.on: len(c.scheduled) for c in contributions}

    def view(row: RecurringRow) -> RecurringView:
        paid = counts.get(row.date) if row.kind == "contribution" else None
        return _evaluate(row, lookup=lookup,
                         contribution=None if paid is None else amount * paid,
                         contributed=amount * row.contributions)

    views = [view(r) for r in outcome.rows]
    latest = view(outcome.latest) if outcome.latest is not None else None
    if lookup is None:
        buy_fees = floor_won(outcome.buy_fee_total)
        dividend_taxes = floor_won(sum((v.row.dividend_tax for v in views
                                        if v.row.dividend_tax is not None), _ZERO))
    else:
        buy_fees = floor_won(sum((v.row.trade_fee * v.fx_rate for v in views
                                  if v.row.trade_fee is not None and v.fx_rate is not None), _ZERO))
        taxed = [(v.row.dividend_tax, v.fx_rate) for v in views
                 if v.row.dividend_tax is not None and v.fx_rate is not None]
        dividend_taxes = floor_won(sum((tax * rate for tax, rate in taxed), _ZERO))
    as_of = bars_rows[-1].quote_date
    sale = None if latest is None else _sale_cost(views, latest, market=stock.market,
                                                  fee_rate=settings.trade_fee_rate,
                                                  sale_tax=sale_tax)
    result = RecurringResult(
        views=views, latest=latest, as_of=as_of, is_final=as_of >= end,
        pending_after_end=pending_after_end, quote_dates=frozenset(trading_days), splits=splits,
        buy_fee_total_krw=buy_fees, dividend_tax_total_krw=dividend_taxes, sale_cost=sale,
        dates=tuple(v.row.date for v in views))
    return PreparedRecurring(stock=stock, settings=settings, sale_tax=sale_tax,
                             dividend_tax_rate=tax_rate, result=result)


def page(views: list[RecurringView], before: dt.date | None,
         limit: int) -> tuple[list[RecurringView], bool]:
    """커서 쪽(005 FR-029와 같다). **같은 날의 행을 가르지 않는다** — 다음 쪽은 `before = 마지막
    날짜`라, 그날의 남은 행을 가르면 건너뛴다."""
    candidates = [v for v in views if before is None or v.row.date < before]
    chunk = candidates[:limit]
    if chunk and len(candidates) > limit:
        last = chunk[-1].row.date
        chunk += [v for v in candidates[limit:] if v.row.date == last]
    return chunk, len(candidates) > len(chunk)


def summary_json(result: RecurringResult, *, amount: Decimal, stock: Stock) -> dict[str, object]:
    """적립식 보드(FR-012). 매수 수수료·배당 소득세는 이미 총자산에서 빠져 있다 — 투자 수익은 기준일
    매도 비용만 뺀다."""
    latest = result.latest
    if latest is None:
        raise NoPriceData("요청한 구간에 시세가 없습니다.")
    sale = result.sale_cost
    after = None if sale is None or sale.total is None else latest.profit - sale.total
    basis = latest.row.basis_krw
    body: dict[str, object] = {
        "contributed": dec(latest.contributed),
        "contributedKrw": dec(basis),
        "contributions": latest.row.contributions,
        "pendingAfterEnd": result.pending_after_end,
        "heldShares": latest.row.held_shares,
        "pending": dec(latest.row.pending),
        "dividendCash": dec(latest.row.dividend_cash),
        "totalKrw": dec(latest.total_krw),
        "buyFeeTotal": dec(result.buy_fee_total_krw),
        "dividendTaxTotal": dec(result.dividend_tax_total_krw),
        "feeTotal": dec(result.buy_fee_total_krw + (sale.fee if sale is not None else _ZERO)),
        "taxTotal": None if sale is None or sale.tax is None
        else dec(result.dividend_tax_total_krw + sale.tax),
        "profit": dec(latest.profit),
        "returnRate": dec(latest.return_rate),
        "profitAfterSale": None if after is None else dec(after),
        "returnRateAfterSale": None if after is None or basis == 0
        else dec(quantize_rate(after / basis)),
        "asOf": result.as_of.isoformat(),
        "isFinal": result.is_final,
    }
    if sale is not None:
        body["saleCost"] = {
            "fee": dec(sale.fee), "tax": None if sale.tax is None else dec(sale.tax),
            "total": None if sale.total is None else dec(sale.total), "taxKind": sale.tax_kind,
            "taxRate": None if sale.tax_rate is None else dec(sale.tax_rate),
            "gain": None if sale.gain is None else dec(sale.gain),
            "deduction": None if sale.deduction is None else dec(sale.deduction)}
    return body


def row_json(v: RecurringView) -> dict[str, object]:
    """표 한 행. 해당이 없으면 키를 두지 않는다 — 0과 "없음"을 구별한다."""
    row = v.row
    body: dict[str, object] = {
        "date": row.date.isoformat(), "kind": row.kind, "openPrice": dec(row.open_price),
        "closePrice": dec(row.close_price), "boughtShares": row.bought_shares,
        "heldShares": row.held_shares, "pending": dec(row.pending),
        "dividendCash": dec(row.dividend_cash), "contributed": dec(v.contributed),
        "contributedKrw": dec(row.basis_krw), "balance": dec(row.balance),
        "profit": dec(v.profit), "returnRate": dec(v.return_rate),
    }
    if v.contribution is not None:
        body["contribution"] = dec(v.contribution)
    if row.deferred:
        body["deferred"] = [d.isoformat() for d in row.deferred]
    optional = {
        "tradeFee": row.trade_fee, "dividendPerShare": row.dividend_per_share,
        "dividendTotal": row.dividend_total, "dividendTax": row.dividend_tax,
        "dividendTotalNet": row.dividend_total_net, "balanceKrw": v.balance_krw,
        "fxRate": v.fx_rate, "exchangeRate": v.exchange_rate,
    }
    body.update({k: dec(value) for k, value in optional.items() if value is not None})
    if v.fx_rate_date is not None:
        body["fxRateDate"] = v.fx_rate_date.isoformat()
    if v.exchange_rate_date is not None:
        body["exchangeRateDate"] = v.exchange_rate_date.isoformat()
    return body
