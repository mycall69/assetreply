"""일자별 상세 조회와 파생 환율 조합 (T026).

**계산을 직접 하지 않는다.** 파생 환율은 `simulation/spread_calc.py`의 순수 함수를
호출만 한다 (헌법 원칙 IV). 표와 단일 날짜 조회가 다른 계산 경로를 타면 같은 입력에
다른 결과가 나올 수 있고, FR-027과 001의 재현성 보장이 함께 깨진다.

산출을 서버에서 하는 이유는 브라우저에 `Decimal`이 없기 때문이다. 클라이언트 계산은
곧 IEEE 754 연산이고, 이는 헌법 원칙 VI를 API 경계에서 무력화한다 (research R2-5).
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from src.api.services.period_rows import (
    PeriodUnit,
    is_ongoing,
    period_bounds,
    period_page,
    shifted_from,
)
from src.db.models import FxRate
from src.repository.spread import spread_set
from src.simulation.fx_change import Quote, RateChange, rate_change
from src.simulation.spread_calc import DerivedRates, SpreadSet, derive_rates


def derive_for_row(base_rate: Decimal, spread: SpreadSet) -> DerivedRates:
    """표 한 행의 파생 환율. 계산은 순수 함수에 위임한다 (FR-023)."""
    return derive_rates(base_rate, spread)


@dataclass(frozen=True, slots=True)
class PeriodRow:
    """표 한 행과 그 행이 덮는 구간 (004 data-model 3절).

    **세 사실을 각각 따로 싣는다.** `shifted_from`·`is_ongoing`·`rate.is_provisional`은
    동시에 참일 수 있고 서로 구별되어야 한다 (FR-015b). 하나로 합쳐 보내면 화면이
    되돌릴 수 없다 (research R4-4).
    """

    rate: FxRate
    period_from: dt.date
    period_to: dt.date
    shifted_from: dt.date | None
    is_ongoing: bool
    # 014 반복 2026-10-10d(FR-031) — 바로 아래 행 대비. 비교할 행이 없으면(저장된 첫 고시) `None`
    change: RateChange | None = None


@dataclass(frozen=True, slots=True)
class DailyPage:
    """표 한 페이지. 고시가 없는 날은 행이 없으므로 날짜가 연속하지 않는다 (FR-021)."""

    rows: list[PeriodRow]
    spread: SpreadSet
    has_more: bool
    oldest_returned: dt.date | None
    unit: PeriodUnit


async def daily_page(
    session: AsyncSession,
    currency_code: str,
    *,
    before: dt.date | None,
    limit: int,
    unit: PeriodUnit = "daily",
    today: dt.date | None = None,
) -> DailyPage:
    """최신순 `limit`건과 적용 스프레드를 함께 돌려준다 (FR-020, FR-026, 004 FR-006).

    `hasMore` 판정을 위해 한 건을 더 읽고 잘라낸다. 별도 count 질의를 돌리지 않는 이유는
    표가 최근 구간만 보여주므로 전체 개수가 필요 없기 때문이다.

    더 읽은 한 건은 쪽의 마지막 행이 견줄 **바로 아래 행**이기도 하다(014 반복 2026-10-10d
    — FR-031). 버리면 아래로 더 받을 때마다 쪽 경계의 행이 등락 없이("—") 보인다. 질의는
    늘지 않는다.

    `unit`이 `daily`면 001·002와 **완전히 같은 행**을 돌려준다. 구간 필드는 붙되
    `period_from == period_to == quote_date`이고 나머지 둘은 비어 있다 — 단위에 따라
    응답 구조가 달라지면 화면이 두 형태를 다뤄야 한다 (contracts/rest-api).
    """
    rows = await period_page(
        session, currency_code, unit=unit, before=before, limit=limit + 1)
    has_more = len(rows) > limit
    page = rows[:limit]
    spread = await spread_set(session, currency_code)
    now = today if today is not None else dt.date.today()
    below: list[FxRate | None] = [*rows[1:limit + 1], None][:len(page)]
    return DailyPage(
        rows=[_with_period(r, unit, now, b) for r, b in zip(page, below, strict=True)],
        spread=spread,
        has_more=has_more,
        oldest_returned=page[-1].quote_date if page else None,
        unit=unit,
    )


def _with_period(
    rate: FxRate, unit: PeriodUnit, today: dt.date, below: FxRate | None,
) -> PeriodRow:
    """행에 구간 정보와 등락을 입힌다. 판정·계산은 순수 함수에 위임한다."""
    start, end = period_bounds(rate.quote_date, unit)
    previous = None if below is None else Quote(date=below.quote_date, rate=below.base_rate)
    return PeriodRow(
        rate=rate,
        period_from=start,
        period_to=end,
        shifted_from=shifted_from(rate.quote_date, unit),
        is_ongoing=is_ongoing(end, today, unit),
        change=rate_change(rate.base_rate, previous),
    )
