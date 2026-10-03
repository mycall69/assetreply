"""가상자산 출처 HTTP 클라이언트 — investing.com (007 FR-016, FR-018, FR-020, research R7-1·R7-11).

**공개되지 않은 내부 API를 쓴다.** 약관이 허가 없는 저장·사용을 금지하므로 개인 이용 전제의 잠정
결정이다(헌법 원칙 II 이탈, 007 plan Complexity Tracking). 출처가 막히는 것은 "언젠가"가 아니라
"언제"의 문제로 전제한다.

- **기본 사용자 에이전트는 403이다.** 설정의 브라우저형 문자열을 모든 요청에 싣는다. 일봉 요청은
  `domain-id` 헤더도
  필요하다(없으면 400)
- **403은 차단이다** — 재시도로 풀리지 않으므로 바로 실패한다. 429·5xx·연결 오류만 지수 백오프 +
  지터로 다시 시도한다
- **목록 갱신과 시세 수집이 이 클라이언트 하나를 함께 쓴다.** 출처 입장에서는 한 클라이언트다 —
  세마포어 1과 요청 사이
  최소 간격을 두 줄이 공유한다

동기 호출을 쓰지 않는다(헌법 원칙 I).
"""

from __future__ import annotations

import asyncio
import datetime as dt
import random
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from types import TracebackType
from typing import Final, Self

import aiohttp

from src.config.settings import Settings
from src.ingestion.investing.errors import (
    InvestingBlocked,
    InvestingError,
    InvestingFormatError,
    InvestingNetworkError,
)
from src.ingestion.investing.parse import CoinPage, DailyBar, parse_coin_page, parse_daily

#: 판(`en`·`ko`)별 목록 API의 `domain_id`(research R7-4). 한국어 판은 한글 이름만을 위해 받는다.
EDITIONS: Final = {"en": "1", "ko": "18"}
#: 한 쪽의 코인 수. 출처 상한이 100이다("number must be at most 100").
PAGE_LIMIT: Final = 100


@dataclass(frozen=True, slots=True)
class CoinPageFetch:
    """목록 한 쪽과 그 원본. 원본은 정규화와 분리해 보관한다(헌법 원칙 V)."""

    page: CoinPage
    page_no: int
    raw: str
    status: int


@dataclass(frozen=True, slots=True)
class DailyFetch:
    """일봉 한 청크와 그 원본. 원본은 마감 전 일봉까지 그대로다 — 버리는 것은 정규화다."""

    bars: list[DailyBar]
    requested_from: dt.date
    requested_to: dt.date
    raw: str
    status: int


class InvestingClient:
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
            timeout = aiohttp.ClientTimeout(total=self._settings.investing_request_timeout_seconds)
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

    async def fetch_coin_pages(self, edition: str) -> AsyncIterator[CoinPageFetch]:
        """한 판의 목록을 커서로 끝까지 넘기며 쪽마다 내놓는다. 쪽마다 진행을 적을 수 있게 하나씩
        낸다(FR-005b)."""
        domain_id = EDITIONS.get(edition)
        if domain_id is None:
            raise ValueError(f"모르는 판입니다: {edition!r}")
        url = f"{self._settings.investing_coins_base_url}/v1/crypto/coins"
        params = {"sort": "rank", "order": "asc", "limit": str(PAGE_LIMIT), "domain_id": domain_id}
        page_no = 0
        while True:
            raw, status = await self._get(url, params, self._headers())
            page = parse_coin_page(raw)
            page_no += 1
            yield CoinPageFetch(page=page, page_no=page_no, raw=raw, status=status)
            if page.next_cursor is None:
                return
            params = {**params, "cursor": page.next_cursor}

    async def fetch_daily(
        self, source_id: str, start: dt.date, end: dt.date, *, last_day: dt.date
    ) -> DailyFetch:
        """`start`~`end`의 일봉. `last_day`(계산 끝, UTC 어제)보다 뒤의 행은 버린다(FR-022)."""
        url = f"{self._settings.investing_history_base_url}/historical/{source_id}"
        params = {
            "start-date": start.isoformat(), "end-date": end.isoformat(),
            "time-frame": "Daily", "add-missing-rows": "false"}
        headers = {**self._headers(), "domain-id": self._settings.investing_domain_id}
        raw, status = await self._get(url, params, headers)
        return DailyFetch(
            bars=parse_daily(raw, last_day=last_day), requested_from=start, requested_to=end,
            raw=raw, status=status)

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        # 비워 두면 싣지 않는다 — aiohttp 기본값이 나가 403이 된다(quickstart 17이 이 경로로 차단을
        # 재현한다)
        if self._settings.investing_user_agent:
            headers["User-Agent"] = self._settings.investing_user_agent
        return headers

    async def _get(
        self, url: str, params: dict[str, str], headers: dict[str, str]
    ) -> tuple[str, int]:
        if self._session is None:
            raise InvestingNetworkError("클라이언트 세션이 열려 있지 않습니다.")
        attempts = self._settings.investing_max_retries
        last: InvestingError = InvestingNetworkError("시세 출처에 요청하지 못했습니다.")
        for attempt in range(attempts):
            async with self._gate:
                await self._keep_interval()
                try:
                    async with self._session.get(url, params=params, headers=headers) as response:
                        raw = await response.text()
                        status = response.status
                except (aiohttp.ClientError, TimeoutError) as exc:
                    last = InvestingNetworkError("시세 출처에 연결하지 못했습니다.")
                    last.__cause__ = exc
                else:
                    if status == 200:
                        return raw, status
                    if status == 403:
                        raise InvestingBlocked("시세 출처가 접근을 막았습니다(403).")
                    if status != 429 and status < 500:
                        raise InvestingFormatError(f"시세 출처가 요청을 거절했습니다({status}).")
                    last = InvestingNetworkError(f"시세 출처가 응답하지 못했습니다({status}).")
            if attempt + 1 < attempts:
                await self._sleep(self._backoff_seconds(attempt))
        raise last

    async def _keep_interval(self) -> None:
        """요청 사이 최소 간격. **요청을 시작한 시각**을 기준으로 잰다 — 응답이 늦게 와도 다음
        요청을 더 미루지 않는다."""
        interval = self._settings.investing_min_interval_ms / 1000
        if self._last_request_at is not None:
            wait = interval - (self._monotonic() - self._last_request_at)
            if wait > 0:
                await self._sleep(wait)
        self._last_request_at = self._monotonic()

    def _backoff_seconds(self, attempt: int) -> float:
        """지수 백오프 + 지터. 지터가 없으면 여러 요청이 같은 순간에 재시도해 차단을 부른다. 지터는
        기준보다 작다."""
        base = self._settings.investing_backoff_base_ms / 1000
        delay: float = base * (2 ** attempt) + random.random() * base
        return delay
