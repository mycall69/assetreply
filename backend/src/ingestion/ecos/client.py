"""ECOS HTTP 클라이언트 (T044).

`FxRateSource` Protocol의 실제 구현체다. **이 파일과 형제 모듈이 ECOS 고유 개념이
존재할 수 있는 유일한 경계다** (헌법 원칙 II).

핵심은 두 가지다.
- 출처는 **오류도 HTTP 200으로 반환**하므로 본문 판별이 필수다 (parser가 담당).
- 호출 제한을 지키기 위해 동시 호출 수를 제한하고 실패 시 지수 백오프 + 지터를 적용한다
  (FR-007, FR-012).
"""

from __future__ import annotations

import asyncio
import datetime as dt
import random
from types import TracebackType
from typing import Self

import aiohttp

from src.config.settings import Settings
from src.ingestion.ecos.errors import SourceError, SourceUnavailable
from src.ingestion.ecos.item_mapping import resolve_item_mapping
from src.ingestion.ecos.parser import parse_search_response
from src.ingestion.protocols import FetchResult, ItemMapping

BASE_URL = "https://ecos.bok.or.kr/api"
STAT_CODE = "731Y001"
CYCLE = "D"
LANGUAGE = "kr"
FORMAT = "json"

# 1회 요청 행 범위. 청크가 365일이라 한 청크는 최대 366행이다 (research R2).
ROW_START = 1
ROW_END = 1000


class EcosClient:
    """ECOS 조회 어댑터.

    `async with`로 세션 수명을 관리한다. 세션을 재사용해야 연결이 매 요청 새로 열리지
    않는다.
    """

    def __init__(
        self,
        settings: Settings,
        *,
        session: aiohttp.ClientSession | None = None,
        item_codes: dict[str, str] | None = None,
    ) -> None:
        self._settings = settings
        self._session = session
        self._owns_session = session is None
        self._semaphore = asyncio.Semaphore(settings.ecos_max_concurrent_per_currency)
        self._item_codes = dict(item_codes or {})

    async def __aenter__(self) -> Self:
        if self._session is None:
            self._session = aiohttp.ClientSession()
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

    # ── 내부 ────────────────────────────────────────────────────────

    def _search_url(self, item_code: str, date_from: dt.date, date_to: dt.date) -> str:
        parts = (
            self._settings.ecos_api_key.reveal(), FORMAT, LANGUAGE,
            str(ROW_START), str(ROW_END), STAT_CODE, CYCLE,
            date_from.strftime("%Y%m%d"), date_to.strftime("%Y%m%d"), item_code,
        )
        return f"{BASE_URL}/StatisticSearch/{'/'.join(parts)}"

    def _item_list_url(self) -> str:
        key = self._settings.ecos_api_key.reveal()
        return f"{BASE_URL}/StatisticItemList/{key}/{FORMAT}/{LANGUAGE}/1/10000/{STAT_CODE}/"

    async def _get(self, url: str) -> tuple[str, int]:
        if self._session is None:
            raise RuntimeError("EcosClient를 async with로 열어야 합니다.")
        async with self._semaphore:
            try:
                async with self._session.get(url) as response:
                    return await response.text(), response.status
            except aiohttp.ClientError as exc:
                raise SourceUnavailable(f"출처에 연결하지 못했습니다: {exc}") from exc

    async def _backoff(self, attempt: int) -> None:
        """지수 백오프 + 지터. 여러 통화가 동시에 재시도하며 겹치는 것을 흩는다."""
        base = self._settings.ecos_retry_base_delay_ms / 1000
        delay = base * (2 ** attempt) + random.uniform(0, base)
        await asyncio.sleep(delay)

    # ── FxRateSource ────────────────────────────────────────────────

    async def fetch_daily_rates(
        self, currency_code: str, date_from: dt.date, date_to: dt.date
    ) -> FetchResult:
        """구간의 일별 매매기준율을 가져온다. 재시도 가능한 오류만 다시 시도한다."""
        item_code = self._item_codes.get(currency_code)
        if item_code is None:
            item_code = (await self.verify_item_mapping(currency_code)).source_item_code

        url = self._search_url(item_code, date_from, date_to)
        last: SourceError | None = None

        for attempt in range(self._settings.ecos_retry_max_attempts):
            body, status = await self._get(url)
            try:
                return parse_search_response(body, status=status)
            except SourceError as exc:
                if not exc.retryable:
                    raise
                last = exc
                await self._backoff(attempt)

        assert last is not None
        raise last

    async def verify_item_mapping(self, currency_code: str) -> ItemMapping:
        """항목코드를 검증하고 바뀌었으면 이름으로 재탐색한다 (FR-015)."""
        body, status = await self._get(self._item_list_url())
        if status < 200 or status >= 300:
            raise SourceUnavailable(f"항목 목록 조회 실패 HTTP {status}")
        known = self._item_codes.get(currency_code, "")
        mapping = resolve_item_mapping(body, currency_code, known_code=known)
        self._item_codes[currency_code] = mapping.source_item_code
        return mapping
