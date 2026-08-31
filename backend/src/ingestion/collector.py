"""수집기 — 청크 분할, 청크별 커밋, 재개 (T044, T050).

FR-005: 전체 구간을 날짜 청크로 나눠 순차 요청한다. 전 구간을 한 번에 요청하지 않는다.
FR-010: 청크가 성공할 때마다 저장·커밋하고 커버리지를 갱신한다.
FR-011: 재실행 시 마지막 완료 청크의 다음 구간부터 재개한다.
research R3: 선두 구간이 데이터 없음이면 실제 최초 제공일을 런타임에 발견해 기록한다.
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.dialect import upsert
from src.db.models import Currency, FxCoverage, FxRate, FxRawResponse
from src.ingestion.protocols import FetchOutcome, FxRateSource

SOURCE_ID = "ECOS:731Y001"

DateRange = tuple[dt.date, dt.date]


def split_into_chunks(start: dt.date, end: dt.date, *, chunk_days: int) -> list[DateRange]:
    """구간을 `chunk_days` 단위로 나눈다. 청크는 겹치지 않고 빈틈도 없다."""
    if chunk_days <= 0:
        raise ValueError(f"chunk_days는 1 이상이어야 합니다: {chunk_days}")
    if end < start:
        return []

    chunks: list[DateRange] = []
    cursor = start
    step = dt.timedelta(days=chunk_days - 1)
    while cursor <= end:
        chunk_end = min(cursor + step, end)
        chunks.append((cursor, chunk_end))
        cursor = chunk_end + dt.timedelta(days=1)
    return chunks


async def next_start_date(
    session: AsyncSession, currency_code: str, *, default: dt.date
) -> dt.date:
    """수집 시작일 — 재개 지점 또는 역방향 백필 지점 (FR-002, FR-011).

    커버리지가 탐색 시작일보다 **늦게** 시작하면 앞쪽 구간이 비어 있다는 뜻이므로
    그곳부터 채운다. 이 분기가 없으면 탐색 시작일을 앞당겨도 이미 커버리지가 있는
    통화는 `covered_through + 1`만 돌려주어 과거를 영원히 수집하지 않는다.
    실제로 이 때문에 USD 31년치가 조용히 누락됐다 (헌법 v4.1.0 개정 사유).
    """
    row = (await session.execute(
        select(FxCoverage).where(
            FxCoverage.currency_code == currency_code))).scalar_one_or_none()
    if row is None:
        return default
    if row.covered_from > default:
        return default
    return row.covered_through + dt.timedelta(days=1)


async def _record_coverage(
    session: AsyncSession, currency_code: str, start: dt.date, through: dt.date
) -> None:
    existing = (await session.execute(
        select(FxCoverage).where(FxCoverage.currency_code == currency_code))
    ).scalar_one_or_none()
    if existing is None:
        await upsert(session, FxCoverage, [{
            "currency_code": currency_code,
            "covered_from": start,
            "covered_through": through,
        }], preserve=())
    else:
        # 앞뒤 양방향으로 확장한다. 뒤쪽만 갱신하면 역방향 백필 결과가 유실된다 (FR-002).
        if start < existing.covered_from:
            existing.covered_from = start
        if through > existing.covered_through:
            existing.covered_through = through


async def _record_first_available(
    session: AsyncSession, currency_code: str, first_date: dt.date
) -> None:
    """실제 최초 제공일을 발견해 기록한다 (FR-002a, research R3).

    이미 기록된 값보다 이른 날짜를 찾으면 갱신한다. 역방향 백필로 더 과거를 수집하면
    앞서 기록한 값은 진짜 최초일이 아니었던 것이므로 그대로 두면 안 된다.
    """
    current = (await session.execute(
        select(Currency.first_available_date).where(Currency.code == currency_code))
    ).scalar_one_or_none()
    if current is None or first_date < current:
        await session.execute(
            update(Currency).where(Currency.code == currency_code)
            .values(first_available_date=first_date))


async def collect_range(
    session: AsyncSession,
    source: FxRateSource,
    currency_code: str,
    start: dt.date,
    end: dt.date,
    *,
    chunk_days: int,
) -> int:
    """구간을 청크로 나눠 수집한다. 저장된 고시 건수를 돌려준다.

    각 청크는 성공 즉시 커밋된다. 중간에 실패해도 이미 커밋된 구간과 커버리지는 유효하다
    (FR-013).
    """
    stored = 0
    for chunk_start, chunk_end in split_into_chunks(start, end, chunk_days=chunk_days):
        result = await source.fetch_daily_rates(currency_code, chunk_start, chunk_end)

        session.add(FxRawResponse(
            currency_code=currency_code,
            requested_from=chunk_start,
            requested_to=chunk_end,
            http_status=result.raw_status,
            result_code=result.raw_result_code,
            body=result.raw_body,
        ))

        if result.outcome is FetchOutcome.OK and result.quotes:
            # `is_provisional=False`를 명시하는 것이 잠정→확정 전환의 전부다 (FR-037a).
            # 이 값을 빼면 잠정 행을 덮어써도 상태가 그대로 남아 영원히 확정되지 않는다.
            await upsert(session, FxRate, [{
                "currency_code": currency_code,
                "quote_date": q.quote_date,
                "base_rate": q.base_rate,
                "quote_unit": q.quote_unit,
                "source": SOURCE_ID,
                "is_provisional": False,
            } for q in result.quotes])
            stored += len(result.quotes)
            await _record_first_available(session, currency_code, result.quotes[0].quote_date)

        await _record_coverage(session, currency_code, start, chunk_end)
        await session.commit()
    return stored
