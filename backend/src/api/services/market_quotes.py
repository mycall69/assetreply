"""대시보드 현재 시세 서비스 (014 T034) — FR-003~FR-009, FR-018, SC-003, SC-007, research
R14-6·R14-8, contracts A1.

- **출처는 묶어서 한 번** — 결과를 `MARKET_QUOTE_CACHE_SECONDS`(기본 30초) 동안 두고, 같은 순간의
  요청은 잠금 하나로 기다리게 해
  한 번만 부른다(단일 비행 — 탭이 여럿이어도 FR-008). 실패는
  `MARKET_QUOTE_FAILURE_CACHE_SECONDS`(기본 10초)만 기억한다
- **카드마다 따로 실패한다**(FR-009) — 한 지표가 빠지면 그 카드만 실패다. 출처 전체가 실패하면
  지표마다 마지막 성공 값을
  "새로 받지 못함"(`stale`)과 함께 보인다
- **전일 종가는 이력에서** 읽는다(R14-8) — 저장소를 Protocol로 받는다(헌법 원칙 IV)
- 저장하지 않는다 — 현재 시세는 메모리에만 있다(시장 환율 포함 — 명확화 2)
"""

from __future__ import annotations

import asyncio
import datetime as dt
from collections.abc import Callable, Sequence
from decimal import Decimal
from typing import Final, Protocol

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.config.settings import Settings
from src.ingestion.yahoo.market import Failure, QuoteFetch, failure_kind
from src.ingestion.yahoo.market_symbols import multiplier_of
from src.repository import market_daily
from src.simulation.market_indicators import INDICATORS, Indicator
from src.simulation.market_indicators import get as get_indicator
from src.simulation.market_quote import MarketQuote, SourceQuote, compose_quote, session_date_of
from src.simulation.market_session import display_timezone

Json = dict[str, object]

#: 화면이 보이는 출처 이름(FR-025).
SOURCE_NAME: Final = "Yahoo Finance"


class MarketQuoteSource(Protocol):
    """현재 시세 출처. 어댑터를 교체할 수 있도록 Protocol에 의존한다(헌법 원칙 II·IV)."""

    async def fetch_quotes(self, indicator_ids: Sequence[str]) -> QuoteFetch: ...


class MarketHistoryRepository(Protocol):
    """저장된 이력 — 카드의 전일 종가와 커버리지 끝."""

    async def previous_close(
        self, indicator_id: str, before: dt.date
    ) -> tuple[dt.date, Decimal] | None: ...

    async def coverage_through(self, indicator_id: str) -> dt.date | None: ...


class DbMarketHistory:
    """`MarketHistoryRepository`의 DB 구현.

    부를 때마다 세션을 연다 — 서비스는 앱 수명과 함께 산다.
    """

    def __init__(self, factory: async_sessionmaker[AsyncSession]) -> None:
        self._factory = factory

    async def previous_close(
        self, indicator_id: str, before: dt.date
    ) -> tuple[dt.date, Decimal] | None:
        async with self._factory() as session:
            return await market_daily.previous_close(session, indicator_id, before)

    async def coverage_through(self, indicator_id: str) -> dt.date | None:
        async with self._factory() as session:
            row = await market_daily.get_coverage(session, indicator_id)
            return None if row is None else row.covered_through


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def dec(value: Decimal) -> str:
    """금액 문자열 — 지수 표기 없이(011 `stock_recurring.dec`와 같은 까닭)."""
    return format(value, "f")


def _iso(instant: dt.datetime) -> str:
    return instant.astimezone(dt.UTC).isoformat().replace("+00:00", "Z")


def quote_json(quote: MarketQuote) -> Json:
    previous = quote.previous
    return {
        "value": dec(quote.value),
        "valueTime": _iso(quote.value_time),
        "sessionDate": quote.session_date.isoformat(),
        "state": quote.state,
        "provisional": quote.provisional,
        "delayMinutes": quote.delay_minutes,
        "previous": None
        if previous is None
        else {
            "close": dec(previous.close),
            "date": None if previous.date is None else previous.date.isoformat(),
            "from": previous.source,
        },
        "change": None if quote.change is None else dec(quote.change),
        "changeRate": None if quote.change_rate is None else dec(quote.change_rate),
        "changeRateBlank": quote.change_rate_blank,
        "direction": quote.direction,
    }


def indicator_json(indicator: Indicator) -> Json:
    return {
        "id": indicator.id,
        "name": indicator.name,
        "group": indicator.group,
        "order": indicator.order,
        "unit": indicator.unit,
        "kind": indicator.kind,
        "market": {"key": indicator.market, "timezone": display_timezone(indicator.market)},
        "notes": list(indicator.notes),
    }


