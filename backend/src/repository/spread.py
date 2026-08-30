"""스프레드 설정 리포지토리 (T067).

FR-025: 허용 범위(0 이상 1 미만)를 벗어난 값은 거부하고 기존 값을 유지한다.
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.errors import InvalidSpread, UnknownCurrency
from src.db.models import FxSpread
from src.simulation.spread_calc import SpreadSet, is_valid_spread

FIELDS = ("cash_buy", "cash_sell", "remit_send", "remit_receive")


async def get_spread(session: AsyncSession, currency_code: str) -> FxSpread | None:
    return (await session.execute(
        select(FxSpread).where(
            FxSpread.currency_code == currency_code))).scalar_one_or_none()


async def list_spreads(session: AsyncSession) -> list[FxSpread]:
    return list((await session.execute(
        select(FxSpread).order_by(FxSpread.currency_code))).scalars())


async def spread_set(session: AsyncSession, currency_code: str) -> SpreadSet:
    """도메인 계산용 값 객체로 변환한다."""
    row = await get_spread(session, currency_code)
    if row is None:
        raise UnknownCurrency(f"스프레드 설정이 없습니다: {currency_code}")
    return SpreadSet(row.cash_buy, row.cash_sell, row.remit_send, row.remit_receive)


async def update_spread(
    session: AsyncSession, currency_code: str, values: dict[str, Decimal]
) -> FxSpread:
    """네 값을 모두 검증한 뒤에 적용한다.

    하나라도 범위를 벗어나면 아무것도 바꾸지 않는다 — 일부만 반영되면 사용자가 의도한
    조합과 다른 상태가 남는다.
    """
    row = await get_spread(session, currency_code)
    if row is None:
        raise UnknownCurrency(f"지원하지 않는 통화입니다: {currency_code}")

    invalid = [f for f in FIELDS if not is_valid_spread(values[f])]
    if invalid:
        raise InvalidSpread(
            f"스프레드는 0 이상 1 미만이어야 합니다: {', '.join(invalid)}")

    for field in FIELDS:
        setattr(row, field, values[field])
    return row
