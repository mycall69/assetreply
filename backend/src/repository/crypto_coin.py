"""코인 목록 리포지토리 (T017) — 007 FR-004, FR-005, FR-005a, FR-006, data-model 1·2·4절.

**코인·원본 테이블에 삭제 질의를 두지 않는다.** 목록에서 빠진 코인은 `missing`으로
표시하고(FR-005a), 원본 응답은 지우지 않는다(헌법 원칙 V). 지울 수 있는 것은 점유 행뿐이라 점유는
`crypto_list_lock.py`에 따로 둔다.

**코인은 (출처, 출처 식별자)로 식별한다**(FR-004) — 심볼은 유일하지 않다. 갱신은 수천 건이라 행마다
ORM 객체를 고치지 않고 **묶음 질의**로 한다. 표준 `INSERT`·`UPDATE`만 쓴다(헌법 DB 운영 규약) —
방언별 upsert는 기본 키 충돌만 다루는데 이 테이블의 식별은 보조 유니크 키다(006 `stock_listing`과
같은 이유).
"""

from __future__ import annotations

import datetime as dt
import hashlib
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

from sqlalchemy import insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import CryptoCoin, CryptoCoinRefresh, CryptoListRaw, CryptoListRawBody
from src.ingestion.investing.parse import CoinRow

#: 한 질의에 싣는 행·식별자 수. 너무 크면 패킷 한도에, 너무 작으면 왕복 수에 걸린다.
_CHUNK = 500
_LAST_ERROR_LENGTH = 512


def _chunks[T](items: Sequence[T], size: int = _CHUNK) -> Iterable[Sequence[T]]:
    for start in range(0, len(items), size):
        yield items[start:start + size]


# ── 갱신 기록 ─────────────────────────────────────────────────────────


async def get_refresh(session: AsyncSession, edition: str) -> CryptoCoinRefresh | None:
    return await session.get(CryptoCoinRefresh, edition)


async def all_refresh(session: AsyncSession) -> dict[str, CryptoCoinRefresh]:
    rows = (await session.execute(
        select(CryptoCoinRefresh).execution_options(populate_existing=True))).scalars()
    return {row.edition: row for row in rows}


async def _refresh_row(session: AsyncSession, edition: str) -> CryptoCoinRefresh:
    row = await session.get(CryptoCoinRefresh, edition)
    if row is None:
        row = CryptoCoinRefresh(edition=edition, attempts=0)
        session.add(row)
    return row


async def record_attempt(
    session: AsyncSession, edition: str, now: dt.datetime, today: dt.date
) -> None:
    """시도를 그날(한국 시간)로 센다. 갱신 판정이 "오늘 이미 시도했나"를 이것으로 본다(FR-005)."""
    row = await _refresh_row(session, edition)
    if row.attempt_date != today:
        row.attempt_date = today
        row.attempts = 0
    row.attempts = (row.attempts or 0) + 1
    row.last_attempt_at = now
    await session.flush()


async def record_failure(
    session: AsyncSession, edition: str, now: dt.datetime, kind: str, message: str
) -> None:
    """실패 종류와 사유를 남긴다. **기준 시각(`as_of`)은 바꾸지 않는다** — 이전 목록이 그대로다."""
    row = await _refresh_row(session, edition)
    row.last_failed_at = now
    row.last_error_kind = kind
    row.last_error = message[:_LAST_ERROR_LENGTH]
    await session.flush()


async def record_success(
    session: AsyncSession, edition: str, now: dt.datetime, today: dt.date, row_count: int
) -> None:
    row = await _refresh_row(session, edition)
    row.as_of = now
    row.as_of_date = today
    row.row_count = row_count
    row.last_error_kind = None
    row.last_error = None
    await session.flush()


# ── 코인 ──────────────────────────────────────────────────────────────


async def load_coins(session: AsyncSession) -> list[CryptoCoin]:
    return list((await session.execute(select(CryptoCoin))).scalars())


async def get_coin(session: AsyncSession, coin_id: int) -> CryptoCoin | None:
    return await session.get(CryptoCoin, coin_id)


async def first_available_dates(
    session: AsyncSession, coin_ids: Sequence[int]
) -> dict[int, dt.date | None]:
    """코인별 첫 일봉. 수집 중 발견하므로(research R7-10) 검색 색인에 담지 않고 결과마다 읽는다."""
    if not coin_ids:
        return {}
    rows = (await session.execute(select(CryptoCoin.id, CryptoCoin.first_available_date).where(
        CryptoCoin.id.in_(list(coin_ids))))).all()
    return {int(i): d for i, d in rows}


