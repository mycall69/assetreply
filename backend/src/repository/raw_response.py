"""원본 응답 리포지토리 (T048).

FR-004a: 기한 없이 보관한다. 자동 정리를 하지 않는다 — 값이 갱신된 경우 갱신 전 값을
추적하는 유일한 근거이기 때문이다(FR-003b).
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import FxRawResponse


async def count_for_currency(session: AsyncSession, currency_code: str) -> int:
    return (await session.execute(
        select(func.count()).select_from(FxRawResponse)
        .where(FxRawResponse.currency_code == currency_code))).scalar_one()


async def count_calls_on(session: AsyncSession, day: dt.date) -> int:
    """그 날짜에 데이터 출처를 호출한 수 (003 FR-024, research R3-5).

    001은 성공·실패와 무관하게 모든 외부 응답을 이 테이블에 남긴다. 즉 **행 수가 곧
    호출 수**다. 별도 집계 테이블을 두면 두 숫자가 갈라질 수 있고, 갈라지면 어느 쪽이
    맞는지 판단할 근거가 없다.

    기준일은 서버 날짜를 따른다. 출처의 한도 리셋 시각은 비공개이므로 이 값은
    **참고 지표**이며 한도 판정의 근거가 아니다 — 판정은 출처가 돌려주는 신호로만 한다.
    """
    start = dt.datetime.combine(day, dt.time.min)
    end = start + dt.timedelta(days=1)
    return (await session.execute(
        select(func.count()).select_from(FxRawResponse)
        .where(FxRawResponse.received_at >= start)
        .where(FxRawResponse.received_at < end))).scalar_one()


async def recent(
    session: AsyncSession, currency_code: str, *, limit: int = 20
) -> list[FxRawResponse]:
    return list((await session.execute(
        select(FxRawResponse)
        .where(FxRawResponse.currency_code == currency_code)
        .order_by(FxRawResponse.received_at.desc())
        .limit(limit))).scalars())
