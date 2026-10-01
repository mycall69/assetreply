"""시세 출처 HTTP 클라이언트 (T012) — 헌법 원칙 I·II.

**이 파일과 형제 모듈이 출처 고유 개념이 존재할 수 있는 유일한 경계다** (원칙 II).

**문서화되지 않은 비공식 엔드포인트를 쓴다.** Yahoo가 2017년 공식 API를 종료한 뒤
대체 공개 API를 내놓지 않았고, 이 호출은 예고 없이 바뀌거나 막힐 수 있다. 원칙 II의
"이용약관 준수" 항목이 미충족이며, 그 이탈은 005 plan의 Complexity Tracking에 기록돼
있다. **출처가 막히는 것은 "언젠가"가 아니라 "언제"의 문제로 전제한다.**

완화 수단 셋을 여기서 지킨다.
- 동시 호출 수 제한 (`asyncio.Semaphore`)
- 지수 백오프 + 지터
- **보수적인 호출 간격.** 공격적 폴링이 차단의 주된 원인이다

동기 호출을 쓰지 않는다 — 요청 처리 경로에서 이벤트 루프를 막으면 수집 처리량과 API
응답성이 동시에 무너진다 (원칙 I).
"""

from __future__ import annotations

import asyncio
import datetime as dt
import random
from types import TracebackType
from typing import Self

import aiohttp

from src.config.settings import Settings
from src.ingestion.yahoo.errors import (
    StockSourceError,
    StockSourceUnavailable,
    raise_for_response,
)
from src.ingestion.yahoo.parse import ChartData, StockQuote, parse_chart, parse_search

#: 출처가 브라우저가 아닌 요청을 거절하므로 일반적인 UA를 보낸다.
_USER_AGENT = "Mozilla/5.0 (compatible; AssetReplay/1.0)"

_SECONDS_PER_DAY = 86_400


class YahooStockClient:
    """시세 조회 어댑터.

    `async with`로 세션 수명을 관리한다. 세션을 재사용해야 연결이 매 요청 새로 열리지
    않는다 — 003에서 세션을 열지 않아 수집이 한 번도 성공하지 못한 적이 있다.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._session: aiohttp.ClientSession | None = None
        self._gate = asyncio.Semaphore(settings.stock_max_concurrent)

    async def __aenter__(self) -> Self:
        timeout = aiohttp.ClientTimeout(
            total=self._settings.stock_request_timeout_seconds)
        self._session = aiohttp.ClientSession(
            timeout=timeout,
            headers={"User-Agent": _USER_AGENT, "Accept": "application/json"},
        )
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if self._session is not None:
            await self._session.close()
            self._session = None

    async def fetch_chart(
        self, symbol: str, date_from: dt.date, date_to: dt.date
    ) -> tuple[ChartData, str, int]:
        """일봉·배당·분할을 한 번에 받는다.

        정규화된 데이터와 **원본 본문·상태 코드**를 함께 돌려준다. 원본을 보관해야
        같은 날짜의 값이 나중에 달라졌을 때 되짚을 수 있다 (FR-046, 시계열 불변식).
        """
        # 종료일을 포함하려면 그날 끝까지 요청해야 한다.
        period1 = int(dt.datetime.combine(date_from, dt.time.min, dt.UTC).timestamp())
        period2 = (
            int(dt.datetime.combine(date_to, dt.time.min, dt.UTC).timestamp())
            + _SECONDS_PER_DAY - 1
        )
        path = f"/v8/finance/chart/{symbol}"
        params = {
            "period1": str(period1),
            "period2": str(period2),
            "interval": "1d",
            "events": "div,splits",
        }
        body, raw, status = await self._get(path, params)
        return parse_chart(body), raw, status

    async def search(self, query: str, limit: int) -> tuple[list[StockQuote], str, int]:
        """종목을 검색한다 (FR-002a).

        목록을 미리 쌓아 두지 않고 검색 시점에 묻는다 — 신규 상장 종목이 빠지지 않는
        근거다 (FR-002c, research R5-2).
        """
        body, raw, status = await self._get(
            "/v1/finance/search",
            {"q": query, "quotesCount": str(limit), "newsCount": "0"},
        )
        return parse_search(body), raw, status

    async def _get(
        self, path: str, params: dict[str, str]
    ) -> tuple[object, str, int]:
        """지수 백오프 + 지터로 재시도한다.

        호출 사이에 **보수적인 간격**을 둔다. 간격을 줄이면 호출 수가 늘어 차단
        위험이 커지는데, 출처가 한도를 공개하지 않아 미리 알 수 없다.
        """
        if self._session is None:
            raise StockSourceUnavailable("클라이언트 세션이 열려 있지 않습니다.")

        url = f"{self._settings.stock_source_base_url}{path}"
        attempts = self._settings.stock_retry_max_attempts
        last: Exception | None = None

        for attempt in range(attempts):
            async with self._gate:
                try:
                    async with self._session.get(url, params=params) as response:
                        raw = await response.text()
                        status = response.status
                        body = _as_json(raw)
                        raise_for_response(status, body)
                        return body, raw, status
                except StockSourceError as exc:
                    last = exc
                except aiohttp.ClientError as exc:
                    last = StockSourceUnavailable("시세 출처에 연결하지 못했습니다.")
                    last.__cause__ = exc
                except TimeoutError as exc:
                    last = StockSourceUnavailable("시세 출처가 응답하지 않습니다.")
                    last.__cause__ = exc

            if attempt + 1 < attempts:
                await asyncio.sleep(self._backoff_seconds(attempt))

        raise last if last is not None else StockSourceUnavailable("알 수 없는 실패")

    def _backoff_seconds(self, attempt: int) -> float:
        """지수 백오프 + 지터.

        지터가 없으면 여러 요청이 같은 순간에 재시도해 차단을 부른다.
        """
        base = self._settings.stock_retry_base_delay_ms / 1000
        delay: float = base * (2 ** attempt)
        return delay + random.uniform(0, base)

    async def delay_between_chunks(self) -> None:
        """청크 사이의 간격. 공격적 폴링이 차단의 주된 원인이다."""
        await asyncio.sleep(self._settings.stock_chunk_delay_ms / 1000)


def _as_json(raw: str) -> object:
    """본문을 JSON으로 읽는다. 실패하면 상태 코드 판정에 맡긴다."""
    import json

    try:
        return json.loads(raw)
    except ValueError:
        return None
