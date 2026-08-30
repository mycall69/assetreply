"""날짜별 환율 조회 서비스 (T052).

FR-016~020, FR-018a/b. 고시가 없는 날에 값을 만들어내지 않는 것이 이 모듈의 핵심 책임이다
(헌법 원칙 V).

영업일 판정에 별도의 휴장일 캘린더를 쓰지 않는다. 커버리지 안에서 값이 있는 날이 곧
영업일이다 (research R8).
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from src.api.errors import OutOfRange
from src.repository.coverage import get_coverage
from src.repository.fx_rate import get_rate, previous_business_day
from src.repository.spread import spread_set
from src.simulation.spread_calc import DerivedRates, SpreadSet, derive_rates


@dataclass(frozen=True, slots=True)
class Reference:
    """참고 정보 — 요청일의 값이 **아니다**. UI에서 주 결과와 분리 표시한다."""

    kind: str
    quote_date: dt.date
    quote_unit: int
    base_rate: Decimal
    note: str


@dataclass(frozen=True, slots=True)
class RateResult:
    """조회 결과. `no_quote`일 때 `base_rate`는 반드시 None이다."""

    status: str
    currency: str
    date: dt.date
    quote_unit: int | None = None
    base_rate: Decimal | None = None
    source: str | None = None
    message: str | None = None
    reference: Reference | None = None
    derived: DerivedRates | None = None
    applied_spread: SpreadSet | None = None
    # 현재 설정된 스프레드를 과거 날짜에 적용한 가정 비교임을 나타낸다 (FR-026a)
    spread_basis: str | None = None


async def query_rate(
    session: AsyncSession, currency_code: str, target: dt.date
) -> RateResult:
    """해당일의 매매기준율을 조회한다.

    고시가 없으면 값을 보간하거나 인접일 값으로 대체해 반환하지 않는다. 직전 영업일 값은
    별도의 참고 정보로만 담는다 (FR-018·018a·018b).
    """
    coverage = await get_coverage(session, currency_code)
    if coverage is None:
        raise OutOfRange("아직 수집된 데이터가 없습니다.")

    today = dt.date.today()
    if target >= today:
        raise OutOfRange(
            f"조회 가능한 범위를 벗어났습니다. {coverage.covered_from} ~ "
            f"{min(coverage.covered_through, today - dt.timedelta(days=1))}")
    if target < coverage.covered_from:
        raise OutOfRange(
            f"조회 가능한 범위를 벗어났습니다. {coverage.covered_from} ~ "
            f"{coverage.covered_through}")

    row = await get_rate(session, currency_code, target)
    if row is not None:
        spread = await spread_set(session, currency_code)
        return RateResult(
            status="quoted", currency=currency_code, date=target,
            quote_unit=row.quote_unit, base_rate=row.base_rate, source=row.source,
            derived=derive_rates(row.base_rate, spread),
            applied_spread=spread, spread_basis="current")

    prev = await previous_business_day(
        session, currency_code, target, not_before=coverage.covered_from)
    reference = None if prev is None else Reference(
        kind="previous_business_day",
        quote_date=prev.quote_date,
        quote_unit=prev.quote_unit,
        base_rate=prev.base_rate,
        note=f"요청하신 {target.isoformat()}의 값이 아닙니다.")

    return RateResult(
        status="no_quote", currency=currency_code, date=target,
        message="해당일에는 고시가 없습니다.", reference=reference)
