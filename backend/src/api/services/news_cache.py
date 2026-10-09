"""대시보드 뉴스 캐시 (014 T076) — FR-020, FR-023, FR-024, research R14-13, contracts A5.

**저장하지 않는다**(FR-023) — 서버 메모리에만 둔다. 앱을 다시 띄우면 비어 있다가 처음 열 때 받는다.

- **성공**은 `NEWS_CACHE_SECONDS`(기본 600) 동안 둔다 — 화면을 열 때마다·탭마다 세 사이트를 다시
  긁지 않는다
- **실패**는 `NEWS_FAILURE_CACHE_SECONDS`(기본 60)부터 기억하고, 연달아 실패하면 두 배씩
  `NEWS_FAILURE_CACHE_MAX_SECONDS`
  (기본 600)까지 늘린다(물러서기). 기억이 남은 동안의 재요청은 출처를 부르지 않고 같은 실패와 남은
  시간
  (`retryAfterSeconds`)을 준다. 성공하면 처음으로 돌아간다 — 오래 기억하면 출처가 돌아온 뒤에도
  실패가 보인다
- **칸마다 따로다** — 잠금·기억이 칸마다라 느리거나 실패한 칸이 다른 칸을 막지 않는다(FR-024). 같은
  칸의 동시 요청은
  출처를 한 번 부른다(단일 비행)
"""

from __future__ import annotations

import asyncio
import datetime as dt
import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Final, Protocol

from src.config.settings import Settings
from src.ingestion.news.errors import FailureReason, NewsError
from src.ingestion.news.types import NewsItem, NewsList, SourceKey

Json = dict[str, object]
_log = logging.getLogger(__name__)
_SECOND: Final = dt.timedelta(seconds=1)


class NewsSource(Protocol):
    async def fetch(self, source: SourceKey) -> NewsList: ...


@dataclass(frozen=True, slots=True)
class SourceInfo:
    name: str
    url: str
    list: str


#: 칸의 이름·출처 화면(칸에 거는 링크 — FR-020 표)·목록 이름.
INFO: Final[dict[SourceKey, SourceInfo]] = {
    "kr": SourceInfo("네이버 증권", "https://stock.naver.com/news", "주요뉴스"),
    "us": SourceInfo(
        "Yahoo Finance", "https://finance.yahoo.com/topic/latest-news/", "Latest News"
    ),
    "jp": SourceInfo("Yahoo!ファイナンス", "https://finance.yahoo.co.jp/news", "ヘッドライン"),
}


@dataclass(frozen=True, slots=True)
class _Success:
    listed: NewsList
    until: dt.datetime


@dataclass(frozen=True, slots=True)
class _Failure:
    reason: FailureReason
    message: str
    until: dt.datetime
    #: 연달아 실패한 수 — 다음 기억 시간을 정한다
    count: int


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def _iso(moment: dt.datetime) -> str:
    """초까지의 UTC(contracts A5 — `2026-10-09T13:12:30Z`). 마이크로초는 버린다(T081 실측)."""
    return moment.astimezone(dt.UTC).replace(tzinfo=None, microsecond=0).isoformat() + "Z"


def _item_json(item: NewsItem) -> Json:
    return {
        "rank": item.rank,
        "title": item.title,
        "url": item.url,
        "publisher": item.publisher,
        "publishedAt": None if item.published_at is None else _iso(item.published_at),
        "publishedDate": None if item.published_date is None else item.published_date.isoformat(),
        "publishedText": item.published_text,
        "paid": item.paid,
    }


class NewsCache:
    def __init__(
        self,
        source: NewsSource,
        settings: Settings,
        *,
        clock: Callable[[], dt.datetime] = utc_now,
    ) -> None:
        self._source = source
        self._settings = settings
        self._clock = clock
        self._success: dict[SourceKey, _Success] = {}
        self._failure: dict[SourceKey, _Failure] = {}
        # 잠금은 이벤트 루프에 묶인다 — 처음 쓸 때 만든다(테스트마다 루프가 다르다)
        self._locks: dict[SourceKey, asyncio.Lock] = {}

    def _lock(self, source: SourceKey) -> asyncio.Lock:
        lock = self._locks.get(source)
        if lock is None:
            lock = self._locks[source] = asyncio.Lock()
        return lock

    def _hold(self, count: int) -> dt.timedelta:
        """`count`번째 연속 실패의 기억 시간 — 처음 값에서 두 배씩, 상한까지."""
        base = self._settings.news_failure_cache_seconds
        ceiling = self._settings.news_failure_cache_max_seconds
        return dt.timedelta(seconds=min(base << min(count - 1, 30), ceiling))

    async def body(self, source: SourceKey) -> Json:
        """contracts A5의 본문. 출처가 실패해도 본문이다(`status: "failed"`)."""
        async with self._lock(source):
            now = self._clock()
            cached = self._success.get(source)
            if cached is not None and now < cached.until:
                return self._ok(source, cached.listed)
            remembered = self._failure.get(source)
            if remembered is not None and now < remembered.until:
                return self._failed(source, remembered, now)
            _log.info("뉴스 출처 요청: %s", source)
            try:
                listed = await self._source.fetch(source)
            except NewsError as exc:
                count = 1 if remembered is None else remembered.count + 1
                failure = _Failure(exc.reason, str(exc), now + self._hold(count), count)
                self._failure[source] = failure
                self._success.pop(source, None)
                _log.warning("뉴스 출처 실패: %s %s", source, exc.reason)
                return self._failed(source, failure, now)
            self._failure.pop(source, None)
            seconds = dt.timedelta(seconds=self._settings.news_cache_seconds)
            self._success[source] = _Success(listed, now + seconds)
            return self._ok(source, listed)

    def _head(self, source: SourceKey) -> Json:
        info = INFO[source]
        return {"source": source, "sourceName": info.name, "sourceUrl": info.url, "list": info.list}

    def _ok(self, source: SourceKey, listed: NewsList) -> Json:
        return {
            **self._head(source),
            "status": "ok",
            "fetchedAt": _iso(listed.fetched_at),
            "items": [_item_json(item) for item in listed.items],
            "failure": None,
        }

    def _failed(self, source: SourceKey, failure: _Failure, now: dt.datetime) -> Json:
        remaining = failure.until - now
        # 남은 시간은 올림한 초다 — 0이 되기 전에는 "곧바로"라고 말하지 않는다
        seconds = -(-remaining // _SECOND) if remaining > dt.timedelta(0) else 0
        return {
            **self._head(source),
            "status": "failed",
            "fetchedAt": None,
            "items": [],
            "failure": {
                "reason": failure.reason,
                "message": failure.message,
                "retryAfterSeconds": seconds,
            },
        }


_shared: NewsCache | None = None


def set_shared_service(cache: NewsCache | None) -> None:
    """앱 수명의 캐시 — `lifespan`이 둔다(ASGITransport는 lifespan을 돌리지 않아 테스트가 둔다)."""
    global _shared
    _shared = cache


def get_shared_service() -> NewsCache | None:
    return _shared
