"""목록 갱신 — 판정·교체·실패 기록 (T035) — 006 FR-013~018a, FR-062, research R6-3, R6-4.

**검색은 갱신을 요청만 한다.** 판정(`should_refresh`)과 상태(`list_state`)는 순수 함수이고, 실제
갱신(`refresh_unit`)은 워커가 부른다.

**한 단위의 모든 쪽을 받은 뒤** 검사를 통과하면 한 트랜잭션에서 교체한다(R6-4). 중간 쪽 실패, 빈
목록, 필수 필드 위반, **이전 건수 × 설정 비율보다 적은 목록**은 아무것도 바꾸지 않는다 — 출처가 오류
없이 일부만 주면 실패 판정을 통과하므로 축소 검사가 두 번째 방어선이다.

**하루의 경계는 한국 시간이다.** 저장 시각은 UTC(시간대 없는 값)이고, "오늘 받았나"만 한국 날짜로
본다.

**인증 실패 막힘은 프로세스 메모리에 둔다.** 인증 정보는 기동 시 `.env`에서 읽으므로 고치면 다시
띄우게 되고 그때 풀린다(FR-013b). DB에 두면 고친 뒤에도 그날 내내 막혀 고친 것이 효과가 없다고
읽힌다.
"""

from __future__ import annotations

import datetime as dt
import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Final, Literal, Protocol

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.config.settings import Settings
from src.db.models import StockListingRefresh
from src.ingestion.kiwoom.client import KiwoomPage
from src.ingestion.kiwoom.errors import KiwoomError
from src.ingestion.kiwoom.parse import parse_listing, source_of
from src.observability.events import mask_secrets
from src.observability.logging_config import collection_logger
from src.repository import stock_listing as repo
from src.worker.listing_queue import ListingQueue

#: 검색이 다루는 목록 단위 (FR-015). 국내를 앞에 둔다 — 그날 첫 검색에서 먼저 요청된다.
LISTING_UNITS: Final = ("KOSPI", "KOSDAQ", "NYSE", "NASDAQ", "AMEX")

_KST_OFFSET: Final = dt.timedelta(hours=9)

_log = logging.getLogger(__name__)


def utc_now() -> dt.datetime:
    """저장용 현재 시각 — UTC, 시간대 없는 값(헌법 시계열 불변식)."""
    return dt.datetime.now(dt.UTC).replace(tzinfo=None)


def kst_date(now: dt.datetime) -> dt.date:
    """UTC 시각(시간대 없는 값)의 한국 날짜."""
    return (now + _KST_OFFSET).date()


# ── 판정 (순수 함수) ──────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class RefreshRecord:
    """갱신 기록의 판정용 사본. ORM 객체를 순수 함수에 넘기지 않는다."""

    as_of: dt.datetime | None
    as_of_date: dt.date | None
    row_count: int | None
    attempt_date: dt.date | None
    attempts: int
    last_failed_at: dt.datetime | None
    last_error_kind: str | None

    @classmethod
    def from_row(cls, row: StockListingRefresh | None) -> RefreshRecord | None:
        if row is None:
            return None
        return cls(as_of=row.as_of, as_of_date=row.as_of_date, row_count=row.row_count,
                   attempt_date=row.attempt_date, attempts=row.attempts or 0,
                   last_failed_at=row.last_failed_at, last_error_kind=row.last_error_kind)


def should_refresh(
    record: RefreshRecord | None,
    *,
    now: dt.datetime,
    refreshing: bool,
    auth_blocked: bool,
    credentials_present: bool,
    retry_interval: dt.timedelta,
    max_attempts: int,
) -> bool:
    """이 단위의 갱신을 요청할까 (research R6-3의 순서)."""
    if not credentials_present or refreshing or auth_blocked:
        return False
    if record is None:
        return True
    today = kst_date(now)
    if record.as_of_date == today:
        return False
    if record.last_failed_at is not None and now - record.last_failed_at < retry_interval:
        return False
    return not (record.attempt_date == today and record.attempts >= max_attempts)


ListStateName = Literal["never", "refreshing", "ready", "stale", "failed", "auth_blocked"]

#: 실패 종류 → 화면에 보낼 사유 (contracts `lists[].reason`).
_REASON_BY_KIND: Final[dict[str, str]] = {
    "auth": "auth_failed", "rate_limit": "rate_limit", "network": "network", "invalid": "invalid"}
#: 사유 → 사용자가 할 일 (FR-028a).
_ACTION_BY_REASON: Final[dict[str, str]] = {
    "auth_missing": "set_credentials", "auth_failed": "set_credentials",
    "rate_limit": "retry_later", "network": "retry_later", "invalid": "retry_later"}


