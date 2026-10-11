"""기준금리의 변화 까닭 (014 반복 2026-10-11d T208) — FR-042, SC-026, research R14-33, contracts
A16.

**문장을 만들지 않는다** — 최근 결정을 다룬 출처의 시황 기사(제목·요약 원문·언론사·시각·주소)를
그대로 싣는다(지표 까닭 FR-027과 같은 뜻).

- 출처는 승인된 네이버 뉴스 포커스다(분류만 다르다 — 404 채권·선물 → 403 해외 증시 → 429 환율).
  날짜는 그 은행의 **최근 결정일(한국)과
  다음 날**이다 — 지표의 "마지막 세션 이후" 규칙을 쓰지 않는다(결정은 몇 주에 한 번이라 며칠 뒤면
  늘 "찾지 못함"이 된다)
- 고르기: 제목에 그 은행 낱말과 금리 낱말이 **둘 다**(`commentary.matches_bank`), 게시 시각이
  **발표 시각 30분 전 이후**(출처의 발표 시각은
  어림이다 — 한은 10:00인데 결정 기사가 09:52, T202 실측). 시각을 모르면 결정일 한국 0시 이후.
  분류·출처 차례로 위에서부터 최대 3개, 같은
  제목은 한 번. 게시 시각을 모르는 기사는 고르지 않는다
- **저장하지 않는다** — 은행마다 메모리에 `DASHBOARD_COMMENTARY_CACHE_SECONDS`(기본 600), 같은
  (분류, 날짜) 응답은 은행 사이에 한 번만 받는다.
  실패는 지표 까닭과 같은 물러서기다
- 결정이 아직 없으면 받지 않고 `none`이다. 출처를 부를 때마다 수집 로그에 한 줄(`commentary_fetch`)
"""

from __future__ import annotations

import asyncio
import datetime as dt
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Final, Protocol
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.config.settings import Settings
from src.ingestion.news.commentary import BANK_SIDS, CommentaryItem, matches_bank
from src.ingestion.news.errors import FailureReason, NewsError
from src.ingestion.news.types import normalize_title
from src.observability.logging_config import collection_logger
from src.repository import policy_rate_repository as repo
from src.simulation.policy_rate import Bank, Decision

Json = dict[str, object]
_KST: Final = ZoneInfo("Asia/Seoul")
_SECOND: Final = dt.timedelta(seconds=1)
_DAY: Final = dt.timedelta(days=1)
#: 출처의 발표 시각은 어림이다 — 그보다 이만큼 앞의 기사부터 본다(R14-33).
LEAD: Final = dt.timedelta(minutes=30)
LIMIT: Final = 3
SOURCE: Final = "네이버 증권"
SOURCE_URL: Final = "https://stock.naver.com/news"


class DayFetcher(Protocol):
    async def fetch_day(self, sid: str, day: dt.date) -> list[CommentaryItem]: ...


class LatestDecision(Protocol):
    async def latest(self, bank_id: str) -> Decision | None: ...


class DbLatestDecision:
    """저장된 최근 결정 — 요청마다 세션 하나."""

    def __init__(self, factory: async_sessionmaker[AsyncSession]) -> None:
        self._factory = factory

    async def latest(self, bank_id: str) -> Decision | None:
        async with self._factory() as session:
            return await repo.latest(session, bank_id)


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def since_of(decision: Decision) -> dt.datetime:
    """고르기의 시작 — 발표 시각 30분 전, 모르면 결정일(한국) 0시."""
    if decision.announced_at is not None:
        return decision.announced_at - LEAD
    return dt.datetime.combine(decision.decided_on, dt.time(0), tzinfo=_KST).astimezone(dt.UTC)


def select_items(
    items: Sequence[CommentaryItem], bank_id: str, *, since: dt.datetime, limit: int = LIMIT
) -> list[CommentaryItem]:
    """받은 차례로 그 은행·금리의 기사를 `limit`개. 같은 제목(공백을 접은)은 한 번."""
    out: list[CommentaryItem] = []
    seen: set[str] = set()
    for item in items:
        if item.published_at is None or item.published_at < since:
            continue
        if not matches_bank(item.title, bank_id):
            continue
        key = normalize_title(item.title)
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
        if len(out) >= limit:
            break
    return out


def _iso(moment: dt.datetime) -> str:
    return moment.astimezone(dt.UTC).replace(tzinfo=None, microsecond=0).isoformat() + "Z"


def _item_json(item: CommentaryItem) -> Json:
    return {
        "title": item.title,
        "summary": item.summary,
        "publisher": item.publisher,
        "publishedAt": None if item.published_at is None else _iso(item.published_at),
        "publishedText": item.published_text,
        "url": item.url,
    }


def _event(name: str, **fields: object) -> None:
    """수집 로그 한 줄. `message` 같은 `LogRecord` 예약 이름을 칸으로 쓰지 않는다."""
    collection_logger().info(name, extra={"event": name, **fields})


@dataclass(frozen=True, slots=True)
class _Success:
    body: Json
    until: dt.datetime
    #: 이 본문의 결정일 — 새 결정이 저장되면 캐시가 낡는다
    decided_on: dt.date | None


