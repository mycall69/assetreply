"""지표 모달의 변화 까닭 (014 반복 2026-10-10b T118) — FR-027, FR-022, SC-013, research R14-17,
contracts A8.

**문장을 만들지 않는다** — 출처의 시황 기사(제목·요약 원문·언론사·시각·주소)를 그대로 싣는다. 까닭을
지어내면 틀려도 그럴듯해 보인다(spec FR-027 실패 양상).

- 고르기: 마지막 세션 날짜(그 시장 현지 0시) 이후 게시된 기사만, 출처 차례로 위에서부터 최대 3개,
  같은 제목은 한 번. 게시 시각을 모르는 기사는 고르지 않는다 — 지난 변화의 기사일 수 있다
- 세션 날짜는 현재 시세(카드와 같은 값)의 `session_date`다. 시세가 없으면 그 시장 현지 어제다
- **저장하지 않는다** — 지표마다 메모리에 `DASHBOARD_COMMENTARY_CACHE_SECONDS`(기본 600) 둔다.
  실패는 뉴스 칸(T076)과 같은 물러서기다(`NEWS_FAILURE_CACHE_SECONDS`부터 두 배씩
  `NEWS_FAILURE_CACHE_MAX_SECONDS`까지)
- 출처를 부를 때마다 수집 로그에 한 줄(`commentary_fetch`) — 뉴스 칸과 같은 까닭
"""

from __future__ import annotations

import asyncio
import datetime as dt
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Final, Protocol
from zoneinfo import ZoneInfo

from src.config.settings import Settings
from src.ingestion.news.commentary import CommentaryItem, source_of, source_url
from src.ingestion.news.errors import FailureReason, NewsError
from src.ingestion.news.types import normalize_title
from src.observability.logging_config import collection_logger
from src.simulation.market_indicators import Indicator
from src.simulation.market_quote import MarketQuote
from src.simulation.market_session import market, trading_date

Json = dict[str, object]
_SECOND: Final = dt.timedelta(seconds=1)
_DAY: Final = dt.timedelta(days=1)
#: 환율의 하루 경계는 출처 일봉의 런던 0시다(`market_session.trading_date`와 같다).
_LONDON: Final = ZoneInfo("Europe/London")
LIMIT: Final = 3


class CommentaryFetcher(Protocol):
    async def fetch(self, indicator_id: str) -> list[CommentaryItem]: ...


class QuoteLookup(Protocol):
    async def quote(self, indicator_id: str) -> MarketQuote | None: ...


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def since_of(session_date: dt.date, market_key: str) -> dt.datetime:
    """그 세션 날짜의 시장 현지 0시(UTC)."""
    zone = _LONDON if market_key == "fx" else market(market_key).zone
    return dt.datetime.combine(session_date, dt.time(0), tzinfo=zone).astimezone(dt.UTC)


def select_items(
    items: Sequence[CommentaryItem], *, since: dt.datetime, limit: int = LIMIT
) -> list[CommentaryItem]:
    """세션 이후의 기사를 출처 차례로 위에서부터 `limit`개. 같은 제목(공백을 접은)은 한 번."""
    out: list[CommentaryItem] = []
    seen: set[str] = set()
    for item in items:
        if item.published_at is None or item.published_at < since:
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


@dataclass(frozen=True, slots=True)
class _Failure:
    reason: FailureReason
    message: str
    until: dt.datetime
    count: int


class CommentaryService:
    def __init__(
        self,
        fetcher: CommentaryFetcher,
        quotes: QuoteLookup | None,
        settings: Settings,
        *,
        clock: Callable[[], dt.datetime] = utc_now,
    ) -> None:
        self._fetcher = fetcher
        self._quotes = quotes
        self._settings = settings
        self._clock = clock
        self._success: dict[str, _Success] = {}
        self._failure: dict[str, _Failure] = {}
        # 잠금은 이벤트 루프에 묶인다 — 처음 쓸 때 만든다
        self._locks: dict[str, asyncio.Lock] = {}

    def _lock(self, indicator_id: str) -> asyncio.Lock:
        lock = self._locks.get(indicator_id)
        if lock is None:
            lock = self._locks[indicator_id] = asyncio.Lock()
        return lock

    def _hold(self, count: int) -> dt.timedelta:
        base = self._settings.news_failure_cache_seconds
        ceiling = self._settings.news_failure_cache_max_seconds
        return dt.timedelta(seconds=min(base << min(count - 1, 30), ceiling))

    async def _session_date(self, indicator: Indicator, now: dt.datetime) -> dt.date:
        quote = None if self._quotes is None else await self._quotes.quote(indicator.id)
        if quote is not None:
            return quote.session_date
        return trading_date(indicator.market, now) - _DAY

    async def body(self, indicator: Indicator) -> Json:
        """contracts A8 본문. 출처가 실패해도 본문이다(`status: "failed"`)."""
        async with self._lock(indicator.id):
            now = self._clock()
            cached = self._success.get(indicator.id)
            if cached is not None and now < cached.until:
                return cached.body
            remembered = self._failure.get(indicator.id)
            if remembered is not None and now < remembered.until:
                return self._failed(indicator, remembered, now)
            session = await self._session_date(indicator, now)
            try:
                items = await self._fetcher.fetch(indicator.id)
            except NewsError as exc:
                count = 1 if remembered is None else remembered.count + 1
                failure = _Failure(exc.reason, str(exc), now + self._hold(count), count)
                self._failure[indicator.id] = failure
                self._success.pop(indicator.id, None)
                _event(
                    "commentary_fetch",
                    indicator=indicator.id,
                    status="failed",
                    reason=exc.reason,
                    detail=str(exc),
                )
                return self._failed(indicator, failure, now)
            self._failure.pop(indicator.id, None)
            chosen = select_items(items, since=since_of(session, indicator.market))
            body: Json = {
                **self._head(indicator),
                "status": "ok" if chosen else "none",
                "fetchedAt": _iso(now),
                "sessionDate": session.isoformat(),
                "items": [_item_json(item) for item in chosen],
                "failure": None,
            }
            seconds = dt.timedelta(seconds=self._settings.dashboard_commentary_cache_seconds)
            self._success[indicator.id] = _Success(body, now + seconds)
            _event(
                "commentary_fetch",
                indicator=indicator.id,
                status="ok",
                items=len(items),
                chosen=len(chosen),
            )
            return body

    def _head(self, indicator: Indicator) -> Json:
        return {
            "indicator": indicator.id,
            "source": source_of(indicator.id).name,
            "sourceUrl": source_url(indicator.id, self._settings),
        }

    def _failed(self, indicator: Indicator, failure: _Failure, now: dt.datetime) -> Json:
        remaining = failure.until - now
        seconds = -(-remaining // _SECOND) if remaining > dt.timedelta(0) else 0
        return {
            **self._head(indicator),
            "status": "failed",
            "fetchedAt": None,
            "sessionDate": None,
            "items": [],
            "failure": {
                "reason": failure.reason,
                "message": failure.message,
                "retryAfterSeconds": seconds,
            },
        }


_shared: CommentaryService | None = None


def set_shared_service(service: CommentaryService | None) -> None:
    """앱 수명의 서비스 — `lifespan`이 둔다(ASGITransport 테스트는 직접 둔다)."""
    global _shared
    _shared = service


def get_shared_service() -> CommentaryService | None:
    return _shared
