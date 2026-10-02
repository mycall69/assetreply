"""검색용 종목 목록 리포지토리 (T034) — 006 FR-014, FR-015, FR-019, FR-019a, FR-061, data-model
1~4a절.

**종목·원본 테이블에 삭제 질의를 두지 않는다.** 목록에서 빠진 종목은 `missing`으로 표시하고(FR-019),
원본 응답은 지우지 않는다(헌법 원칙 V, research R6-13). 지울 수 있는 것은 점유 행뿐이다.

**종목은 국가와 코드로 식별한다**(FR-019a). 단위는 키가 아니다 — 이전상장으로 단위가 바뀌어도 행은
하나이고, 새 단위의 갱신이 그 행의 단위를 바꾼다. "빠짐" 표시는 **지금 그 단위에 속한 행만** 한다.
그래서 어느 단위가 먼저 갱신되든 결과가 같다(research R6-4).

갱신은 수천 건이라 행마다 ORM 객체를 고치지 않고 **묶음 질의**로 한다. 표준 `INSERT`·`UPDATE`만
쓴다(헌법 DB 운영 규약) — 방언별 upsert는 기본 키 충돌만 다루는데 이 테이블의 식별은 보조 유니크
키다.
"""

from __future__ import annotations

import datetime as dt
import hashlib
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from sqlalchemy import delete, func, insert, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import (
    StockListing,
    StockListingLock,
    StockListingRaw,
    StockListingRawBody,
    StockListingRefresh,
)
from src.ingestion.kiwoom.parse import ListingRow

#: 한 질의에 싣는 행·식별자 수. 너무 크면 패킷 한도에, 너무 작으면 왕복 수에 걸린다.
_CHUNK = 500
_LAST_ERROR_LENGTH = 512


def _chunks[T](items: Sequence[T], size: int = _CHUNK) -> Iterable[Sequence[T]]:
    for start in range(0, len(items), size):
        yield items[start:start + size]


# ── 갱신 기록 ─────────────────────────────────────────────────────────


async def get_refresh(session: AsyncSession, unit: str) -> StockListingRefresh | None:
    return await session.get(StockListingRefresh, unit)


async def all_refresh(session: AsyncSession) -> dict[str, StockListingRefresh]:
    rows = (await session.execute(select(StockListingRefresh))).scalars()
    return {row.unit: row for row in rows}


async def _refresh_row(session: AsyncSession, unit: str) -> StockListingRefresh:
    row = await session.get(StockListingRefresh, unit)
    if row is None:
        row = StockListingRefresh(unit=unit, attempts=0)
        session.add(row)
    return row


async def record_attempt(
    session: AsyncSession, unit: str, now: dt.datetime, today: dt.date
) -> None:
    """시도 횟수를 그날(한국 시간)로 센다 (FR-013a). 날이 바뀌면 처음부터 센다."""
    row = await _refresh_row(session, unit)
    if row.attempt_date != today:
        row.attempt_date = today
        row.attempts = 0
    row.attempts = (row.attempts or 0) + 1
    row.last_attempt_at = now
    await session.flush()


async def record_failure(
    session: AsyncSession, unit: str, now: dt.datetime, kind: str, message: str
) -> None:
    """실패 종류와 사유를 남긴다. **기준 시각(`as_of`)은 바꾸지 않는다** — 이전 목록이 그대로다."""
    row = await _refresh_row(session, unit)
    row.last_failed_at = now
    row.last_error_kind = kind
    row.last_error = message[:_LAST_ERROR_LENGTH]
    await session.flush()


async def index_version(session: AsyncSession) -> dt.datetime | None:
    """검색 색인의 버전 — 단위별 기준 시각의 최댓값. 교체가 일어나면 바뀐다."""
    return (await session.execute(select(func.max(StockListingRefresh.as_of)))).scalar_one()


# ── 종목 ──────────────────────────────────────────────────────────────


async def load_listings(session: AsyncSession) -> list[StockListing]:
    return list((await session.execute(select(StockListing))).scalars())


async def get_listing(session: AsyncSession, listing_id: int) -> StockListing | None:
    return await session.get(StockListing, listing_id)


async def find_listing(
    session: AsyncSession, country: str, code: str
) -> StockListing | None:
    return (await session.execute(select(StockListing).where(
        StockListing.country == country, StockListing.code == code))).scalar_one_or_none()


@dataclass(frozen=True, slots=True)
class ReplaceCounts:
    inserted: int
    updated: int
    missing: int


def _changed(row: StockListing, incoming: ListingRow) -> bool:
    return (row.unit, row.name_ko, row.name_en, row.kind, row.listed_on, row.status) != (
        incoming.unit, incoming.name_ko, incoming.name_en, incoming.kind,
        incoming.listed_on, "listed")


