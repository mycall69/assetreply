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

from src.repository.fx_rate import series
from src.repository.spread import spread_set
from src.simulation.fx_convert import (
    SPREAD_DISCOUNT,
    RateLookup,
    exchange_rate,
    resolve_rate,
)


class FxUnavailable(Exception):
    """환산에 필요한 환율이 없다 (409).

    **값을 만들어내지 않는다.** 환산할 수 없다는 사실이 드러나야 한다 (헌법 원칙 V).
    """


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
    """
    margin = start - dt.timedelta(days=30)
    rows = await series(session, currency, margin, end)
    return RateLookup({r.quote_date: r.base_rate for r in rows})


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