@dataclass(frozen=True, slots=True)
class ListState:
    unit: str
    state: ListStateName
    as_of: dt.datetime | None
    reason: str | None
    action: str | None


def list_state(
    unit: str,
    record: RefreshRecord | None,
    *,
    today: dt.date,
    refreshing: bool,
    auth_blocked: bool,
    credentials_present: bool,
) -> ListState:
    """단위의 화면 상태 (data-model 2절 표). 저장하지 않고 매번 계산한다."""
    as_of = record.as_of if record is not None else None
    if refreshing:
        return ListState(unit, "refreshing", as_of, None, "wait")
    if auth_blocked:
        return ListState(unit, "auth_blocked", as_of, "auth_failed", "set_credentials")

    fresh: ListStateName = "ready" if record is not None and record.as_of_date == today else "stale"
    if not credentials_present:
        return ListState(unit, "never" if as_of is None else fresh, as_of,
                         "auth_missing", "set_credentials")

    reason: str | None = None
    if (record is not None and record.last_failed_at is not None
            and (as_of is None or record.last_failed_at > as_of)):
        reason = _REASON_BY_KIND.get(record.last_error_kind or "", "invalid")
    action = _ACTION_BY_REASON[reason] if reason is not None else None
    if as_of is None:
        return ListState(unit, "never", None, reason, action or "wait")
    if reason is not None:
        return ListState(unit, "failed", as_of, reason, action)
    return ListState(unit, fresh, as_of, None, None)


# ── 인증 실패 막힘 (프로세스 메모리) ──────────────────────────────────


class AuthBlocker:
    """인증 실패로 막힌 단위. 프로세스 재시작까지 산다(FR-013b)."""

    __slots__ = ("_units",)

    def __init__(self) -> None:
        self._units: set[str] = set()

    def block(self, unit: str) -> None:
        self._units.add(unit)

    def is_blocked(self, unit: str) -> bool:
        return unit in self._units

    def reset(self) -> None:
        self._units.clear()


_blocker = AuthBlocker()


def get_auth_blocker() -> AuthBlocker:
    return _blocker


# ── 갱신 요청 (검색이 부른다) ─────────────────────────────────────────


async def request_refreshes(
    session: AsyncSession,
    *,
    now: dt.datetime,
    settings: Settings,
    queue: ListingQueue,
    blocker: AuthBlocker,
    units: Sequence[str] = LISTING_UNITS,
) -> list[ListState]:
    """단위마다 갱신을 **요청만** 하고 지금 상태를 돌려준다. 기다리지 않는다(FR-017).

    정체 점유를 여기서 회수한다 — 프로세스가 갱신 도중 죽으면 점유가 남고, 회수하지 않으면 그 단위는
    다시 갱신할 수 없으며 화면은 영원히 "갱신 중"이다.
    """
    await repo.reclaim_stale_locks(
        session, now, stale_after=dt.timedelta(minutes=settings.listing_lock_stale_minutes))
    await session.commit()
    records = await repo.all_refresh(session)
    locked = await repo.locked_units(session)
    today = kst_date(now)

    states: list[ListState] = []
    for unit in units:
        record = RefreshRecord.from_row(records.get(unit))
        refreshing = unit in locked
        blocked = blocker.is_blocked(unit)
        if should_refresh(
                record, now=now, refreshing=refreshing, auth_blocked=blocked,
                credentials_present=settings.kiwoom_credentials_present,
                retry_interval=dt.timedelta(minutes=settings.listing_retry_interval_minutes),
                max_attempts=settings.listing_max_attempts_per_day):
            queue.request(unit)
        states.append(list_state(
            unit, record, today=today, refreshing=refreshing, auth_blocked=blocked,
            credentials_present=settings.kiwoom_credentials_present))
    return states


# ── 갱신 실행 (워커가 부른다) ─────────────────────────────────────────


class ListingSource(Protocol):
    """목록 출처. 어댑터를 교체할 수 있도록 Protocol에 의존한다 (헌법 원칙 II·IV)."""

    async def fetch_unit(self, unit: str) -> list[KiwoomPage]: ...


@dataclass(frozen=True, slots=True)
class RefreshResult:
    unit: str
    outcome: Literal["replaced", "failed", "busy"]
    kind: str | None
    rows: int


