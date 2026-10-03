"""시뮬레이션의 환전·환산 조합 (T073~T076) — 005 FR-019~023, FR-041a~041c.

**초기 환전과 평가 환산을 섞지 않는다.** 계산 자체는 `simulation/fx_convert.py`의
순수 함수가 하고, 여기서는 환율을 읽어 넘기기만 한다 (헌법 원칙 IV).

001~004가 쌓은 환율을 소비한다. 새로 만들지 않는다.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from src.config.settings import SUPPORTED_CURRENCIES
from src.db.models import Stock
from src.repository.fx_rate import series
from src.repository.spread import spread_set
from src.simulation.fx_convert import (
    SPREAD_DISCOUNT,
    RateLookup,
    exchange_rate,
    per_unit,
    resolve_rate,
)


class FxUnavailable(Exception):
    """환산에 필요한 환율이 없다 (409).

    **값을 만들어내지 않는다.** 환산할 수 없다는 사실이 드러나야 한다 (헌법 원칙 V).
    """


def fx_currency_for(stock: Stock) -> str | None:
    """KRW 평가에 외환 DB의 환율이 필요한 통화. 국내 종목이면 `None`이다 (006 FR-068).

    **원금 통화를 보지 않는다.** 투자 수익·수익율은 원금 통화와 관계없이 KRW라, 달러 원금으로 미국
    종목을 돌려도 환율이 필요하다. 반복 2026-10-03 #3까지는 "원금과 종목 통화가 같으면 필요
    없다"였다. 표·차트의 계산(`prepare`)과 수집 판정(`collecting_body`)이 이 함수 하나를 쓴다 —
    한쪽만 바꾸면 환율을 받지 않은 채 계산하러 가서 409가 나거나, 받아 놓고 쓰지 않는다.
    """
    if stock.currency == "KRW" or stock.currency not in SUPPORTED_CURRENCIES:
        return None
    return stock.currency


@dataclass(frozen=True, slots=True)
class InitialExchange:
    """초기 환전 1회의 결과 (FR-019~022)."""

    rate: Decimal
    rate_date: dt.date
    spread_discount: Decimal


async def load_rates(
    session: AsyncSession, currency: str, start: dt.date, end: dt.date
) -> RateLookup:
    """구간의 매매기준율을 날짜별로 읽는다.

    구간을 시작일보다 앞까지 넓혀 읽는다 — 시작일에 고시가 없으면 **가장 가까운
    이전 고시일로 날짜를 옮겨** 써야 하는데, 구간을 딱 맞춰 읽으면 옮길 곳이 없다.

    **날짜를 옮기는 것이지 값을 채우는 것이 아니다.** 옮긴 날짜를 함께 돌려주므로
    사용자가 보는 것은 언제나 실제로 고시된 날짜와 그날의 값이다 (FR-022, FR-041c).

    **1단위당 값으로 바꿔 둔다**(006 FR-042). 행의 고시 단위로 나눈다 — 엔화는 100엔당
    값이라 그대로 쓰면 환전이 100배 틀린다. 환전과 평가가 모두 이 값을 쓴다.
    """
    margin = start - dt.timedelta(days=30)
    rows = await series(session, currency, margin, end)
    return RateLookup({r.quote_date: per_unit(r.base_rate, r.quote_unit) for r in rows})


async def cash_buy_spread(session: AsyncSession, currency: str) -> Decimal:
    """그 통화의 현금 살 때 스프레드. 002가 만든 설정을 그대로 쓴다."""
    return (await spread_set(session, currency)).cash_buy


def build_exchange(
    lookup: RateLookup, on: dt.date, spread: Decimal, currency: str
) -> InitialExchange:
    """환전 환율을 만든다 (FR-019, FR-020).

    `on`은 **실제로 매수가 일어나는 첫 거래일**이다. 투자 시작 날짜가 아니다 —
    돈은 살 때 바꾸며, 시작 날짜가 휴일이면 그날의 환율도 없다.

    **현금 살 때 환율에 수수료 90% 우대**를 적용한다. 우대의 대상은 스프레드이며,
    스프레드의 90%를 깎아 결과적으로 10%만 적용된다.

    그날 고시가 없으면 가장 가까운 이전 고시일을 쓰고 **그 날짜를 함께 돌려준다**
    (FR-022).
    """
    resolved = resolve_rate(lookup, on)
    if resolved is None:
        raise FxUnavailable(
            f"{on.isoformat()} 이전의 {currency} 환율이 없어 환전할 수 없습니다.")
    base, used = resolved
    return InitialExchange(
        rate=exchange_rate(base, spread),
        rate_date=used,
        spread_discount=SPREAD_DISCOUNT,
    )
