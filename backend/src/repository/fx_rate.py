"""환율 시계열 리포지토리 (T047).

upsert는 `db/dialect.py` 헬퍼만 호출한다. 방언 구문을 직접 쓰면 헌법 v4.0.0 위반이다.
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import FxRate


async def get_rate(
    session: AsyncSession, currency_code: str, quote_date: dt.date
) -> FxRate | None:
    return (await session.execute(
        select(FxRate).where(
            FxRate.currency_code == currency_code,
            FxRate.quote_date == quote_date))).scalar_one_or_none()


async def previous_business_day(
    session: AsyncSession, currency_code: str, before: dt.date, *, not_before: dt.date
) -> FxRate | None:
    """`before` 미만에서 값이 존재하는 가장 가까운 날 (research R8).

    별도의 휴장일 캘린더를 두지 않는다. 출처가 값을 주지 않은 것이 곧 "고시 없음"의
    정의이며, 커버리지 안에서 값이 있는 날이 곧 영업일이다.
    """
    return (await session.execute(
        select(FxRate)
        .where(FxRate.currency_code == currency_code,
               FxRate.quote_date < before,
               FxRate.quote_date >= not_before)
        .order_by(FxRate.quote_date.desc())
        .limit(1))).scalar_one_or_none()


async def series(
    session: AsyncSession, currency_code: str, start: dt.date, end: dt.date
) -> list[FxRate]:
    return list((await session.execute(
        select(FxRate)
        .where(FxRate.currency_code == currency_code,
               FxRate.quote_date >= start,
               FxRate.quote_date <= end)
        .order_by(FxRate.quote_date))).scalars())
