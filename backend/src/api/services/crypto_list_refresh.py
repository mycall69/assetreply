"""코인 목록 갱신 — 판정·교체·실패 기록 (T018) — 007 FR-004~FR-006, FR-005b, FR-019, research
R7-4·R7-11.

**검색은 갱신을 요청만 한다.** 판정(`list_due`)과 상태(`edition_state`)는 순수 함수이고, 실제
갱신(`refresh_coins`)은 목록 갱신 줄이 부른다(006 `listing_refresh`와 같은 구조).

**두 판을 다 받은 뒤** 한 트랜잭션에서 교체한다. 영문 판(`en`)이 목록이고 한국어 판(`ko`)은 한글
이름만 준다 — 그래서 한국어 판만 실패하면 영문으로 교체하고 저장된 한글 이름을 그대로 둔다. 영문
판의 중간 쪽 실패, 빈 목록, **이전 코인 수 × 설정 비율보다 적은 목록**은 아무것도 바꾸지 않는다 —
출처가 오류 없이 일부만 주면 실패 판정을 통과하므로 축소 검사가 두 번째 방어선이다.

**하루의 경계는 한국 시간이다**(006과 같다). 저장 시각은 UTC(시간대 없는 값)다.
"""

from __future__ import annotations

import datetime as dt
import logging
import math
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from decimal import Decimal
from typing import Final, Literal, Protocol

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.api.services.listing_refresh import kst_date, utc_now
from src.config.settings import Settings
from src.db.models import CryptoCoinRefresh
from src.ingestion.investing.client import PAGE_LIMIT, CoinPageFetch
from src.ingestion.investing.errors import InvestingError
from src.ingestion.investing.parse import CoinRow, korean_names
from src.observability.events import mask_secrets
from src.observability.logging_config import collection_logger
from src.repository import crypto_coin as repo
from src.repository import crypto_list_lock as locks
from src.worker.crypto_list_queue import CryptoListQueue

#: 출처 이름. 코인 식별의 앞부분이다 — (출처, 출처 식별자).
SOURCE: Final = "investing"
#: 출처의 코인 목록은 모두 달러 시세다(research R7-3).
QUOTE_CURRENCY: Final = "USD"
EN: Final = "en"
KO: Final = "ko"

_log = logging.getLogger(__name__)


# ── 판정 (순수 함수) ──────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class CoinRefreshRecord:
    """갱신 기록의 판정용 사본. ORM 객체를 순수 함수에 넘기지 않는다."""

    as_of: dt.datetime | None = None
    as_of_date: dt.date | None = None
    row_count: int | None = None
    attempt_date: dt.date | None = None
    attempts: int = 0
    last_failed_at: dt.datetime | None = None
    last_error_kind: str | None = None

    @classmethod
    def from_row(cls, row: CryptoCoinRefresh | None) -> CoinRefreshRecord | None:
        if row is None:
            return None
        return cls(as_of=row.as_of, as_of_date=row.as_of_date, row_count=row.row_count,
                   attempt_date=row.attempt_date, attempts=row.attempts or 0,
                   last_failed_at=row.last_failed_at, last_error_kind=row.last_error_kind)


def list_due(record: CoinRefreshRecord | None, *, today: dt.date, refresh_days: int) -> bool:
    """목록을 다시 받을까 (FR-005, data-model 2절). 영문 판의 기록으로 본다 — 한국어 판은 함께
    받는다.

    **그날 이미 시도했으면 받지 않는다** — 실패도 시도다. 같은 날 검색마다 다시 받으면 막힌 출처를
    하루 내내 두드린다.
    """
    if record is None:
        return True
    if record.attempt_date == today:
        return False
    if record.as_of_date is None:
        return True
    return (today - record.as_of_date).days >= refresh_days


EditionStateName = Literal["never", "refreshing", "failed", "ready"]


@dataclass(frozen=True, slots=True)
class EditionState:
    state: EditionStateName
    as_of: dt.datetime | None
    reason: str | None


def edition_state(record: CoinRefreshRecord | None, *, refreshing: bool) -> EditionState:
    """판의 화면 상태 (contracts `list.state`). 저장하지 않고 매번 계산한다.

    이전 목록이 없으면 갱신 중이어도 `never`다 — "처음 받는 중"과 "새로 받는 중(이전 목록으로
    찾는다)"은 사용자에게 다른 말이다(ui-wireframes C2).
    """
    as_of = record.as_of if record is not None else None
    failed = (record is not None and record.last_failed_at is not None
              and (as_of is None or record.last_failed_at > as_of))
    reason = (record.last_error_kind or "format") if failed and record is not None else None
    if as_of is None:
        if failed and not refreshing:
            return EditionState("failed", None, reason)
        return EditionState("never", None, None)
    if refreshing:
        return EditionState("refreshing", as_of, None)
    if failed:
        return EditionState("failed", as_of, reason)
    return EditionState("ready", as_of, None)


