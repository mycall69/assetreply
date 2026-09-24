"""통합 테스트 공용 픽스처 — 스키마 초기화와 스텁 데이터 소스."""
from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from src.config.settings import Settings, load_settings
from src.db.engine import create_engine, dispose_engine
from src.db.migrate import reset_schema
from src.db.session import make_session_factory
from src.ingestion.protocols import DailyQuote, FetchOutcome, FetchResult, ItemMapping


@pytest.fixture
def settings() -> Settings:
    return load_settings()


@pytest.fixture
async def engine(settings: Settings):
    eng = create_engine(settings)
    await reset_schema()
    yield eng
    await dispose_engine(eng)


@pytest.fixture
def session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return make_session_factory(engine)


class StubSource:
    """`FxRateSource` 스텁. 네트워크를 쓰지 않는다(헌법 원칙 III)."""

    def __init__(self, quotes: dict[str, list[tuple[str, str]]] | None = None,
                 *, unit: int = 1) -> None:
        self._quotes = quotes or {}
        self._unit = unit
        self.requests: list[tuple[str, dt.date, dt.date]] = []
        self.raise_on_call: Exception | None = None
        # N번째 호출부터 예외를 던진다 (중단 시나리오용)
        self.raise_after: int = 0

    async def fetch_daily_rates(
        self, currency_code: str, date_from: dt.date, date_to: dt.date
    ) -> FetchResult:
        self.requests.append((currency_code, date_from, date_to))
        if self.raise_on_call is not None and len(self.requests) > self.raise_after:
            raise self.raise_on_call
        rows = [
            DailyQuote(dt.date.fromisoformat(d), Decimal(v), self._unit)
            for d, v in self._quotes.get(currency_code, [])
            if date_from <= dt.date.fromisoformat(d) <= date_to
        ]
        outcome = FetchOutcome.OK if rows else FetchOutcome.NO_DATA
        return FetchResult(tuple(rows), outcome, "{}", 200,
                           None if rows else "INFO-200")

    async def verify_item_mapping(self, currency_code: str) -> ItemMapping:
        return ItemMapping(currency_code, "0000001", "스텁")


@pytest.fixture
def captured():
    """수집 로거에 직접 핸들러를 붙여 기록을 모은다.

    `caplog`를 쓰지 않는 이유는 그것이 루트 핸들러에 의존하기 때문이다. 수집 로거는
    전파하지 않는 것이 요구사항이라(research R3-10), 전파에 기대는 검증은 요구사항과
    모순된다.
    """
    import logging

    from src.observability.logging_config import COLLECTION_LOGGER_NAME

    records: list[logging.LogRecord] = []

    class _Collect(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append(record)

    logger = logging.getLogger(COLLECTION_LOGGER_NAME)
    handler = _Collect()
    saved_level, saved_propagate = logger.level, logger.propagate
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.disabled = False
    try:
        yield records
    finally:
        logger.removeHandler(handler)
        logger.level, logger.propagate = saved_level, saved_propagate
