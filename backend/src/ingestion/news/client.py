"""뉴스 HTTP 클라이언트 (014 T072) — FR-020, FR-024, research R14-13.

세 칸이 aiohttp 세션 하나를 함께 쓴다(앱 수명에 하나 — `lifespan`이 연다·닫는다). 동기 호출을 쓰지
않는다(헌법 원칙 I).

- **브라우저형 사용자 에이전트는 필수다** — Yahoo Finance는 aiohttp 기본값·curl이면 곧바로
  429였다(실측). 설정
  `NEWS_USER_AGENT`. `Accept-Language`는 칸마다(ko-KR·en-US·ja-JP)
- **403은 차단, 429는 요청 제한이다** — 다시 시도로 풀리지 않으므로 바로 실패한다. 실패 기억과
  물러서기는 캐시가
  한다(`api/services/news_cache`). 연결 오류·시간 초과·5xx만 짧게 다시
  시도한다(`NEWS_RETRY_MAX_ATTEMPTS`)
- 출처의 응답 본문과 요청 머리를 오류 문구에 싣지 않는다
"""

from __future__ import annotations

import asyncio
import datetime as dt
from collections.abc import Awaitable, Callable, Mapping
from types import TracebackType
from typing import Final, Self

import aiohttp

from src.config.settings import Settings
from src.ingestion.news import naver, yahoo_jp, yahoo_us
from src.ingestion.news.errors import (
    NewsBlocked,
    NewsConnectionError,
    NewsError,
    NewsRateLimited,
)
from src.ingestion.news.types import NewsItem, NewsList, SourceKey, TextFetcher

#: 연결 오류 뒤 다시 시도하기 전 기다림(초).
RETRY_DELAY_SECONDS: Final = 1.0
#: 응답 머리 한 줄의 최대 바이트. Yahoo Finance 화면의 `Content-Security-Policy`가 약
#: 19.5KB다(2026-10-10 실측 — T081).
#: aiohttp 기본값(8,190)이면 본문을 받기 전에 400 오류가 나 칸이 늘 "연결 실패"다.
MAX_HEADER_FIELD_BYTES: Final = 65_536

Fetch = Callable[[TextFetcher, str], Awaitable[list[NewsItem]]]


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


class NewsClient:
    """`async with`로 세션 수명을 관리한다. 넘겨받은 세션은 닫지 않는다."""

    def __init__(
        self,
        settings: Settings,
        *,
        session: aiohttp.ClientSession | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        clock: Callable[[], dt.datetime] = utc_now,
    ) -> None:
        self._settings = settings
        self._session = session
        self._owns_session = session is None
        self._sleep = sleep
        self._clock = clock

    async def __aenter__(self) -> Self:
        if self._session is None:
            timeout = aiohttp.ClientTimeout(total=self._settings.news_request_timeout_seconds)
            self._session = aiohttp.ClientSession(
                timeout=timeout, max_field_size=MAX_HEADER_FIELD_BYTES
            )
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if self._owns_session and self._session is not None:
            await self._session.close()
            self._session = None

    def _url(self, source: SourceKey) -> str:
        return {
            "kr": self._settings.news_kr_url,
            "us": self._settings.news_us_url,
            "jp": self._settings.news_jp_url,
        }[source]

    async def fetch(self, source: SourceKey) -> NewsList:
        """그 칸의 위 10개. 실패는 `NewsError`다."""
        now = self._clock()
        url = self._url(source)
        if source == "kr":
            items = await naver.fetch(self, url, now=now)
        elif source == "us":
            items = await yahoo_us.fetch(self, url, now=now)
        else:
            items = await yahoo_jp.fetch(self, url, now=now)
        return NewsList(source=source, fetched_at=now, items=tuple(items))

    def _headers(self, accept_language: str) -> dict[str, str]:
        headers = {"Accept-Language": accept_language}
        # 비워 두면 싣지 않는다 — aiohttp 기본값이 나가 429가 된다(차단 경로를 재현하는 수단)
        if self._settings.news_user_agent:
            headers["User-Agent"] = self._settings.news_user_agent
        return headers

    async def get_text(
        self, url: str, *, params: Mapping[str, str] | None = None, accept_language: str
    ) -> str:
        if self._session is None:
            raise NewsConnectionError("뉴스 클라이언트 세션이 열려 있지 않습니다.")
        attempts = max(1, self._settings.news_retry_max_attempts)
        last: NewsError = NewsConnectionError("뉴스 출처에 연결하지 못했습니다.")
        for attempt in range(attempts):
            try:
                async with self._session.get(
                    url, params=dict(params or {}), headers=self._headers(accept_language)
                ) as response:
                    status = response.status
                    raw = await response.text()
            except (aiohttp.ClientError, TimeoutError) as exc:
                last = NewsConnectionError("뉴스 출처에 연결하지 못했습니다.")
                last.__cause__ = exc
            else:
                if status == 200:
                    return raw
                if status == 403:
                    raise NewsBlocked("뉴스 출처가 접근을 막았습니다(403).")
                if status == 429:
                    raise NewsRateLimited("뉴스 출처가 요청을 제한했습니다(429).")
                last = NewsConnectionError(f"뉴스 출처가 응답하지 못했습니다({status}).")
                if status < 500:
                    raise last
            if attempt + 1 < attempts:
                await self._sleep(RETRY_DELAY_SECONDS)
        raise last