async def replace_unit(
    session: AsyncSession,
    unit: str,
    rows: Sequence[ListingRow],
    *,
    now: dt.datetime,
    today: dt.date,
    source: str,
) -> ReplaceCounts:
    """한 단위의 목록을 교체한다. **커밋하지 않는다** — 호출자가 한 트랜잭션으로 묶는다.

    1. 받은 종목을 넣거나 고친다(단위가 바뀐 종목은 그 단위로 옮긴다)
    2. 지금 이 단위에 속했는데 이번에 없는 종목을 `missing`으로 표시한다 — 지우지 않는다
    3. 갱신 기록의 기준 시각과 건수를 바꾼다
    """
    countries = {r.country for r in rows}
    existing: dict[tuple[str, str], StockListing] = {}
    for country in countries:
        found = (await session.execute(
            select(StockListing).where(StockListing.country == country))).scalars()
        existing.update({(r.country, r.code): r for r in found})

    new_rows: list[dict[str, object]] = []
    seen_ids: list[int] = []
    for incoming in rows:
        current = existing.get((incoming.country, incoming.code))
        if current is None:
            new_rows.append({
                "country": incoming.country, "code": incoming.code, "unit": incoming.unit,
                "name_ko": incoming.name_ko, "name_en": incoming.name_en,
                "kind": incoming.kind, "listed_on": incoming.listed_on, "status": "listed",
                "first_seen_at": now, "last_seen_at": now, "source": source,
            })
            continue
        seen_ids.append(int(current.id))
        if _changed(current, incoming):
            await session.execute(update(StockListing).where(
                StockListing.id == current.id).values(
                unit=incoming.unit, name_ko=incoming.name_ko, name_en=incoming.name_en,
                kind=incoming.kind, listed_on=incoming.listed_on, status="listed",
                source=source))

    for chunk in _chunks(seen_ids):
        await session.execute(update(StockListing).where(
            StockListing.id.in_(chunk)).values(last_seen_at=now))
    for batch in _chunks(new_rows):
        await session.execute(insert(StockListing), list(batch))

    # 지금 이 단위에 속한 행만 본다 — 다른 단위로 옮긴 종목을 여기서 "빠짐"으로 만들지 않는다.
    incoming_codes = {(r.country, r.code) for r in rows}
    in_unit = (await session.execute(
        select(StockListing.id, StockListing.country, StockListing.code).where(
            StockListing.unit == unit, StockListing.status == "listed"))).all()
    missing_ids = [int(i) for i, c, code in in_unit if (c, code) not in incoming_codes]
    for chunk in _chunks(missing_ids):
        await session.execute(update(StockListing).where(
            StockListing.id.in_(chunk)).values(status="missing"))

    refresh = await _refresh_row(session, unit)
    refresh.as_of = now
    refresh.as_of_date = today
    refresh.row_count = len(rows)
    refresh.last_error_kind = None
    refresh.last_error = None
    await session.flush()
    # 묶음 질의로 고친 행이 세션의 객체에 남은 옛 값으로 읽히지 않게 한다.
    session.expire_all()
    return ReplaceCounts(len(new_rows), len(seen_ids), len(missing_ids))


# ── 원본 ──────────────────────────────────────────────────────────────


def body_digest(body: str) -> str:
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class RawPage:
    page_no: int
    status_code: int
    body: str


async def store_raw_pages(
    session: AsyncSession,
    unit: str,
    pages: Sequence[RawPage],
    *,
    batch_started_at: dt.datetime,
    fetched_at: dt.datetime,
) -> None:
    """쪽마다 기록을 남기고, 본문은 **같은 것이 없을 때만** 넣는다 (research R6-13).

    헤더는 받지 않는다 — 인증 헤더가 섞이면 토큰이 DB에 평문으로 남는다(FR-061).
    """
    digests = [body_digest(p.body) for p in pages]
    known = set((await session.execute(select(StockListingRawBody.sha256).where(
        StockListingRawBody.sha256.in_(set(digests))))).scalars()) if digests else set()
    for page, digest in zip(pages, digests, strict=True):
        if digest not in known:
            session.add(StockListingRawBody(
                sha256=digest, body=page.body, first_stored_at=fetched_at))
            known.add(digest)
    # 본문을 먼저 내보낸다. 관계(relationship)를 두지 않은 외래 키는 작업 단위가 순서를 정하지 않아,
    # 한 번에 내보내면 쪽 기록이 본문보다 먼저 들어가 외래 키에 걸린다.
    await session.flush()
    for page, digest in zip(pages, digests, strict=True):
        session.add(StockListingRaw(
            unit=unit, batch_started_at=batch_started_at, page_no=page.page_no,
            status_code=page.status_code, body_sha256=digest, fetched_at=fetched_at))
    await session.flush()


# ── 점유 ──────────────────────────────────────────────────────────────


async def try_lock(session: AsyncSession, unit: str, now: dt.datetime) -> bool:
    """점유를 잡는다. **기본 키 충돌이 곧 "이미 갱신 중"이다.** 잡으면 곧바로 커밋한다 — 커밋하지
    않으면 다른 세션이 점유를 보지 못해 같은 단위를 함께 받는다."""
    session.add(StockListingLock(unit=unit, started_at=now, heartbeat_at=now))
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        return False
    return True


async def heartbeat(session: AsyncSession, unit: str, now: dt.datetime) -> None:
    await session.execute(update(StockListingLock).where(
        StockListingLock.unit == unit).values(heartbeat_at=now))


async def release_lock(session: AsyncSession, unit: str) -> None:
    await session.execute(delete(StockListingLock).where(StockListingLock.unit == unit))


async def release_all_locks(session: AsyncSession) -> None:
    """기동 시 남은 점유를 푼다. 프로세스가 하나라 그 점유는 죽은 프로세스의 것이다."""
    await session.execute(delete(StockListingLock))


async def reclaim_stale_locks(
    session: AsyncSession, now: dt.datetime, *, stale_after: dt.timedelta
) -> list[str]:
    """심장박동이 멈춘 점유를 회수한다. 회수하지 않으면 그 단위는 다시 갱신할 수 없다."""
    cutoff = now - stale_after
    stale = list((await session.execute(select(StockListingLock.unit).where(
        StockListingLock.heartbeat_at < cutoff).order_by(StockListingLock.unit))).scalars())
    if stale:
        await session.execute(delete(StockListingLock).where(StockListingLock.unit.in_(stale)))
    return stale


async def locked_units(session: AsyncSession) -> set[str]:
    return set((await session.execute(select(StockListingLock.unit))).scalars())
