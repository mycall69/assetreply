"""대시보드 지표 종가·원본·커버리지·개정 저장소 (014 T016) — FR-005, FR-017, FR-019, SC-006,
data-model 1.

- 종가는 `(지표, 현지 거래일)` 복합 기본 키다. **없는 날만 넣는다** — 있는 날의 값이 다르면 덮어쓰지
  않고 개정 한 줄을 남긴다
  (헌법 원칙 V — 확정 값의 재현성, 008 금리 개정과 같은 뜻). 그래서 방언 upsert가 아니라 "있는 날
  읽기 → 새 날만 삽입"이다
- 원본은 정규화와 따로, 본문 그대로다
- 커버리지는 **요청한 범위**다 — 휴장으로 새 행이 없어도 요청한 날까지 늘어난다(007
  `record_coverage`와 같다). 실패한 청크는
  넣지 않는다 — 받은 구간만 커버리지다(FR-019)
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Final

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.dialect import upsert
from src.db.models import (
    MarketCloseRevision,
    MarketIndicatorCoverage,
    MarketIndicatorDaily,
    MarketIndicatorRaw,
)

#: 저장할 때 남기는 출처 이름 — 어느 어댑터가 넣었는지 행에서 알 수 있어야 한다.
SOURCE: Final = "yahoo:chart"
#: 한 번에 넣는 행 수. 730일 청크가 한 번에 들어간다.
_BATCH: Final = 1000
#: 실패 문구 열의 길이(data-model 1.3).
_MESSAGE_MAX: Final = 500

Close = tuple[dt.date, Decimal]


@dataclass(frozen=True, slots=True)
class Revision:
    """확정으로 저장한 날의 값이 출처에서 달랐다 — 저장 값은 그대로다."""

    trade_date: dt.date
    stored_close: Decimal
    source_close: Decimal


@dataclass(frozen=True, slots=True)
class StoreResult:
    inserted: int
    revisions: list[Revision] = field(default_factory=list)


async def store_closes(
    session: AsyncSession, indicator_id: str, closes: Sequence[Close], *, detected_at: dt.datetime
) -> StoreResult:
    """없는 날만 넣고, 있는 날의 값이 다르면 개정을 남긴다. 같은 개정은 한 번만 넣는다."""
    if not closes:
        return StoreResult(0)
    days = [day for day, _ in closes]
    existing = {
        row.trade_date: row.close
        for row in (
            await session.execute(
                select(MarketIndicatorDaily).where(
                    MarketIndicatorDaily.indicator_id == indicator_id,
                    MarketIndicatorDaily.trade_date >= min(days),
                    MarketIndicatorDaily.trade_date <= max(days),
                )
            )
        ).scalars()
    }
    known = {
        (row.trade_date, row.source_close)
        for row in (
            await session.execute(
                select(MarketCloseRevision).where(
                    MarketCloseRevision.indicator_id == indicator_id,
                    MarketCloseRevision.trade_date >= min(days),
                    MarketCloseRevision.trade_date <= max(days),
                )
            )
        ).scalars()
    }

    fresh: list[MarketIndicatorDaily] = []
    revisions: list[Revision] = []
    for day, value in closes:
        stored = existing.get(day)
        if stored is None:
            fresh.append(
                MarketIndicatorDaily(
                    indicator_id=indicator_id, trade_date=day, close=value, source=SOURCE
                )
            )
            existing[day] = value
        elif stored != value and (day, value) not in known:
            revisions.append(Revision(day, stored, value))
            known.add((day, value))
    for start in range(0, len(fresh), _BATCH):
        session.add_all(fresh[start : start + _BATCH])
        await session.flush()
    for revision in revisions:
        session.add(
            MarketCloseRevision(
                indicator_id=indicator_id,
                trade_date=revision.trade_date,
                stored_close=revision.stored_close,
                source_close=revision.source_close,
                detected_at=detected_at,
            )
        )
    if revisions:
        await session.flush()
    return StoreResult(len(fresh), revisions)


async def store_raw(
    session: AsyncSession,
    indicator_id: str,
    *,
    requested_from: dt.date,
    requested_to: dt.date,
    status_code: int,
    body: str,
    received_at: dt.datetime,
) -> None:
    """원본 응답을 그대로 남긴다. 주소·머리는 남기지 않는다."""
    session.add(
        MarketIndicatorRaw(
            indicator_id=indicator_id,
            requested_from=requested_from,
            requested_to=requested_to,
            status_code=status_code,
            body=body,
            received_at=received_at,
        )
    )
    await session.flush()


async def get_coverage(session: AsyncSession, indicator_id: str) -> MarketIndicatorCoverage | None:
    return await session.get(MarketIndicatorCoverage, indicator_id, populate_existing=True)


async def _ensure_coverage(session: AsyncSession, indicator_id: str) -> MarketIndicatorCoverage:
    row = await get_coverage(session, indicator_id)
    if row is None:
        row = MarketIndicatorCoverage(indicator_id=indicator_id)
        session.add(row)
        await session.flush()
    return row


async def record_coverage(
    session: AsyncSession, indicator_id: str, start: dt.date, end: dt.date
) -> None:
    """받은 범위를 합친다. **덮어쓰지 않는다** — 덮어쓰면 앞서 받은 구간을 잊어 다시 받는다(005와
    같다).

    차례는 수집 실행기가 정한다 — 늘 지금 구간에 맞닿은 청크를 받으므로 합친 구간이 연속이다.
    """
    current = await get_coverage(session, indicator_id)
    if (
        current is not None
        and current.covered_from is not None
        and current.covered_through is not None
    ):
        start, end = min(start, current.covered_from), max(end, current.covered_through)
    await upsert(
        session,
        MarketIndicatorCoverage,
        [{"indicator_id": indicator_id, "covered_from": start, "covered_through": end}],
        preserve=(),
    )


async def record_first_day(session: AsyncSession, indicator_id: str, day: dt.date) -> None:
    """출처의 첫 거래일을 기록한다. 이미 더 이른 날이 있으면 두지 않는다."""
    row = await _ensure_coverage(session, indicator_id)
    if row.first_day is None or day < row.first_day:
        row.first_day = day
        await session.flush()


async def record_success(session: AsyncSession, indicator_id: str, *, at: dt.datetime) -> None:
    row = await _ensure_coverage(session, indicator_id)
    row.last_success_at = at
    await session.flush()


async def record_failure(
    session: AsyncSession, indicator_id: str, *, at: dt.datetime, kind: str, message: str | None
) -> None:
    """마지막 실패를 남긴다. 성공 기록은 지우지 않는다 — 화면은 시각을 견줘 "성공 뒤의 실패"만
    보인다(FR-019)."""
    row = await _ensure_coverage(session, indicator_id)
    row.last_failure_at = at
    row.last_failure_kind = kind
    row.last_failure_message = None if message is None else message[:_MESSAGE_MAX]
    await session.flush()


async def closes(
    session: AsyncSession,
    indicator_id: str,
    start: dt.date | None = None,
    end: dt.date | None = None,
) -> list[Close]:
    """(구간의) 종가를 날짜 오름차순으로. 휴장일은 행이 없어 날짜가 연속하지 않는다 — 그것이
    정상이다."""
    stmt = select(MarketIndicatorDaily.trade_date, MarketIndicatorDaily.close).where(
        MarketIndicatorDaily.indicator_id == indicator_id
    )
    if start is not None:
        stmt = stmt.where(MarketIndicatorDaily.trade_date >= start)
    if end is not None:
        stmt = stmt.where(MarketIndicatorDaily.trade_date <= end)
    rows = (await session.execute(stmt.order_by(MarketIndicatorDaily.trade_date))).all()
    return [(row[0], row[1]) for row in rows]


async def previous_close(session: AsyncSession, indicator_id: str, before: dt.date) -> Close | None:
    """`before`보다 앞선 마지막 저장 종가(카드의 전일 종가 — FR-005). 없으면 `None`."""
    row = (
        await session.execute(
            select(MarketIndicatorDaily.trade_date, MarketIndicatorDaily.close)
            .where(
                MarketIndicatorDaily.indicator_id == indicator_id,
                MarketIndicatorDaily.trade_date < before,
            )
            .order_by(MarketIndicatorDaily.trade_date.desc())
            .limit(1)
        )
    ).first()
    return None if row is None else (row[0], row[1])


async def coverage_reaches(session: AsyncSession, indicator_id: str, day: dt.date) -> bool:
    """커버리지 끝이 `day`에 닿았는가."""
    row = await get_coverage(session, indicator_id)
    return row is not None and row.covered_through is not None and row.covered_through >= day
