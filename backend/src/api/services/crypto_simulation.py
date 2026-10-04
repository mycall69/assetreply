"""가상자산 시뮬레이션 조회·조합 (T032) — 007 FR-007~FR-009, FR-022, FR-024~FR-036.

**계산을 직접 하지 않는다.** 보유 계산은 `simulation/crypto_hold.py`, KRW 평가는
`simulation/fx_convert.evaluate_krw`의 순수 함수다(헌법 원칙 IV). 여기서는 읽어 넘기기만 한다.
**결과를 저장하지 않는다** — 일봉·설정·환율의 함수다(005 R5-9).

- 계산 끝은 **UTC 어제**다(FR-022). 한국 시간 어제로 두면 한국 오전 9시 전에 마감 전 일봉을 요구한다
- 원금 통화는 원화 또는 코인의 시세 통화뿐이다(FR-007). 원화면 첫 매수일에 환전(현금 살 때 +
  우대)하고, 평가는 그 행의 매매기준율
- 투자 수익·수익률은 원금 통화와 관계없이 **KRW 기준**이다(FR-035) — 주식과 같은 함수로 평가한다
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from src.api.errors import CurrencyPairNotAllowed, UnknownCoin
from src.api.services.stock_fx import (
    FxUnavailable,
    InitialExchange,
    build_exchange,
    cash_buy_spread,
    fx_currency_for,
    load_rates,
)
from src.api.services.stock_simulation import BeforeListing, NoPriceData
from src.db.models import CryptoCoin
from src.repository import crypto_daily
from src.repository.crypto_setting import CryptoSettings, get_settings
from src.simulation.crypto_hold import DayOpen, HoldCondition, HoldRow, simulate_hold
from src.simulation.fx_convert import (
    RateLookup,
    evaluate_krw,
    resolve_rate,
    to_foreign,
    to_principal,
)


def utc_yesterday(now: dt.datetime | None = None) -> dt.date:
    """마지막으로 마감된 UTC 하루 (FR-022). 출처의 일봉은 UTC 00:00 기준이다(헌법 원칙 V)."""
    return (now or dt.datetime.now(dt.UTC)).astimezone(dt.UTC).date() - dt.timedelta(days=1)


def allowed_principals(quote_currency: str) -> list[str]:
    """그 코인에 고를 수 있는 원금 통화 — 원화와 시세 통화뿐이다(FR-007)."""
    return list(dict.fromkeys(("KRW", quote_currency)))


def check_principal_currency(code: str, quote_currency: str) -> None:
    """**어느 경로로 들어온 요청이든** 이 함수를 지난다(이력 재실행, 직접 요청 — 006 FR-051과 같은
    이유)."""
    allowed = allowed_principals(quote_currency)
    if code not in allowed:
        raise CurrencyPairNotAllowed(
            f"원금 통화는 KRW 또는 코인의 시세 통화({quote_currency})여야 합니다: {code}", allowed)


async def require_coin(session: AsyncSession, coin_id: int) -> CryptoCoin:
    """코인을 찾는다. 없으면 404 — **빈 결과를 돌려주지 않는다**(사용자는 성과가 0이라고 읽는다)."""
    coin = await session.get(CryptoCoin, coin_id)
    if coin is None:
        raise UnknownCoin(
            f"목록에서 찾을 수 없는 코인입니다(id {coin_id}). 검색에서 다시 고르세요.")
    return coin


def require_start_available(coin: CryptoCoin, start: dt.date) -> None:
    """**수집 전** 판정 — 기록된 시작 가능 날짜보다 이르면 막는다(FR-008, research R7-10).

    수집하지 않는다 — 시작하면 받을 수 없는 구간을 기다리게 된다. 시작일을 몰래 옮기지 않는다.
    """
    if coin.first_available_date is not None and start < coin.first_available_date:
        raise BeforeListing(coin.first_available_date, "price_start")


@dataclass(frozen=True, slots=True)
class CryptoRowView:
    """KRW로 평가한 행. 행의 금액은 시세 통화로 남고, 투자 수익·수익률이 KRW 기준이다(FR-035)."""

    row: HoldRow
    #: 입력한 원금(원금 통화). 시뮬레이터 안의 원금은 환전한 시세 통화 금액이다.
    principal: Decimal
    profit: Decimal
    return_rate: Decimal
    fx_rate: Decimal | None = None
    fx_rate_date: dt.date | None = None
    balance_krw: Decimal | None = None


@dataclass(frozen=True, slots=True)
class CryptoResult:
    rows: list[CryptoRowView]
    latest: CryptoRowView | None
    as_of: dt.date
    is_final: bool
    bought_on: dt.date
    exchange: InitialExchange | None = None
    #: 원금의 KRW 값 — 원금 통화가 KRW가 아닐 때만. **첫 매수일의 매매기준율**이다(006 FR-068).
    principal_krw: Decimal | None = None
    #: 실제로 일봉이 있는 날 — 차트의 결측 판정에 쓴다.
    quote_dates: frozenset[dt.date] = frozenset()
    #: 일봉마다의 평가(오름차순). 차트가 요청할 때만 만든다 — 표는 월 행만 쓴다.
    daily: tuple[CryptoRowView, ...] = ()


@dataclass(frozen=True, slots=True)
class Prepared:
    """표와 차트가 **같은 함수를 같은 입력으로** 부르게 모아 둔다(005 SC-032와 같은 이유)."""

    coin: CryptoCoin
    settings: CryptoSettings
    result: CryptoResult


def _krw_principal(lookup: RateLookup, first_day: dt.date, principal: Decimal,
                   currency: str) -> Decimal:
    resolved = resolve_rate(lookup, first_day)
    if resolved is None:
        raise FxUnavailable(
            f"{first_day.isoformat()} 이전의 {currency} 환율이 없어 "
            "원금을 KRW로 평가할 수 없습니다.")
    return to_principal(principal, resolved[0], "KRW")


def _evaluate(row: HoldRow, *, lookup: RateLookup, principal: Decimal,
              basis: Decimal) -> CryptoRowView:
    """그 행의 **매매기준율로** KRW 평가한다. 초기 환율 하나로 전 구간을 평가하면 그 뒤의 환율
    변동이 사라진다."""
    resolved = resolve_rate(lookup, row.date)
    if resolved is None:
        raise FxUnavailable(f"{row.date.isoformat()} 이전의 환율이 없어 KRW로 평가할 수 없습니다.")
    rate, used = resolved
    krw = evaluate_krw(row.balance, row.cash, rate, basis)
    return CryptoRowView(row=row, principal=principal, profit=krw.profit,
                         return_rate=krw.return_rate, fx_rate=rate, fx_rate_date=used,
                         balance_krw=krw.balance_krw)


async def run_simulation(
    session: AsyncSession,
    coin: CryptoCoin,
    *,
    start: dt.date,
    end: dt.date,
    principal: Decimal,
    fee_rate: Decimal,
    lookup: RateLookup | None,
    spread: Decimal | None,
    daily: bool = False,
) -> CryptoResult:
    """일봉을 읽어 순수 함수에 넘긴다. 일봉이 끊기면 **마지막 일봉까지만** 계산한다(FR-024) — 이어
    그리지 않는다."""
    rows = await crypto_daily.bars(session, int(coin.id), start.replace(day=1), end)
    if not rows:
        raise NoPriceData("출처에 이 구간의 시세가 없습니다.")
    first_day = rows[0].day
    # **수집 후** 판정 — 시작 월에 일봉이 하나도 없으면 막는다(R7-10, 006 R6-8). 첫 매수가 몰래 뒤로
    # 밀리지 않게 한다.
    if (first_day.year, first_day.month) != (start.year, start.month):
        raise BeforeListing(first_day, "price_start")

    currency = coin.quote_currency
    exchange: InitialExchange | None = None
    principal_krw: Decimal | None = None
    if lookup is not None and spread is not None:
        # 원화 원금 — **실제로 매수하는 첫 일봉의 날**에 환전한다. 시작일이 아니다.
        exchange = build_exchange(lookup, first_day, spread, currency)
    elif lookup is not None:
        principal_krw = _krw_principal(lookup, first_day, principal, currency)
    working = to_foreign(principal, exchange.rate, currency) if exchange is not None else principal

    outcome = simulate_hold(
        [DayOpen(r.day, r.open) for r in rows],
        HoldCondition(start=start, principal=working, fee_rate=fee_rate,
                      first_available=coin.first_available_date))
    as_of = rows[-1].day
    assert outcome.bought_on is not None  # 일봉이 있으므로 산다
    quote_dates = frozenset(r.day for r in rows)

    if lookup is None:
        # 시세 통화가 KRW다 — 평가할 것이 없다.
        def plain(row: HoldRow) -> CryptoRowView:
            return CryptoRowView(row=row, principal=principal, profit=row.profit,
                                 return_rate=row.return_rate)
        views = [plain(r) for r in outcome.rows]
        latest = plain(outcome.latest) if outcome.latest else None
        per_day = [plain(r) for r in outcome.daily] if daily else []
    else:
        basis = principal_krw if principal_krw is not None else principal
        views = [_evaluate(r, lookup=lookup, principal=principal, basis=basis)
                 for r in outcome.rows]
        latest = (_evaluate(outcome.latest, lookup=lookup, principal=principal, basis=basis)
                  if outcome.latest else None)
        per_day = ([_evaluate(r, lookup=lookup, principal=principal, basis=basis)
                    for r in outcome.daily] if daily else [])
    return CryptoResult(
        rows=views, latest=latest, as_of=as_of, is_final=as_of >= end,
        bought_on=outcome.bought_on, exchange=exchange, principal_krw=principal_krw,
        quote_dates=quote_dates, daily=tuple(per_day))


async def prepare(
    session: AsyncSession,
    coin: CryptoCoin,
    *,
    start: dt.date,
    end: dt.date,
    principal: Decimal,
    principal_currency: str,
    daily: bool = False,
) -> Prepared:
    """설정·환율을 읽어 시뮬레이션을 돌린다. `daily`면 일봉마다의 평가도 만든다(차트)."""
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
    result = await run_simulation(
        session, coin, start=start, end=end, principal=principal,
        fee_rate=settings.trade_fee_rate, lookup=lookup, spread=spread, daily=daily)
    return Prepared(coin=coin, settings=settings, result=result)


def page(rows: list[CryptoRowView], before: dt.date | None,
         limit: int) -> tuple[list[CryptoRowView], bool]:
    """커서 방식 페이지(005 FR-029와 같다) — 오프셋을 쓰지 않는다."""
    candidates = [r for r in rows if before is None or r.row.date < before]
    return candidates[:limit], len(candidates) > limit