class MarketQuoteService:
    """현재 시세 캐시·단일 비행·마지막 성공 값."""

    def __init__(
        self,
        source: MarketQuoteSource,
        history: MarketHistoryRepository,
        settings: Settings,
        *,
        clock: Callable[[], dt.datetime] = utc_now,
    ) -> None:
        self._source = source
        self._history = history
        self._settings = settings
        self._clock = clock
        self._lock: asyncio.Lock | None = None
        self._fetch: QuoteFetch | None = None
        self._fetched_at: dt.datetime | None = None
        self._failure: Failure | None = None
        self._failure_until: dt.datetime | None = None
        self._last_good: dict[str, tuple[SourceQuote, dt.datetime]] = {}

    async def _current(self) -> tuple[QuoteFetch | None, Failure | None, dt.datetime]:
        if self._lock is None:
            self._lock = asyncio.Lock()
        async with self._lock:
            now = self._clock()
            cache = dt.timedelta(seconds=self._settings.market_quote_cache_seconds)
            if (
                self._fetch is not None
                and self._fetched_at is not None
                and now - self._fetched_at < cache
            ):
                return self._fetch, None, self._fetched_at
            if (
                self._failure is not None
                and self._failure_until is not None
                and now < self._failure_until
            ):
                return None, self._failure, now
            try:
                fetch = await self._source.fetch_quotes([i.id for i in INDICATORS])
            except (
                Exception
            ) as exc:  # 출처의 어떤 실패도 카드 실패로 보인다 — 화면 전체를 막지 않는다(FR-009)
                self._failure = Failure(failure_kind(exc), str(exc) or "시세 출처가 실패했습니다.")
                self._failure_until = now + dt.timedelta(
                    seconds=self._settings.market_quote_failure_cache_seconds
                )
                self._fetch, self._fetched_at = None, None
                return None, self._failure, now
            self._failure, self._failure_until = None, None
            self._fetch, self._fetched_at = fetch, now
            for indicator_id, quote in fetch.quotes.items():
                self._last_good[indicator_id] = (quote, now)
            return fetch, None, now

    async def _compose(
        self, indicator: Indicator, quote: SourceQuote, fetched_at: dt.datetime
    ) -> MarketQuote:
        history_previous: tuple[dt.date, Decimal] | None = None
        coverage: dt.date | None = None
        if indicator.history == "market":
            session_date = session_date_of(indicator, quote)
            history_previous = await self._history.previous_close(indicator.id, session_date)
            coverage = await self._history.coverage_through(indicator.id)
        return compose_quote(
            indicator,
            quote,
            multiplier=multiplier_of(indicator.id),
            history_previous=history_previous,
            coverage_through=coverage,
            now=self._clock(),
            fetched_at=fetched_at,
            delay_notice_seconds=self._settings.market_delay_notice_seconds,
            holiday_detect_seconds=self._settings.market_holiday_detect_seconds,
        )

    async def _entry(
        self,
        indicator: Indicator,
        fetch: QuoteFetch | None,
        failure: Failure | None,
        fetched_at: dt.datetime,
    ) -> tuple[MarketQuote | None, bool, Failure | None]:
        quote = None if fetch is None else fetch.quotes.get(indicator.id)
        if quote is not None:
            return await self._compose(indicator, quote, fetched_at), False, None
        own = failure if fetch is None else fetch.failures.get(indicator.id)
        last = self._last_good.get(indicator.id)
        if last is None:
            return None, False, own
        return await self._compose(indicator, last[0], last[1]), True, own

    async def quote(self, indicator_id: str) -> MarketQuote | None:
        """지표 하나의 카드 값(그래프의 잠정 꼬리·지표 화면 머리 — 카드와 같은 값)."""
        indicator = get_indicator(indicator_id)
        if indicator is None:
            return None
        fetch, failure, fetched_at = await self._current()
        composed, _, _ = await self._entry(indicator, fetch, failure, fetched_at)
        return composed

    async def quotes_body(self) -> Json:
        """contracts A1 본문. 출처가 실패해도 늘 15개다."""
        fetch, failure, fetched_at = await self._current()
        items: list[Json] = []
        for indicator in INDICATORS:
            composed, stale, own = await self._entry(indicator, fetch, failure, fetched_at)
            items.append(
                {
                    **indicator_json(indicator),
                    "status": "ok" if composed is not None else "failed",
                    "quote": None if composed is None else quote_json(composed),
                    "stale": stale,
                    "failure": None if own is None else {"kind": own.kind, "message": own.message},
                }
            )
        return {
            "fetchedAt": _iso(fetched_at),
            "refreshAfterSeconds": self._settings.dashboard_refresh_seconds,
            "source": SOURCE_NAME,
            "indicators": items,
        }


_SHARED: MarketQuoteService | None = None


def set_shared_service(service: MarketQuoteService | None) -> None:
    """`lifespan`이 앱 수명 동안의 서비스를 놓는다(010 `apt_naver_link` 관례). 테스트가 스텁을
    놓는다."""
    global _SHARED
    _SHARED = service


def get_shared_service() -> MarketQuoteService | None:
    return _SHARED