@dataclass(frozen=True, slots=True)
class CoinListStatus:
    list: EditionState
    korean: EditionState


def expected_pages(row_count: int | None) -> int | None:
    """이전 코인 수로 어림한 전체 쪽 수(FR-005b). 처음이면 없다."""
    return math.ceil(row_count / PAGE_LIMIT) if row_count else None


# ── 갱신 요청 (검색이 부른다) ─────────────────────────────────────────


async def request_refresh(
    session: AsyncSession,
    *,
    now: dt.datetime,
    settings: Settings,
    queue: CryptoListQueue,
) -> CoinListStatus:
    """주기가 되었으면 갱신을 **요청만** 하고 지금 상태를 돌려준다. 기다리지 않는다.

    정체 점유를 여기서 회수한다 — 프로세스가 갱신 도중 죽으면 점유가 남고, 회수하지 않으면 다시
    갱신할 수 없으며 화면은 영원히 "갱신 중"이다.
    """
    await locks.reclaim_stale_lock(
        session, now, stale_after=dt.timedelta(minutes=settings.crypto_list_lock_stale_minutes))
    await session.commit()
    records = await repo.all_refresh(session)
    english = CoinRefreshRecord.from_row(records.get(EN))
    refreshing = await locks.get_lock(session) is not None or queue.is_active(locks.SCOPE)
    if not refreshing and list_due(english, today=kst_date(now),
                                   refresh_days=settings.crypto_list_refresh_days):
        queue.request(locks.SCOPE)
        refreshing = True
    return CoinListStatus(
        list=edition_state(english, refreshing=refreshing),
        korean=edition_state(CoinRefreshRecord.from_row(records.get(KO)), refreshing=refreshing))


# ── 갱신 실행 (목록 갱신 줄이 부른다) ─────────────────────────────────


class CoinListSource(Protocol):
    """코인 목록 출처. 어댑터를 교체할 수 있도록 Protocol에 의존한다(헌법 원칙 II·IV)."""

    def fetch_coin_pages(self, edition: str) -> AsyncIterator[CoinPageFetch]: ...


@dataclass(frozen=True, slots=True)
class CoinRefreshResult:
    outcome: Literal["replaced", "failed", "busy"]
    kind: str | None
    coins: int
    #: 한글 이름을 이번에 받았나. 영문 판이 실패하면 의미가 없어 `None`이다.
    korean: Literal["ready", "failed"] | None


class _Rejected(Exception):
    """교체하지 않을 목록. 출처 오류가 아니라 검사의 판정이다."""

    def __init__(self, kind: str, message: str) -> None:
        super().__init__(message)
        self.kind = kind


def _scrub(message: str, settings: Settings) -> str:
    """사유에서 사용자 에이전트를 지운다. 출처나 라이브러리가 요청 값을 문구에 되돌려 보낼 수
    있다(FR-019, SC-011)."""
    if settings.investing_user_agent:
        message = message.replace(settings.investing_user_agent, "***")
    return mask_secrets(message) or ""


def _event(event: str, **fields: object) -> None:
    """수집 전용 로그에 남긴다. 판·쪽 수·코인 수·실패 종류만 싣는다 — 헤더·사유 문구는 싣지
    않는다."""
    collection_logger().info(event, extra={"event": event, **fields})


def _shrunk(new_count: int, previous: int | None, threshold: Decimal) -> bool:
    """**새 코인 수 < 이전 코인 수 × 비율**이면 줄었다고 본다. 정확히 비율이면 받아들인다(006
    FR-018a와 같다)."""
    return previous is not None and previous > 0 and Decimal(new_count) < previous * threshold