@dataclass(frozen=True, slots=True)
class _Failure:
    reason: FailureReason
    message: str
    until: dt.datetime
    count: int


@dataclass(frozen=True, slots=True)
class _Day:
    items: list[CommentaryItem]
    until: dt.datetime


class RateCommentaryService:
    def __init__(
        self,
        fetcher: DayFetcher,
        decisions: LatestDecision,
        settings: Settings,
        *,
        clock: Callable[[], dt.datetime] = utc_now,
    ) -> None:
        self._fetcher = fetcher
        self._decisions = decisions
        self._settings = settings
        self._clock = clock
        self._success: dict[str, _Success] = {}
        self._failure: dict[str, _Failure] = {}
        self._days: dict[tuple[str, dt.date], _Day] = {}
        # 잠금은 이벤트 루프에 묶인다 — 처음 쓸 때 만든다
        self._locks: dict[object, asyncio.Lock] = {}

    def _lock(self, key: object) -> asyncio.Lock:
        lock = self._locks.get(key)
        if lock is None:
            lock = self._locks[key] = asyncio.Lock()
        return lock

    def _hold(self, count: int) -> dt.timedelta:
        base = self._settings.news_failure_cache_seconds
        ceiling = self._settings.news_failure_cache_max_seconds
        return dt.timedelta(seconds=min(base << min(count - 1, 30), ceiling))

    def _keep(self) -> dt.timedelta:
        return dt.timedelta(seconds=self._settings.dashboard_commentary_cache_seconds)

    async def _day(self, sid: str, day: dt.date, now: dt.datetime) -> list[CommentaryItem]:
        """한 (분류, 날짜)의 기사 — 은행 사이에 함께 쓴다."""
        async with self._lock((sid, day)):
            hit = self._days.get((sid, day))
            if hit is not None and now < hit.until:
                return hit.items
            items = await self._fetcher.fetch_day(sid, day)
            self._days[(sid, day)] = _Day(items, now + self._keep())
            return items

    async def body(self, bank: Bank) -> Json:
        """contracts A16 본문. 출처가 실패해도 본문이다(`status: "failed"`)."""
        async with self._lock(bank.id):
            now = self._clock()
            decision = await self._decisions.latest(bank.id)
            decided_on = None if decision is None else decision.decided_on
            cached = self._success.get(bank.id)
            if cached is not None and now < cached.until and cached.decided_on == decided_on:
                return cached.body
            remembered = self._failure.get(bank.id)
            if remembered is not None and now < remembered.until:
                return self._failed(bank, remembered, now)
            if decision is None:
                # 결정이 아직 없다(받는 중) — 출처를 부르지 않는다
                return self._ok(bank, None, [], now, fetched=0)
            items: list[CommentaryItem] = []
            try:
                for sid in BANK_SIDS:
                    for day in (decision.decided_on, decision.decided_on + _DAY):
                        items += await self._day(sid, day, now)
            except NewsError as exc:
                count = 1 if remembered is None else remembered.count + 1
                failure = _Failure(exc.reason, str(exc), now + self._hold(count), count)
                self._failure[bank.id] = failure
                self._success.pop(bank.id, None)
                _event("commentary_fetch", bank=bank.id, status="failed", reason=exc.reason,
                       detail=str(exc))
                return self._failed(bank, failure, now)
            self._failure.pop(bank.id, None)
            chosen = select_items(items, bank.id, since=since_of(decision))
            return self._ok(bank, decision.decided_on, chosen, now, fetched=len(items))

    def _ok(
        self,
        bank: Bank,
        decided_on: dt.date | None,
        chosen: list[CommentaryItem],
        now: dt.datetime,
        *,
        fetched: int,
    ) -> Json:
        body: Json = {
            **self._head(bank),
            "status": "ok" if chosen else "none",
            "fetchedAt": _iso(now),
            "decisionDate": None if decided_on is None else decided_on.isoformat(),
            "items": [_item_json(item) for item in chosen],
            "failure": None,
        }
        self._success[bank.id] = _Success(body, now + self._keep(), decided_on)
        if decided_on is not None:
            _event("commentary_fetch", bank=bank.id, status="ok", items=fetched,
                   chosen=len(chosen))
        return body

    def _head(self, bank: Bank) -> Json:
        return {"bank": bank.id, "source": SOURCE, "sourceUrl": SOURCE_URL}

    def _failed(self, bank: Bank, failure: _Failure, now: dt.datetime) -> Json:
        remaining = failure.until - now
        seconds = -(-remaining // _SECOND) if remaining > dt.timedelta(0) else 0
        return {
            **self._head(bank),
            "status": "failed",
            "fetchedAt": None,
            "decisionDate": None,
            "items": [],
            "failure": {
                "reason": failure.reason,
                "message": failure.message,
                "retryAfterSeconds": seconds,
            },
        }


_shared: RateCommentaryService | None = None


def set_shared_service(service: RateCommentaryService | None) -> None:
    """앱 수명의 서비스 — `lifespan`이 둔다(ASGITransport 테스트는 직접 둔다)."""
    global _shared
    _shared = service


def get_shared_service() -> RateCommentaryService | None:
    return _shared
