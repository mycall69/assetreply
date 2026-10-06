"""가상자산 적립식 조회·조합 (011 T038) — FR-002, FR-017~FR-021, research R11-3·R11-5·R11-6·R11-7.

**계산을 직접 하지 않는다.** 일정·환전은 `simulation/contribution_schedule`, 계산은
`simulation/recurring_crypto`, 원화 평가는 `fx_convert.evaluate_krw`, 매도 비용은
`simulation/crypto_sale_cost`의 순수 함수다(헌법 원칙 IV). 여기서는 읽어 넘기고 맞춘다.

**결과를 저장하지 않는다**(005 R5-9) — 일봉·설정·환율의 함수다. 일시금과 같은 검증 함수
(`check_principal_currency`)·같은 시작 월 판정·같은 환율 읽기(`load_rates` — 확정 환율만)를 쓴다.

- 일봉은 **시작 월 1일부터** 읽는다
  - 시작 월에 일봉이 하나도 없으면 막는다(일시금과 같은 판정)
  - 그 달의 첫 일봉을 알아야 1일 결측도 판정한다
- 예정일은 **달력일**이다(가상자산은 휴장이 없다). 일봉이 없는 날(출처 결측)의 납입은 다음 일봉으로
  미룬다(FR-018)
- 원화 평가는 행마다 **그 행까지의 원화 분모**로 나눈다(FR-011 — 주식과 같다)
- 매도 비용의 기준일은 계산 끝 이하의 마지막 일봉이다
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from decimal import ROUND_FLOOR, Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from src.api.services.crypto_simulation import check_principal_currency
from src.api.services.stock_fx import (
    FxUnavailable,
    cash_buy_spread,
    fx_currency_for,
    load_rates,
)
from src.api.services.stock_simulation import BeforeListing, NoPriceData
from src.db.models import CryptoCoin
from src.repository import crypto_daily
from src.repository.crypto_setting import CryptoSettings, get_settings
from src.simulation.contribution_schedule import (
    Contribution,
    ContributionFxMissing,
    Frequency,
    assign,
    fund,
    scheduled_dates,
)
from src.simulation.crypto_hold import DayOpen
from src.simulation.crypto_sale_cost import CryptoSaleCost, crypto_sale_cost
from src.simulation.fx_convert import RateLookup, evaluate_krw, resolve_rate
from src.simulation.recurring_crypto import RecurringCryptoRow, simulate_recurring_crypto

_ZERO = Decimal("0")
_WON = Decimal("1")


def floor_won(amount: Decimal) -> Decimal:
    return amount.quantize(_WON, rounding=ROUND_FLOOR)


@dataclass(frozen=True, slots=True)
class CryptoRecurringView:
    """원화로 평가한 행. 행의 금액(잔고·대기금·수수료)은 **코인 통화로 남는다**(007 FR-035와
    같다)."""

    row: RecurringCryptoRow
    #: 원금 통화로 센 그 행의 납입액(납입액 × 모인 예정일 수)과 그때까지의 총 납입 원금.
    contribution: Decimal | None
    contributed: Decimal
    profit: Decimal
    return_rate: Decimal
    total_krw: Decimal
    balance_krw: Decimal | None = None
    #: 평가 환율(매매기준율)과 고시일 — 외화 시세 코인만.
    fx_rate: Decimal | None = None
    fx_rate_date: dt.date | None = None
    #: 원화 원금 납입 행의 환전 환율(현금 살 때 + 우대)과 고시일.
    exchange_rate: Decimal | None = None
    exchange_rate_date: dt.date | None = None


@dataclass(frozen=True, slots=True)
class CryptoRecurringResult:
    views: list[CryptoRecurringView]
    latest: CryptoRecurringView
    as_of: dt.date
    is_final: bool
    pending_after_end: int
    #: 실제로 일봉이 있는 날 — 차트의 결측 판정에 쓴다.
    quote_dates: frozenset[dt.date]
    buy_fee_total_krw: Decimal
    sale_cost: CryptoSaleCost
    #: 일봉마다의 평가(오름차순). 차트가 요청할 때만 만든다 — 표는 행만 쓴다.
    daily: tuple[CryptoRecurringView, ...] = ()


@dataclass(frozen=True, slots=True)
class PreparedCryptoRecurring:
    """표와 차트가 **같은 함수를 같은 입력으로** 부르게 모아 둔다(005 SC-032와 같은 이유)."""

    coin: CryptoCoin
    settings: CryptoSettings
    result: CryptoRecurringResult


def _evaluate(row: RecurringCryptoRow, *, lookup: RateLookup | None,
              contribution: Decimal | None, contributed: Decimal) -> CryptoRecurringView:
    exchanged = row.fx_kind == "cash_buy_discounted"
    exchange = (row.fx_rate, row.fx_rate_date) if exchanged else (None, None)
    if lookup is None:
        # 원화 시세 코인 — 코인 통화 기준이 곧 원화 기준이다(넣은 금액의 합 = 원화 분모).
        return CryptoRecurringView(row=row, contribution=contribution, contributed=contributed,
                                   profit=row.profit, return_rate=row.return_rate,
                                   total_krw=row.total)
    resolved = resolve_rate(lookup, row.date)
    if resolved is None:
        raise FxUnavailable(f"{row.date.isoformat()} 이전의 환율이 없어 KRW로 평가할 수 없습니다.")
    rate, used = resolved
    krw = evaluate_krw(row.balance, row.pending, rate, row.basis_krw)
    return CryptoRecurringView(
        row=row, contribution=contribution, contributed=contributed, profit=krw.profit,
        return_rate=krw.return_rate, total_krw=krw.profit + row.basis_krw,
        balance_krw=krw.balance_krw, fx_rate=rate, fx_rate_date=used,
        exchange_rate=exchange[0], exchange_rate_date=exchange[1])


async def prepare_recurring(
    session: AsyncSession, coin: CryptoCoin, *, start: dt.date, end: dt.date, amount: Decimal,
    principal_currency: str, frequency: Frequency, daily: bool = False,
) -> PreparedCryptoRecurring:
    """설정·환율·일봉을 읽어 적립식을 돌린다. `daily`면 일봉마다의 평가도 만든다(차트)."""
    # 계산하는 곳에서도 한 번 더 본다 — 라우트가 빠뜨려도 막힌 조합이 계산되지 않는다.
    check_principal_currency(principal_currency, coin.quote_currency)
    settings = await get_settings(session)
    lookup: RateLookup | None = None
    spread: Decimal | None = None
    currency = fx_currency_for(coin.quote_currency)
    if currency is not None:
        lookup = await load_rates(session, currency, start.replace(day=1), end)
        if principal_currency == "KRW":
            spread = await cash_buy_spread(session, currency)

    rows = await crypto_daily.bars(session, int(coin.id), start.replace(day=1), end)
    if not rows:
        raise NoPriceData("출처에 이 구간의 시세가 없습니다.")
    first_day = rows[0].day
    # **수집 후** 판정 — 시작 월에 일봉이 하나도 없으면 막는다(일시금과 같다, 007 R7-10). 첫 납입이
    # 몰래 다음 달로 밀리지 않게 한다.
    if (first_day.year, first_day.month) != (start.year, start.month):
        raise BeforeListing(first_day, "price_start")

    available = [r.day for r in rows if r.day >= start]
    scheduled = scheduled_dates(start, end, frequency, trading_days=None)
    assigned, pending_after_end = assign(scheduled, available)
    try:
        contributions: list[Contribution] = fund(
            assigned, amount, principal_currency=principal_currency,
            quote_currency=coin.quote_currency, lookup=lookup, spread=spread)
    except ContributionFxMissing as exc:
        # 그 납입을 빼고 계산하면 총 납입 원금이 조용히 준다(FR-005) — 409로 올린다.
        raise FxUnavailable(str(exc)) from exc

    fee_rate = settings.trade_fee_rate
    outcome = simulate_recurring_crypto(
        [DayOpen(r.day, r.open) for r in rows], contributions, fee_rate=fee_rate,
        first_available=coin.first_available_date)
    if outcome.latest is None:
        # 시작일 뒤에 일봉이 없다 — 넣은 납입이 없어 보일 결과가 없다. 0으로 보이지 않는다.
        raise NoPriceData("시작일 뒤에 이 코인의 시세가 없습니다.")

    counts = {c.on: len(c.scheduled) for c in contributions}

    def view(row: RecurringCryptoRow) -> CryptoRecurringView:
        paid = counts.get(row.date) if row.kind == "contribution" else None
        return _evaluate(row, lookup=lookup,
                         contribution=None if paid is None else amount * paid,
                         contributed=amount * row.contributions)

    views = [view(r) for r in outcome.rows]
    latest = view(outcome.latest)
    if lookup is None:
        buy_fees = floor_won(outcome.buy_fee_total)
        sale_krw = latest.row.balance
    else:
        buy_fees = floor_won(sum((v.row.trade_fee * v.fx_rate for v in views
                                  if v.row.trade_fee is not None and v.fx_rate is not None), _ZERO))
        # 표의 원화 잔고(그 행의 매매기준율로 평가한 값)를 판다 — 보이는 평가액과 매도 비용의 기준이
        # 같다.
        assert latest.balance_krw is not None
        sale_krw = latest.balance_krw
    as_of = rows[-1].day
    result = CryptoRecurringResult(
        views=views, latest=latest, as_of=as_of, is_final=as_of >= end,
        pending_after_end=pending_after_end, quote_dates=frozenset(r.day for r in rows),
        buy_fee_total_krw=buy_fees,
        sale_cost=crypto_sale_cost(sale_krw, fee_rate=fee_rate, day=as_of),
        daily=tuple(view(r) for r in outcome.daily) if daily else ())
    return PreparedCryptoRecurring(coin=coin, settings=settings, result=result)


def page(views: list[CryptoRecurringView], before: dt.date | None,
         limit: int) -> tuple[list[CryptoRecurringView], bool]:
    """커서 쪽(005 FR-029와 같다). 하루에 행이 많아야 하나라(납입 또는 그 달 첫 일봉) 날짜로
    자른다."""
    candidates = [v for v in views if before is None or v.row.date < before]
    return candidates[:limit], len(candidates) > limit
