"""ECOS 예금 금리 클라이언트 (008 T010, FR-008, FR-014, FR-016, research R8-5·R8-6).

- **항목 목록**은 통계표마다 한 번 받아 인스턴스에 둔다 — 워커는 클라이언트를 하나만 쓰므로
  프로세스 수명 동안 통계표 둘(예금은행·비은행)에 두 번이다
- 011 — 적금 계열(`…_isav`)도 같은 통계표의 항목 목록을 **함께** 쓴다. 적금 항목은 처음 필요할
  때 받아 둔 본문에서 찾는다 — 항목 목록을 받을 때 함께 찾으면 적금 항목의 변경이 정기예금
  수집까지 멈춘다
- **월 시계열**은 투자처마다 요청 하나로 전체를 받는다(최대 349행 — 1회 행 한도에 여유가 크다)
- 요청은 001과 같은 **관문**(`gate.EcosGate`)을 지난다. 한도 초과면 관문 전체가 백오프한다
- **인증키가 URL 경로에 들어간다.** 돌려주는 결과에는 응답 본문만 담고, 오류 문구에서 키를
  지운다(FR-014)
"""

from __future__ import annotations

import asyncio
import datetime as dt
import random
from collections.abc import Callable
from dataclasses import dataclass
from types import TracebackType
from typing import Final, Self, TypeVar

import aiohttp

from src.config.settings import Settings
from src.ingestion.ecos.deposit_items import TABLE_OF, DepositItem, resolve_deposit_items
from src.ingestion.ecos.deposit_parse import parse_monthly
from src.ingestion.ecos.errors import SourceError, SourceRateLimited, SourceUnavailable
from src.ingestion.ecos.gate import get_gate
from src.ingestion.ecos.installment_items import SERIES_TABLE, resolve_installment_items
from src.ingestion.protocols import MonthlyFetchResult
from src.observability.events import mask_secrets

BASE_URL: Final = "https://ecos.bok.or.kr/api"
FORMAT: Final = "json"
LANGUAGE: Final = "kr"
ROWS: Final = "1/10000"
MONTHLY: Final = "M"

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class ItemsFetch:
    """항목 목록 한 번의 결과 — 원본 본문을 함께 담는다(URL은 없다)."""

    table: str
    items: dict[str, DepositItem]
    raw_body: str
    raw_status: int

    @property
    def source_ref(self) -> str:
        return self.table


@dataclass(frozen=True, slots=True)
class ItemsLookup:
    """투자처의 항목. 이번에 항목 목록을 새로 받았으면 `fetched`에 그 결과(원본 저장용)가 있다."""

    item: DepositItem
    fetched: ItemsFetch | None


class EcosDepositClient:
    """예금 금리 조회 어댑터. `async with`로 세션 수명을 관리한다."""

    def __init__(self, settings: Settings, *, session: aiohttp.ClientSession | None = None) -> None:
        self._settings = settings
        self._session = session
        self._owns_session = session is None
        self._items: dict[str, ItemsFetch] = {}
        self._installment_items: dict[str, DepositItem] = {}

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

    def _url(self, *parts: str) -> str:
        key = self._settings.ecos_api_key.reveal()
        return "/".join((BASE_URL, parts[0], key, FORMAT, LANGUAGE, ROWS, *parts[1:]))

    def _scrub(self, text: str) -> str:
        """오류 문구에 섞여 온 인증키를 지운다 — 키 문자열 그대로와 키처럼 보이는 토큰 모두."""
        cleaned = text.replace(self._settings.ecos_api_key.reveal(), "***")
        return mask_secrets(cleaned) or ""

    async def _get(self, url: str) -> tuple[str, int]:
        if self._session is None:
            raise RuntimeError("EcosDepositClient를 async with로 열어야 합니다.")
        async with get_gate(self._settings).slot():
            try:
                async with self._session.get(url) as response:
                    return await response.text(), response.status
            except aiohttp.ClientError as exc:
                raise SourceUnavailable(self._scrub(f"출처에 연결하지 못했습니다: {exc}")) from exc

    async def _backoff(self, attempt: int, *, rate_limited: bool) -> None:
        base = self._settings.ecos_retry_base_delay_ms / 1000
        delay = base * (2 ** attempt) + random.uniform(0, base)
        if rate_limited:
            await get_gate(self._settings).pause(delay)
        else:
            await asyncio.sleep(delay)

    async def _request(self, url: str, read: Callable[[str, int], T]) -> T:
        """재시도할 수 있는 오류만 다시 시도한다. 오류 문구에서 인증키를 지운다."""
        last: SourceError | None = None
        for attempt in range(self._settings.ecos_retry_max_attempts):
            body, status = await self._get(url)
            try:
                return read(body, status)
            except SourceError as exc:
                exc.args = (self._scrub(str(exc)),)
                if not exc.retryable:
                    raise
                last = exc
                await self._backoff(attempt, rate_limited=isinstance(exc, SourceRateLimited))
        assert last is not None
        raise last

    # ── 공개 ────────────────────────────────────────────────────────

    async def fetch_items(self, table: str) -> ItemsFetch:
        """그 통계표의 항목 목록을 받아 투자처 항목을 확정한다(이름 패턴으로 재확인, R8-1)."""
        url = self._url("StatisticItemList", table) + "/"

        def read(body: str, status: int) -> ItemsFetch:
            if status < 200 or status >= 300:
                raise SourceUnavailable(f"항목 목록 HTTP {status}")
            return ItemsFetch(table, resolve_deposit_items(body, table), body, status)

        fetched = await self._request(url, read)
        self._items[table] = fetched
        return fetched

    async def items_for(self, institution: str) -> ItemsLookup:
        """금리 계열(투자처 또는 적금 계열)의 항목. 그 통계표를 처음 쓰면 항목 목록을 받는다."""
        table = TABLE_OF.get(institution) or SERIES_TABLE[institution]
        cached = self._items.get(table)
        fetched: ItemsFetch | None = None
        if cached is None:
            fetched = cached = await self.fetch_items(table)
        if institution in cached.items:
            return ItemsLookup(cached.items[institution], fetched)
        item = self._installment_items.get(institution)
        if item is None:
            item = resolve_installment_items(cached.raw_body, table)[institution]
            self._installment_items[institution] = item
        return ItemsLookup(item, fetched)

    async def fetch_series(
        self, item: DepositItem, from_month: dt.date, to_month: dt.date
    ) -> MonthlyFetchResult:
        """한 투자처의 월 시계열. `NO_DATA`는 미발표다(오류 아님)."""
        url = self._url("StatisticSearch", item.table, MONTHLY,
                        from_month.strftime("%Y%m"), to_month.strftime("%Y%m"), item.item_code)
        return await self._request(url, lambda body, status: parse_monthly(body, status=status))
