"""기준금리 HTTP 클라이언트 (014 반복 2026-10-11d T207) — FR-043, research R14-32.

**공개되지 않은 내부 API**다(헌법 원칙 II 이탈 — 014 plan Complexity Tracking, 사용자 승인
2026-10-11). 앱 수명에 하나다
(`lifespan`이 연다·닫는다). 동기 호출을 쓰지 않는다(원칙 I).

- 목록 `GET {POLICY_RATE_URL}` · 결정 이력 `GET
  {POLICY_RATE_URL}/{국가}/calendars?page=&pageSize=60`(출처 상한 60 — 61이면 400, 실측)
- 사용자 에이전트는 같은 호스트(네이버 증권)의 `NEWS_USER_AGENT`다. 비워 두면 싣지 않는다(차단
  경로를 재현하는 수단)
- 요청 사이 최소 간격(`POLICY_RATE_MIN_INTERVAL_SECONDS`)을 모든 요청이 함께 지킨다
- 401·403은 차단, 429는 요청 제한, 404는 출처에 없음 — 다시 시도하지 않는다. 그 밖의 4xx는 연결
  실패이고 다시 시도하지 않는다.
  연결 오류·시간 초과·5xx만 지수 백오프로 다시 시도한다(`POLICY_RATE_RETRY_*`)
- 출처의 응답 본문과 요청 머리를 오류 문구에 싣지 않는다
"""

from __future__ import annotations

import asyncio
import random
import time
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from types import TracebackType
from typing import Final, Self

import aiohttp

from src.config.settings import Settings
from src.ingestion.naver_rate import parse
from src.ingestion.naver_rate.banks import nation_of
from src.ingestion.naver_rate.errors import (
    PolicyRateBlocked,
    PolicyRateConnectionError,
    PolicyRateError,
    PolicyRateNotFound,
    PolicyRateRateLimited,
)

#: 결정 이력 한 쪽의 행 수 — 출처의 상한이다(R14-32).
PAGE_SIZE: Final = 60
_LANGUAGE: Final = "ko-KR,ko;q=0.9"


@dataclass(frozen=True, slots=True)
class ListFetch:
    """목록 한 번 — 원본 본문과 은행마다의 줄."""

    raw: str
    entries: dict[str, parse.ListEntry]


@dataclass(frozen=True, slots=True)
class CalendarFetch:
    """결정 이력 한 쪽 — 원본 본문과 읽은 쪽."""

    raw: str
    page: parse.CalendarPage


class NaverRateClient:
    """`async with`로 세션 수명을 관리한다. 넘겨받은 세션은 닫지 않는다."""

    def __init__(
        self,
        settings: Settings,
        *,
        session: aiohttp.ClientSession | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self._settings = settings
        self._session = session
        self._owns_session = session is None
        self._sleep = sleep
        self._monotonic = monotonic
        self._last: float | None = None
        # 잠금은 이벤트 루프에 묶인다 — 처음 쓸 때 만든다
        self._lock: asyncio.Lock | None = None

    async def __aenter__(self) -> Self:
        if self._session is None:
            seconds = self._settings.policy_rate_request_timeout_seconds
            self._session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=seconds))
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

    async def fetch_list(self) -> ListFetch:
        """은행 다섯의 최근 결정·다음 결정일. 실패는 `PolicyRateError`다."""
        raw = await self._get(self._settings.policy_rate_url)
        return ListFetch(raw, parse.parse_list(raw))

    async def fetch_calendars(self, bank_id: str, page: int) -> CalendarFetch:
        """그 은행 결정 이력의 한 쪽(1부터). 실패는 `PolicyRateError`다."""
        url = f"{self._settings.policy_rate_url}/{nation_of(bank_id)}/calendars"
        raw = await self._get(url, params={"page": str(page), "pageSize": str(PAGE_SIZE)})
        return CalendarFetch(raw, parse.parse_calendars(raw))

    def _headers(self) -> dict[str, str]:
        headers = {"Accept-Language": _LANGUAGE}
        if self._settings.news_user_agent:
            headers["User-Agent"] = self._settings.news_user_agent
        return headers

    async def _pace(self) -> None:
        """요청 사이 최소 간격 — 모든 요청이 함께 지킨다."""
        gap = self._settings.policy_rate_min_interval_ms / 1000
        if self._last is not None:
            wait = self._last + gap - self._monotonic()
            if wait > 0:
                await self._sleep(wait)
        self._last = self._monotonic()

    async def _get(self, url: str, *, params: Mapping[str, str] | None = None) -> str:
        if self._session is None:
            raise PolicyRateConnectionError("기준금리 클라이언트 세션이 열려 있지 않습니다.")
        if self._lock is None:
            self._lock = asyncio.Lock()
        attempts = max(1, self._settings.policy_rate_retry_max_attempts)
        last: PolicyRateError = PolicyRateConnectionError("기준금리 출처에 연결하지 못했습니다.")
        async with self._lock:
            for attempt in range(attempts):
                await self._pace()
                try:
                    async with self._session.get(
                        url, params=dict(params or {}), headers=self._headers()
                    ) as response:
                        status = response.status
                        raw = await response.text()
                except (aiohttp.ClientError, TimeoutError) as exc:
                    last = PolicyRateConnectionError("기준금리 출처에 연결하지 못했습니다.")
                    last.__cause__ = exc
                else:
                    if status == 200:
                        return raw
                    if status in (401, 403):
                        raise PolicyRateBlocked(f"기준금리 출처가 접근을 막았습니다({status}).")
                    if status == 429:
                        raise PolicyRateRateLimited("기준금리 출처가 요청을 제한했습니다(429).")
                    if status == 404:
                        raise PolicyRateNotFound("기준금리 출처에 그 은행이 없습니다(404).")
                    last = PolicyRateConnectionError(
                        f"기준금리 출처가 응답하지 못했습니다({status}).")
                    if status < 500:
                        raise last
                if attempt + 1 < attempts:
                    base = self._settings.policy_rate_retry_base_delay_ms / 1000
                    await self._sleep(base * (2**attempt) + random.uniform(0, base))
        raise last