async def _fetch_edition(
    session_factory: async_sessionmaker[AsyncSession],
    source: CoinListSource,
    edition: str,
    *,
    started: dt.datetime,
    now: Callable[[], dt.datetime],
) -> list[CoinRow]:
    """한 판을 끝까지 받는다. **쪽마다** 원본을 남기고 점유 행에 진행을 적는다(FR-005b).

    원본은 검사 전에 남긴다 — 실패한 갱신의 원본이 무엇이 잘못 왔는지 되짚는 근거다. 같은 코인이 두
    쪽에 오면(쪽을 넘기는 사이 순위가 바뀌면) 처음 것만 둔다 — 식별자 유일 키에 걸려 교체 전체가
    실패하면 안 된다.
    """
    coins: dict[str, CoinRow] = {}
    pages = 0
    async with session_factory() as session:
        await locks.set_progress(session, edition=edition, pages_done=0, coins_seen=0, now=now())
        await session.commit()
    async for fetched in source.fetch_coin_pages(edition):
        pages += 1
        for coin in fetched.page.coins:
            coins.setdefault(coin.source_id, coin)
        at = now()
        async with session_factory() as session:
            await repo.store_raw_pages(
                session, edition, [repo.RawPage(fetched.page_no, fetched.status, fetched.raw)],
                batch_started_at=started, fetched_at=at)
            await locks.set_progress(
                session, edition=edition, pages_done=pages, coins_seen=len(coins), now=at)
            await session.commit()
    return list(coins.values())


async def _record_failure(
    session_factory: async_sessionmaker[AsyncSession],
    edition: str,
    at: dt.datetime,
    kind: str,
    message: str,
) -> None:
    async with session_factory() as session:
        await repo.record_failure(session, edition, at, kind, message)
        await session.commit()


async def refresh_coins(
    session_factory: async_sessionmaker[AsyncSession],
    source: CoinListSource,
    *,
    settings: Settings,
    now: Callable[[], dt.datetime] = utc_now,
) -> CoinRefreshResult:
    """두 판을 받아 목록을 교체한다. 이미 갱신 중이면 아무것도 하지 않는다."""
    started = now()
    async with session_factory() as session:
        if not await locks.try_lock(session, started):
            return CoinRefreshResult("busy", None, 0, None)

    try:
        async with session_factory() as session:
            for edition in (EN, KO):
                await repo.record_attempt(session, edition, started, kst_date(started))
            records = await repo.all_refresh(session)
            previous = records[EN].row_count
            await session.commit()
        _event("crypto_list_refresh_started")

        try:
            english = await _fetch_edition(
                session_factory, source, EN, started=started, now=now)
            if not english:
                raise _Rejected("format", "코인 목록이 비어 있습니다.")
            threshold = settings.crypto_list_shrink_threshold
            if _shrunk(len(english), previous, threshold):
                raise _Rejected(
                    "shrunk", f"새 목록 {len(english)}개가 이전 {previous}개의 {threshold}배보다 "
                    "적어 교체하지 않았습니다.")
        except (InvestingError, _Rejected) as exc:
            kind = exc.kind
            await _record_failure(session_factory, EN, now(), kind, _scrub(str(exc), settings))
            _event("crypto_list_refresh_failed", edition=EN, kind=kind)
            return CoinRefreshResult("failed", kind, 0, None)
        except Exception as exc:  # 예상하지 못한 실패도 기록하고 점유를 푼다
            _log.exception("코인 목록 갱신 중 예상하지 못한 오류")
            await _record_failure(session_factory, EN, now(), "format",
                                  f"예상하지 못한 오류: {type(exc).__name__}")
            _event("crypto_list_refresh_failed", edition=EN, kind="format")
            return CoinRefreshResult("failed", "format", 0, None)

        names: dict[str, str] | None = None
        korean_count = 0
        try:
            korean_rows = await _fetch_edition(
                session_factory, source, KO, started=started, now=now)
            names = korean_names(english, korean_rows)
            korean_count = len(korean_rows)
        except InvestingError as exc:
            # 한글 이름만 잃는다 — 영문으로 찾을 수 있다(FR-006). 저장된 한글 이름을 그대로 둔다.
            await _record_failure(session_factory, KO, now(), exc.kind, _scrub(str(exc), settings))
            _event("crypto_list_refresh_failed", edition=KO, kind=exc.kind)

        fetched = now()
        async with session_factory() as session:
            counts = await repo.replace_coins(
                session, english, korean=names, now=fetched, source=SOURCE,
                quote_currency=QUOTE_CURRENCY)
            await repo.record_success(session, EN, fetched, kst_date(fetched), len(english))
            if names is not None:
                await repo.record_success(session, KO, fetched, kst_date(fetched), korean_count)
            await session.commit()
        korean: Literal["ready", "failed"] = "ready" if names is not None else "failed"
        _event("crypto_list_refresh_completed", coins=len(english), korean=korean,
               inserted=counts.inserted, missing=counts.missing,
               korean_names=len(names) if names is not None else None)
        return CoinRefreshResult("replaced", None, len(english), korean)
    finally:
        async with session_factory() as session:
            await locks.release_lock(session)
            await session.commit()
