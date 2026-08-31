"""환율 시계열 리포지토리 (T047, T010).

upsert는 `db/dialect.py` 헬퍼만 호출한다. 방언 구문을 직접 쓰면 헌법 위반이다.

**확정/잠정 구분** (헌법 v5.0.0 원칙 V): 재현성 보장은 확정값에 대한 것이다.
`confirmed_only=True`로 조회하면 잠정 행이 제외되며, 이것이 SC-003(같은 날짜를 반복
조회하면 항상 같은 값)의 구현 근거다. 화면용 조회는 잠정을 포함하되 상태를 함께 내려
사용자가 구분할 수 있게 한다(FR-014, FR-017a, FR-025).
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import FxRate


async def get_rate(
    session: AsyncSession, currency_code: str, quote_date: dt.date,
    *, confirmed_only: bool = False,
) -> FxRate | None:
    stmt = select(FxRate).where(
        FxRate.currency_code == currency_code,
        FxRate.quote_date == quote_date)
    if confirmed_only:
        stmt = stmt.where(FxRate.is_provisional.is_(False))
    return (await session.execute(stmt)).scalar_one_or_none()


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


async def latest(
    session: AsyncSession, currency_code: str, *, confirmed_only: bool = False
) -> FxRate | None:
    """가장 최근 고시 (FR-011). 잠정 오늘 값이 있으면 그것이 최근이다."""
    stmt = select(FxRate).where(FxRate.currency_code == currency_code)
    if confirmed_only:
        stmt = stmt.where(FxRate.is_provisional.is_(False))
    return (await session.execute(
        stmt.order_by(FxRate.quote_date.desc()).limit(1))).scalar_one_or_none()


async def page_before(
    session: AsyncSession, currency_code: str, *, before: dt.date | None, limit: int
) -> list[FxRate]:
    """`before` 미만의 고시일을 최신순으로 `limit`건 (FR-020, FR-026).

    고시가 없는 날은 행 자체가 없으므로 날짜가 연속하지 않는다. 그것이 정상이다
    (FR-021 — 없는 값을 만들어 채우지 않는다).
    """
    stmt = select(FxRate).where(FxRate.currency_code == currency_code)
    if before is not None:
        stmt = stmt.where(FxRate.quote_date < before)
    return list((await session.execute(
        stmt.order_by(FxRate.quote_date.desc()).limit(limit))).scalars())


async def series(
    session: AsyncSession, currency_code: str, start: dt.date, end: dt.date,
    *, confirmed_only: bool = False,
) -> list[FxRate]:
    stmt = select(FxRate).where(
        FxRate.currency_code == currency_code,
        FxRate.quote_date >= start,
        FxRate.quote_date <= end)
    if confirmed_only:
        stmt = stmt.where(FxRate.is_provisional.is_(False))
    return list((await session.execute(stmt.order_by(FxRate.quote_date))).scalars())
