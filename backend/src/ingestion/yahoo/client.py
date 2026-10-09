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
import contextlib
import datetime as dt
import random
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from types import TracebackType
from typing import Self

import aiohttp

from src.config.settings import Settings
from src.ingestion.yahoo.errors import (
    StockSourceError,
    StockSourceRateLimited,
    StockSourceUnavailable,
    raise_for_response,
)
from src.ingestion.yahoo.gate import YahooGate
from src.ingestion.yahoo.parse import (
    ChartFetch,
    RawBody,
    StockQuote,
    parse_chart,
    parse_search,
    parse_splits,
    restore_unadjusted,
)

#: 출처가 브라우저가 아닌 요청을 거절하므로 일반적인 UA를 보낸다.
_USER_AGENT = "Mozilla/5.0 (compatible; AssetReplay/1.0)"

_SECONDS_PER_DAY = 86_400


def _utc_now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def _epoch(day: dt.date) -> int:
    return int(dt.datetime.combine(day, dt.time.min, dt.UTC).timestamp())


class YahooStockClient:
    """시세 조회 어댑터.

    `async with`로 세션 수명을 관리한다. 세션을 재사용해야 연결이 매 요청 새로 열리지
    않는다 — 003에서 세션을 열지 않아 수집이 한 번도 성공하지 못한 적이 있다.
    """

    def __init__(
        self,
        settings: Settings,
        *,
        session: aiohttp.ClientSession | None = None,
        now: Callable[[], dt.datetime] = _utc_now,
        gate: YahooGate | None = None,
    ) -> None:
        self._settings = settings
        # 넘겨받은 세션은 닫지 않는다 — 수명은 넘겨준 쪽이 관리한다
        # (계약 테스트가 흉내 낸 세션을 넣는다).
        self._session = session
        self._owns_session = session is None
        self._now = now
        self._gate = asyncio.Semaphore(settings.stock_max_concurrent)
        # 014 — 대시보드와 함께 지나는 관문(R14-10). **선택 인자다** — 넘기지 않으면 014 전과
        # 같다(FR-026).
        self._shared_gate = gate

    async def __aenter__(self) -> Self:
        if self._session is None:
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
        if self._owns_session and self._session is not None:
            await self._session.close()
            self._session = None

    async def fetch_chart(
        self, symbol: str, date_from: dt.date, date_to: dt.date
    ) -> ChartFetch:
        """일봉·배당·분할을 받아 **원주가로 되살려** 돌려준다 (006 FR-034, research R6-18).

        출처의 시가·종가·배당은 받는 시점까지의 분할을 소급 반영한 값이다. 청크만 보면 그 뒤의
        분할을 알 수 없으므로 **청크 시작일부터 지금까지의 분할 기록**(월봉 — 응답이 작다)을
        함께 받는다. 분할 기록을 받지 못하면 청크도 돌려주지 않는다 — 되살리지 못한 값을
        원주가로 저장하면 분할이 두 번 들어간다.

        두 응답을 모두 원본으로 돌려준다. 원본을 보관해야 같은 날짜의 값이 나중에 달라졌을 때
        되짚을 수 있다 (005 FR-046, 시계열 불변식).
        """
        path = f"/v8/finance/chart/{symbol}"
        # 종료일을 포함하려면 그날 끝까지 요청해야 한다.
        chunk_body, chunk_raw, chunk_status = await self._get(path, {
            "period1": str(_epoch(date_from)),
            "period2": str(_epoch(date_to) + _SECONDS_PER_DAY - 1),
            "interval": "1d",
            "events": "div,splits",
        })
        chart = parse_chart(chunk_body)

        now = self._now()
        history_body, history_raw, history_status = await self._get(path, {
            "period1": str(_epoch(date_from)),
            "period2": str(int(now.timestamp())),
            "interval": "1mo",
            "events": "splits",
        })
        return ChartFetch(
            data=restore_unadjusted(chart, parse_splits(history_body)),
            raws=[
                RawBody("chart", chunk_raw, chunk_status, date_from, date_to),
                RawBody("splits", history_raw, history_status, date_from, now.date()),
            ],
        )

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
                    async with self._slot(), self._session.get(url, params=params) as response:
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
                delay = self._backoff_seconds(attempt)
                if self._shared_gate is not None and isinstance(last, StockSourceRateLimited):
                    # 014 — 한도 신호를 관문에 알린다. 그 백오프 동안 대시보드의 Yahoo 요청도
                    # 기다린다(R14-10).
                    await self._shared_gate.pause(delay)
                else:
                    await asyncio.sleep(delay)

        raise last if last is not None else StockSourceUnavailable("알 수 없는 실패")

    def _slot(self) -> AbstractAsyncContextManager[None]:
        """관문의 자리. 관문이 없으면 아무것도 하지 않는다(014 전과 같다)."""
        if self._shared_gate is None:
            return contextlib.nullcontext()
        return self._shared_gate.slot()

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
