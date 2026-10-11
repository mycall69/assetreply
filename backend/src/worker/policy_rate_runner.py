"""기준금리 결정 이력 수집 실행 (014 반복 2026-10-11d T207) — FR-043, SC-026, research R14-32,
data-model 17.

한 바퀴는 **목록 한 번 → 은행마다 결정 이력**이다(R14-32 — 모두 약 11회):

- 처음(그 은행의 `history_complete`가 아니다)은 결정 이력 전부 — 짧은 쪽(60행 미만)이 올 때까지
  받고 그때 끝났다고 기록한다. 중간에
  실패하면 끝났다고 기록하지 않는다 — 다음 바퀴가 처음 쪽부터 다시 받는다(받은 날은 이미 있어 넣지
  않는다)
- 그 뒤는 목록의 최근 결정일이 저장된 것보다 늦거나(새 결정), 그 한국 날짜에 아직 겹쳐 받지 않았을
  때만 첫 쪽이다(하루 한 번 — 개정 확인). 할 일이 없는 은행도 목록이 성공했으면 성공을 남긴다 — 앞
  바퀴의
  실패가 풀린다
- 쪽마다 원본 → 결정(새 날만) → 상태 순으로 저장하고 커밋한다. 개정은 덮지 않고
  `policy_rate_revised`, 같은 날 다른 값은
  `policy_rate_conflict`를 수집 로그에 남긴다
- 목록이 실패하면 은행 다섯 모두 그 실패다(결정 이력을 부르지 않는다). 목록에 없는 은행은
  `not_found`. **한 은행의 실패가 바퀴를 끝내지 않는다**
- 다음 결정 예정일은 목록의 것이다 — 오늘(한국)보다 이르면 비운다(출처가 지난 날짜를 준다)
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Final, Protocol
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.config.settings import Settings
from src.db.models import PolicyRateRawKind
from src.ingestion.naver_rate.client import PAGE_SIZE, CalendarFetch, ListFetch
from src.ingestion.naver_rate.errors import PolicyRateError
from src.observability.events import mask_secrets
from src.observability.logging_config import collection_logger
from src.repository import policy_rate_repository as repo
from src.simulation.policy_rate import BANKS, rate_text, visible_next_meeting

_KST: Final = ZoneInfo("Asia/Seoul")
_NOT_LISTED: Final = "기준금리 목록에 이 은행이 없습니다."


class PolicyRateSource(Protocol):
    """기준금리 출처. 어댑터를 교체할 수 있도록 Protocol에 의존한다(헌법 원칙 II·IV)."""

    async def fetch_list(self) -> ListFetch: ...

    async def fetch_calendars(self, bank_id: str, page: int) -> CalendarFetch: ...


@dataclass(frozen=True, slots=True)
class RoundResult:
    #: 출처에 보낸 요청 수(실패 포함)
    requests: int
    failed: frozenset[str]


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def _event(name: str, **fields: object) -> None:
    collection_logger().info(name, extra={"event": name, **fields})


def _naive(instant: dt.datetime) -> dt.datetime:
    return instant.astimezone(dt.UTC).replace(tzinfo=None)


def _kind(exc: BaseException) -> str:
    return exc.kind if isinstance(exc, PolicyRateError) else "connection"


def _message(exc: BaseException) -> str:
    return mask_secrets(str(exc)) or "기준금리 수집에 실패했습니다."


class _Counter:
    def __init__(self) -> None:
        self.value = 0


async def _record_failure(
    factory: async_sessionmaker[AsyncSession], bank: str, at: dt.datetime, kind: str, message: str
) -> None:
    async with factory() as session:
        await repo.record_failure(session, bank, at=at, kind=kind, message=message)
        await session.commit()


def _logged(bank: str, page: int, rows: int, inserted: int, fetched: CalendarFetch,
            revisions: list[repo.Revision]) -> None:
    _event("policy_rate_fetch", kind="calendars", bank=bank, page=page, status="ok",
           rows=rows, inserted=inserted)
    for revision in revisions:
        _event("policy_rate_revised", bank=bank, date=revision.decided_on.isoformat(),
               stored=rate_text(revision.stored_rate), source=rate_text(revision.source_rate))
    for conflict in fetched.page.conflicts:
        _event("policy_rate_conflict", bank=bank, date=conflict.decided_on.isoformat(),
               rates=[rate_text(rate) for rate in conflict.rates])


async def _collect(
    factory: async_sessionmaker[AsyncSession],
    source: PolicyRateSource,
    bank: str,
    *,
    full: bool,
    at: dt.datetime,
    today: dt.date,
    sent: _Counter,
) -> None:
    """그 은행의 결정 이력 — 처음이면 짧은 쪽까지 전부, 아니면 첫 쪽만. 실패는 그대로 올린다."""
    page = 1
    while True:
        sent.value += 1
        try:
            fetched = await source.fetch_calendars(bank, page)
        except Exception as exc:
            _event("policy_rate_fetch", kind="calendars", bank=bank, page=page,
                   status="failed", reason=_kind(exc))
            raise
        async with factory() as session:
            # 원본을 먼저 남긴다 — 정규화와 따로, 본문 그대로(헌법 원칙 V)
            await repo.store_raw(session, PolicyRateRawKind.CALENDARS, bank=bank, page=page,
                                 body=fetched.raw, fetched_at=at)
            stored = await repo.store_decisions(
                session, bank, fetched.page.decisions, ingested_at=at)
            last = not full or fetched.page.row_count < PAGE_SIZE
            if full and last:
                await repo.mark_history_complete(session, bank)
            # 쪽마다 커밋한다 — 중단되면 받은 데까지는 남는다
            await session.commit()
        _logged(bank, page, fetched.page.row_count, stored.inserted, fetched, stored.revisions)
        if last:
            break
        page += 1
    async with factory() as session:
        await repo.set_overlap_day(session, bank, today)
        await repo.record_success(session, bank, at=at)
        await session.commit()


async def run_round(
    factory: async_sessionmaker[AsyncSession],
    source: PolicyRateSource,
    *,
    settings: Settings,
    now: dt.datetime,
) -> RoundResult:
    """한 바퀴 — 목록을 보고 은행마다 받을 쪽을 받는다."""
    at = _naive(now)
    today = now.astimezone(_KST).date()
    sent = _Counter()
    sent.value += 1
    try:
        listed = await source.fetch_list()
    except Exception as exc:  # 목록이 실패하면 은행 다섯 모두 그 실패다 — 결정 이력을 부르지 않는다
        kind, message = _kind(exc), _message(exc)
        async with factory() as session:
            for bank in BANKS:
                await repo.record_failure(session, bank.id, at=at, kind=kind, message=message)
            await session.commit()
        _event("policy_rate_fetch", kind="list", status="failed", reason=kind)
        return RoundResult(sent.value, frozenset(bank.id for bank in BANKS))
    async with factory() as session:
        await repo.store_raw(session, PolicyRateRawKind.LIST, bank=None, page=None,
                             body=listed.raw, fetched_at=at)
        await session.commit()
    _event("policy_rate_fetch", kind="list", status="ok", rows=len(listed.entries))

    failed: set[str] = set()
    for bank in BANKS:
        entry = listed.entries.get(bank.id)
        if entry is None:
            await _record_failure(factory, bank.id, at, "not_found", _NOT_LISTED)
            failed.add(bank.id)
            continue
        async with factory() as session:
            await repo.set_next_meeting(
                session, bank.id, visible_next_meeting(entry.next_meeting_on, today))
            state = await repo.get_state(session, bank.id)
            newest = await repo.latest(session, bank.id)
            complete = state is not None and state.history_complete
            overlap = None if state is None else state.last_overlap_on
            await session.commit()
        if complete:
            fresh = entry.decided_on is not None and (
                newest is None or entry.decided_on > newest.decided_on)
            if not fresh and overlap == today:
                # 할 일이 없다 — 목록이 저장된 결정이 최신임을 확인했다. 성공을 남겨야 앞 바퀴의
                # 실패가 풀린다
                async with factory() as session:
                    await repo.record_success(session, bank.id, at=at)
                    await session.commit()
                continue
        try:
            await _collect(factory, source, bank.id, full=not complete, at=at, today=today,
                           sent=sent)
        except Exception as exc:  # 한 은행의 실패가 바퀴를 끝내지 않는다 — 까닭을 남기고 다음으로
            await _record_failure(factory, bank.id, at, _kind(exc), _message(exc))
            failed.add(bank.id)
    return RoundResult(sent.value, frozenset(failed))
