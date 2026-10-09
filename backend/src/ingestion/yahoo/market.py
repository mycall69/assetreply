"""대시보드 지표 출처 클라이언트 (014 T033·T051) — FR-009, FR-017~FR-019, research
R14-1·R14-2·R14-6·R14-10, 헌법 원칙 I·II.

005와 **같은 Yahoo 비공식 엔드포인트**다(005 이탈의 확장 — 014 plan Complexity Tracking, 사용자 승인
2026-10-09).

- 현재 시세는 `spark` **한 번**으로 15개를 받는다. 빠지거나 깨진 심볼만 `range=1d` 차트로 다시
  부른다. spark 자체가 실패하면
  따로 부르지 않는다 — 한도 신호를 키우지 않는다(R14-6)
- 일봉 이력은 `interval=1d&period1&period2` 청크다(R14-2 — `range=max`는 일봉을 주지 않는다)
- 모든 요청은 **Yahoo 관문**을 지난다 — 주식 수집과 동시 수·429 백오프를 함께 지킨다(R14-10)
- 재시도는 지수 백오프 + 지터다. 429는 관문 전체를 쉬게 한다
"""

from __future__ import annotations

import asyncio
import datetime as dt
import random
from collections.abc import Sequence
from dataclasses import dataclass, field
from types import TracebackType
from typing import Self

import aiohttp

from src.config.settings import Settings
from src.ingestion.yahoo.errors import (
    StockSourceAuthError,
    StockSourceError,
    StockSourceRateLimited,
    StockSourceUnavailable,
    StockSymbolNotFound,
    raise_for_response,
)
from src.ingestion.yahoo.gate import YahooGate, get_yahoo_gate
from src.ingestion.yahoo.market_parse import (
    DailyChunk,
    MarketBodyInvalid,
    load,
    parse_daily,
    parse_quote_chart,
    parse_spark,
)
from src.ingestion.yahoo.market_symbols import symbol_of
from src.simulation.market_quote import SourceQuote

#: 출처가 브라우저가 아닌 요청을 거절하므로 일반적인 UA를 보낸다(주식 클라이언트와 같다).
_USER_AGENT = "Mozilla/5.0 (compatible; AssetReplay/1.0)"
_SECONDS_PER_DAY = 86_400


def _epoch(day: dt.date) -> int:
    return int(dt.datetime.combine(day, dt.time.min, dt.UTC).timestamp())


def failure_kind(exc: BaseException) -> str:
    """실패 종류 — 화면이 종류마다 다른 말을 한다(contracts A1 `failure.kind`)."""
    if isinstance(exc, StockSourceRateLimited):
        return "rate_limited"
    if isinstance(exc, StockSourceAuthError):
        return "blocked"
    if isinstance(exc, StockSymbolNotFound):
        return "not_found"
    if isinstance(exc, MarketBodyInvalid):
        return "invalid_body"
    return "connection"


@dataclass(frozen=True, slots=True)
class Failure:
    kind: str
    message: str


@dataclass(frozen=True, slots=True)
class QuoteFetch:
    """시세 한 번의 결과 — 지표 id마다 시세 또는 실패."""

    quotes: dict[str, SourceQuote] = field(default_factory=dict)
    failures: dict[str, Failure] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class DailyFetch:
    """일봉 청크 한 번의 결과 — 정규화 결과와 원본 본문."""

    chunk: DailyChunk
    raw: str
    status: int
    requested_from: dt.date
    requested_to: dt.date