@dataclass(frozen=True, slots=True)
class ReplaceCounts:
    inserted: int
    updated: int
    missing: int


def _changed(row: CryptoCoin, coin: CoinRow, name_ko: str | None) -> bool:
    return (row.symbol, row.name_en, row.slug, row.market_rank, row.status, row.name_ko) != (
        coin.symbol, coin.name, coin.slug, coin.rank, "listed", name_ko)


async def replace_coins(
    session: AsyncSession,
    coins: Sequence[CoinRow],
    *,
    korean: Mapping[str, str] | None,
    now: dt.datetime,
    source: str,
    quote_currency: str,
) -> ReplaceCounts:
    """목록을 교체한다. **커밋하지 않는다** — 호출자가 갱신 기록과 한 트랜잭션으로 묶는다.

    `korean`이 `None`이면 한국어 판을 받지 못한 것이다 — 저장된 한글 이름을 그대로 둔다(FR-006).
    받았으면 그 판이 준 값으로 바꾼다(없으면 `None`).

    1. 받은 코인을 넣거나 고친다
    2. 이번에 없는 코인을 `missing`으로 표시한다 — 지우지 않는다(FR-005a)
    """
    existing = {row.source_id: row for row in (await session.execute(
        select(CryptoCoin).where(CryptoCoin.source == source))).scalars()}

    new_rows: list[dict[str, object]] = []
    seen_ids: list[int] = []
    for coin in coins:
        current = existing.get(coin.source_id)
        if current is None:
            new_rows.append({
                "source": source, "source_id": coin.source_id, "slug": coin.slug,
                "symbol": coin.symbol, "name_en": coin.name,
                "name_ko": korean.get(coin.source_id) if korean is not None else None,
                "quote_currency": quote_currency, "market_rank": coin.rank, "status": "listed",
                "first_seen_at": now, "last_seen_at": now,
            })
            continue
        seen_ids.append(int(current.id))
        name_ko = korean.get(coin.source_id) if korean is not None else current.name_ko
        if _changed(current, coin, name_ko):
            await session.execute(update(CryptoCoin).where(CryptoCoin.id == current.id).values(
                symbol=coin.symbol, name_en=coin.name, slug=coin.slug, market_rank=coin.rank,
                status="listed", name_ko=name_ko))

    for chunk in _chunks(seen_ids):
        await session.execute(update(CryptoCoin).where(
            CryptoCoin.id.in_(chunk)).values(last_seen_at=now))
    for batch in _chunks(new_rows):
        await session.execute(insert(CryptoCoin), list(batch))

    incoming = {c.source_id for c in coins}
    missing_ids = [int(row.id) for sid, row in existing.items()
                   if sid not in incoming and row.status == "listed"]
    for chunk in _chunks(missing_ids):
        await session.execute(update(CryptoCoin).where(
            CryptoCoin.id.in_(chunk)).values(status="missing"))
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
    edition: str,
    pages: Sequence[RawPage],
    *,
    batch_started_at: dt.datetime,
    fetched_at: dt.datetime,
) -> None:
    """쪽마다 기록을 남기고, 본문은 **같은 것이 없을 때만** 넣는다. 헤더는 받지 않는다 — 사용자
    에이전트가 남는다."""
    digests = [body_digest(p.body) for p in pages]
    known = set((await session.execute(select(CryptoListRawBody.sha256).where(
        CryptoListRawBody.sha256.in_(set(digests))))).scalars()) if digests else set()
    for page, digest in zip(pages, digests, strict=True):
        if digest not in known:
            session.add(CryptoListRawBody(
                sha256=digest, body=page.body, first_stored_at=fetched_at))
            known.add(digest)
    # 본문을 먼저 내보낸다 — 관계 없는 외래 키는 작업 단위가 순서를 정하지 않는다(006과 같다).
    await session.flush()
    for page, digest in zip(pages, digests, strict=True):
        session.add(CryptoListRaw(
            edition=edition, batch_started_at=batch_started_at, page_no=page.page_no,
            status_code=page.status_code, body_sha256=digest, fetched_at=fetched_at))
    await session.flush()
