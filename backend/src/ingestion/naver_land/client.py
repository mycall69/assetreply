"""Npay 부동산 단지 자동완성 HTTP 클라이언트 (010 반복 3, FR-029, research R10-19).

**공개되지 않은 내부 API를 쓴다.** Npay 부동산 검색 칸이 입력마다 부르는 단지 자동완성이다 — 개인
이용 전제의 잠정 결정이다(헌법 원칙 II 이탈, 010 plan Complexity Tracking). 출처가 막히는 것은
"언젠가"가 아니라 "언제"의 문제로 전제한다 — 막히면 단지 링크가 네이버 검색으로 물러난다.

- **기본 사용자 에이전트는 403이다.** 설정의 브라우저형 문자열과 `Referer`·`Accept-Language`를 모든
  요청에
  싣는다 — `Accept-Language`가 없으면 곧바로 429다(T067 실측)
- **403은 차단이다** — 재시도로 풀리지 않으므로 바로 실패한다. 429·5xx·연결 오류만 지수 백오프 +
  지터로 다시
  시도한다. 429가 끝까지 이어지면 요청 제한이다
- 짧은 시간에 여러 번 부르면 429다(관찰) — 세마포어 1과 요청 사이 최소 간격을 지킨다. 앱 수명에
  하나를 둔다

동기 호출을 쓰지 않는다(헌법 원칙 I).
"""

from __future__ import annotations

import asyncio
import random
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from types import TracebackType
from typing import Final, Self

import aiohttp

from src.config.settings import Settings
from src.ingestion.naver_land.errors import (
    NaverLandBlocked,
    NaverLandError,
    NaverLandFormatError,
    NaverLandNetworkError,
    NaverLandRateLimited,
)
from src.ingestion.naver_land.parse import NaverComplexCandidate, parse_complexes

#: 한 번에 받는 후보 수 — 검색 칸과 같다.
PAGE_SIZE: Final = "10"


@dataclass(frozen=True, slots=True)
class ComplexSearchFetch:
    """검색어 하나의 후보와 그 원본. 원본은 정규화와 함께 보관한다(헌법 원칙 V)."""

    keyword: str
    candidates: list[NaverComplexCandidate]
    raw: str
    status: int


class NaverLandClient:
    """`async with`로 세션 수명을 관리한다. 넘겨받은 세션은 닫지 않는다 — 수명은 넘겨준 쪽이
    관리한다."""

    def __init__(
        self,
        settings: Settings,
        *,
        session: aiohttp.ClientSession | None = None,
        monotonic: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._settings = settings
        self._session = session
        self._owns_session = session is None
        self._monotonic = monotonic
        self._sleep = sleep
        self._gate = asyncio.Semaphore(1)
        self._last_request_at: float | None = None

    async def __aenter__(self) -> Self:
        if self._session is None:
            timeout = aiohttp.ClientTimeout(total=self._settings.naver_land_request_timeout_seconds)
            self._session = aiohttp.ClientSession(timeout=timeout)
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

    async def search_complexes(self, keyword: str) -> ComplexSearchFetch:
        """검색어의 단지 후보(응답 순서)."""
        url = f"{self._settings.naver_land_base_url}/search/autocomplete/complexes"
        params = {"keyword": keyword, "size": PAGE_SIZE, "page": "0"}
        raw, status = await self._get(url, params)
        return ComplexSearchFetch(keyword=keyword, candidates=parse_complexes(raw), raw=raw,
                                  status=status)

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json, text/plain, */*"}
        # 비워 두면 싣지 않는다 — aiohttp 기본값이 나가 403이 된다(quickstart 15가 이 경로로 차단을
        # 재현한다)
        if self._settings.naver_land_user_agent:
            headers["User-Agent"] = self._settings.naver_land_user_agent
        if self._settings.naver_land_referer:
            headers["Referer"] = self._settings.naver_land_referer
        # 없으면 곧바로 429다 — 요청 제한이 아니라 브라우저답지 않은 요청을 거른다(T067 실측).
        if self._settings.naver_land_accept_language:
            headers["Accept-Language"] = self._settings.naver_land_accept_language
        return headers

    async def _get(self, url: str, params: dict[str, str]) -> tuple[str, int]:
        if self._session is None:
            raise NaverLandNetworkError("클라이언트 세션이 열려 있지 않습니다.")
        attempts = self._settings.naver_land_max_retries
        last: NaverLandError = NaverLandNetworkError("단지 번호 출처에 요청하지 못했습니다.")
        for attempt in range(attempts):
            async with self._gate:
                await self._keep_interval()
                try:
                    async with self._session.get(url, params=params,
                                                 headers=self._headers()) as response:
                        raw = await response.text()
                        status = response.status
                except (aiohttp.ClientError, TimeoutError) as exc:
                    last = NaverLandNetworkError("단지 번호 출처에 연결하지 못했습니다.")
                    last.__cause__ = exc
                else:
                    if status == 200:
                        return raw, status
                    if status == 403:
                        raise NaverLandBlocked("단지 번호 출처가 접근을 막았습니다(403).")
                    if status == 429:
                        last = NaverLandRateLimited("단지 번호 출처가 요청을 제한했습니다(429).")
                    elif status < 500:
                        raise NaverLandFormatError(
                            f"단지 번호 출처가 요청을 거절했습니다({status}).")
                    else:
                        last = NaverLandNetworkError(
                            f"단지 번호 출처가 응답하지 못했습니다({status}).")
            if attempt + 1 < attempts:
                await self._sleep(self._backoff_seconds(attempt))
        raise last

    async def _keep_interval(self) -> None:
        """요청 사이 최소 간격. **요청을 시작한 시각**을 기준으로 잰다."""
        interval = self._settings.naver_land_min_interval_ms / 1000
        if self._last_request_at is not None:
            wait = interval - (self._monotonic() - self._last_request_at)
            if wait > 0:
                await self._sleep(wait)
        self._last_request_at = self._monotonic()

    def _backoff_seconds(self, attempt: int) -> float:
        """지수 백오프 + 지터. 지터는 기준보다 작다."""
        base = self._settings.naver_land_backoff_base_ms / 1000
        delay: float = base * (2 ** attempt) + random.random() * base
        return delay