class YahooMarketClient:
    """대시보드 지표 어댑터. `async with`로 세션 수명을 관리한다."""

    def __init__(
        self,
        settings: Settings,
        *,
        gate: YahooGate | None = None,
        session: aiohttp.ClientSession | None = None,
    ) -> None:
        self._settings = settings
        self._gate = gate
        # 넘겨받은 세션은 닫지 않는다 — 계약 테스트가 흉내 낸 세션을 넣는다.
        self._session = session
        self._owns_session = session is None

    async def __aenter__(self) -> Self:
        if self._session is None:
            timeout = aiohttp.ClientTimeout(total=self._settings.market_request_timeout_seconds)
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

    async def fetch_quotes(self, indicator_ids: Sequence[str]) -> QuoteFetch:
        """지표들의 현재 시세. spark 한 번 + 빠진 심볼만 차트(R14-6). spark가 실패하면 그 예외를
        올린다."""
        symbols = {indicator_id: symbol_of(indicator_id) for indicator_id in indicator_ids}
        body, _, _ = await self._get(
            "/v7/finance/spark",
            {"symbols": ",".join(symbols.values()), "range": "1d", "interval": "1d"},
            retry_rate_limit=False,
        )
        parsed = parse_spark(body)
        quotes: dict[str, SourceQuote] = {}
        failures: dict[str, Failure] = {}
        for indicator_id, symbol in symbols.items():
            quote = parsed.get(symbol)
            if quote is None:
                try:
                    chart, _, _ = await self._get(
                        f"/v8/finance/chart/{symbol}",
                        {"range": "1d", "interval": "1d"},
                        retry_rate_limit=False,
                    )
                    quote = parse_quote_chart(chart)
                except StockSourceError as exc:
                    failures[indicator_id] = Failure(failure_kind(exc), str(exc))
                    continue
            if quote is None:
                failures[indicator_id] = Failure(
                    "invalid_body", "시세 출처가 값을 주지 않았습니다."
                )
                continue
            quotes[indicator_id] = quote
        return QuoteFetch(quotes, failures)

    async def fetch_daily(
        self, indicator_id: str, date_from: dt.date, date_to: dt.date, *, current_date: dt.date
    ) -> DailyFetch:
        """일봉 청크 하나(R14-2). `current_date`(그 시장의 지금 거래일) 이후의 봉은 확정으로 내지
        않는다.

        `period1`은 첫 거래일이 1970년 이전이면 음수 epoch다 — 날짜에서 계산하므로 상수가 없다.
        """
        body, raw, status = await self._get(
            f"/v8/finance/chart/{symbol_of(indicator_id)}",
            {
                "period1": str(_epoch(date_from)),
                "period2": str(_epoch(date_to) + _SECONDS_PER_DAY - 1),
                "interval": "1d",
            },
        )
        chunk = parse_daily(body, current_date=current_date)
        return DailyFetch(chunk, raw, status, date_from, date_to)

    async def delay_between_chunks(self) -> None:
        """청크 사이의 간격. 공격적 폴링이 차단의 주된 원인이다."""
        await asyncio.sleep(self._settings.market_chunk_delay_ms / 1000)

    def _shared_gate(self) -> YahooGate:
        return self._gate if self._gate is not None else get_yahoo_gate(self._settings)

    async def _get(
        self, path: str, params: dict[str, str], *, retry_rate_limit: bool = True
    ) -> tuple[object, str, int]:
        """관문을 지나 한 번 부른다. 연결·5xx는 다시 시도하고, 429는 관문을 쉬게 한다."""
        if self._session is None:
            raise StockSourceUnavailable("클라이언트 세션이 열려 있지 않습니다.")
        url = f"{self._settings.market_source_base_url}{path}"
        gate = self._shared_gate()
        attempts = self._settings.market_retry_max_attempts
        last: StockSourceError | None = None
        for attempt in range(attempts):
            try:
                async with gate.slot(), self._session.get(url, params=params) as response:
                    raw = await response.text()
                    status = response.status
                body = load(raw)
                if status == 200 and body is None:
                    raise MarketBodyInvalid("시세 출처의 응답이 유효하지 않습니다.")
                raise_for_response(status, body)
                return body, raw, status
            except StockSourceRateLimited as exc:
                last = exc
                await gate.pause(self._backoff_seconds(attempt))
                if not retry_rate_limit:
                    raise
                continue
            except StockSymbolNotFound, StockSourceAuthError, MarketBodyInvalid:
                raise
            except StockSourceUnavailable as exc:
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
        """지수 백오프 + 지터 — 지터가 없으면 여러 요청이 같은 순간에 재시도해 차단을 부른다."""
        base = self._settings.market_retry_base_delay_ms / 1000
        delay: float = base * (2**attempt)
        return delay + random.uniform(0, base)