def _scrub(message: str, settings: Settings) -> str:
    """사유에서 키·시크릿을 지운다. 출처가 요청에 실은 값을 문구에 되돌려 보낼 수 있다(FR-060)."""
    for secret in (settings.kiwoom_app_key.reveal(), settings.kiwoom_app_secret.reveal()):
        if secret:
            message = message.replace(secret, "***")
    return mask_secrets(message) or ""


def _event(event: str, unit: str, **fields: object) -> None:
    """수집 전용 로그에 남긴다(research R6-14). 단위·쪽 수·종목 수·실패 종류만 싣는다."""
    collection_logger().info(event, extra={"event": event, "unit": unit, **fields})


async def _fail(
    session_factory: async_sessionmaker[AsyncSession],
    unit: str,
    at: dt.datetime,
    kind: str,
    message: str,
    *,
    settings: Settings,
    blocker: AuthBlocker,
) -> RefreshResult:
    async with session_factory() as session:
        await repo.record_failure(session, unit, at, kind, _scrub(message, settings))
        await session.commit()
    if kind == "auth":
        blocker.block(unit)
    _event("listing_refresh_failed", unit, kind=kind)
    return RefreshResult(unit, "failed", kind, 0)


def _shrunk(new_count: int, previous: int | None, threshold: Decimal) -> bool:
    """**새 건수 < 이전 건수 × 비율**이면 줄었다고 본다. 정확히 비율이면 받아들인다(FR-018a)."""
    return previous is not None and previous > 0 and Decimal(new_count) < previous * threshold


async def refresh_unit(
    session_factory: async_sessionmaker[AsyncSession],
    source: ListingSource,
    unit: str,
    *,
    settings: Settings,
    now: Callable[[], dt.datetime] = utc_now,
    blocker: AuthBlocker | None = None,
) -> RefreshResult:
    """한 단위를 받아 교체한다. 이미 갱신 중이면 아무것도 하지 않는다(FR-014)."""
    blocker = blocker if blocker is not None else get_auth_blocker()
    started = now()
    async with session_factory() as session:
        if not await repo.try_lock(session, unit, started):
            return RefreshResult(unit, "busy", None, 0)

    try:
        async with session_factory() as session:
            await repo.record_attempt(session, unit, started, kst_date(started))
            await session.commit()
        _event("listing_refresh_started", unit)

        try:
            pages = await source.fetch_unit(unit)
        except KiwoomError as exc:
            return await _fail(session_factory, unit, now(), exc.kind, str(exc),
                               settings=settings, blocker=blocker)
        except Exception as exc:  # 예상하지 못한 실패도 기록하고 점유를 푼다
            _log.exception("목록 갱신 중 예상하지 못한 오류 unit=%s", unit)
            return await _fail(session_factory, unit, now(), "invalid",
                               f"목록 갱신 중 예상하지 못한 오류: {type(exc).__name__}",
                               settings=settings, blocker=blocker)

        fetched = now()
        # 원본은 검사 전에 남긴다 — 실패한 갱신의 원본이 무엇이 잘못 왔는지 되짚는 근거다.
        async with session_factory() as session:
            await repo.heartbeat(session, unit, fetched)
            await repo.store_raw_pages(
                session, unit,
                [repo.RawPage(p.page_no, p.status, p.body) for p in pages],
                batch_started_at=started, fetched_at=fetched)
            await session.commit()

        try:
            rows = parse_listing(unit, [p.body for p in pages])
        except KiwoomError as exc:
            return await _fail(session_factory, unit, fetched, exc.kind, str(exc),
                               settings=settings, blocker=blocker)

        async with session_factory() as session:
            previous = await repo.get_refresh(session, unit)
            previous_count = previous.row_count if previous is not None else None
        if not rows:
            return await _fail(session_factory, unit, fetched, "invalid",
                               f"{unit} 목록이 비어 있습니다.", settings=settings, blocker=blocker)
        threshold = settings.listing_shrink_threshold
        if _shrunk(len(rows), previous_count, threshold):
            return await _fail(
                session_factory, unit, fetched, "invalid",
                f"{unit} 새 목록 {len(rows)}건이 이전 {previous_count}건의 {threshold}배보다 "
                "적어 교체하지 않았습니다.", settings=settings, blocker=blocker)

        async with session_factory() as session:
            counts = await repo.replace_unit(
                session, unit, rows, now=fetched, today=kst_date(fetched),
                source=source_of(unit))
            await session.commit()
        _event("listing_refresh_completed", unit, pages=len(pages), rows=len(rows),
               inserted=counts.inserted, missing=counts.missing)
        return RefreshResult(unit, "replaced", None, len(rows))
    finally:
        async with session_factory() as session:
            await repo.release_lock(session, unit)
            await session.commit()
