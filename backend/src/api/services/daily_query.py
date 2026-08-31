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

from src.db.models import FxRate
from src.repository.fx_rate import page_before
from src.repository.spread import spread_set
from src.simulation.spread_calc import DerivedRates, SpreadSet, derive_rates


def derive_for_row(base_rate: Decimal, spread: SpreadSet) -> DerivedRates:
    """표 한 행의 파생 환율. 계산은 순수 함수에 위임한다 (FR-023)."""
    return derive_rates(base_rate, spread)


@dataclass(frozen=True, slots=True)
class DailyPage:
    """표 한 페이지. 고시가 없는 날은 행이 없으므로 날짜가 연속하지 않는다 (FR-021)."""

    rows: list[FxRate]
    spread: SpreadSet
    has_more: bool
    oldest_returned: dt.date | None


async def daily_page(
    session: AsyncSession,
    currency_code: str,
    *,
    before: dt.date | None,
    limit: int,
) -> DailyPage:
    """최신순 `limit`건과 적용 스프레드를 함께 돌려준다 (FR-020, FR-026).

    `hasMore` 판정을 위해 한 건을 더 읽고 잘라낸다. 별도 count 질의를 돌리지 않는 이유는
    표가 최근 구간만 보여주므로 전체 개수가 필요 없기 때문이다.
    """
    rows = await page_before(session, currency_code, before=before, limit=limit + 1)
    has_more = len(rows) > limit
    page = rows[:limit]
    spread = await spread_set(session, currency_code)
    return DailyPage(
        rows=page,
        spread=spread,
        has_more=has_more,
        oldest_returned=page[-1].quote_date if page else None,
    )
