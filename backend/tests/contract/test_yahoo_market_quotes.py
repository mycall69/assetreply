"""대시보드 현재 시세 계약 (014 T021) — FR-009, FR-018, research R14-6, 헌법 원칙 II·III.

**네트워크를 쓰지 않는다**(원칙 III). 세션을 흉내 내고 실측 응답 본문(`fixtures/market/`)을 쓴다.

- 15개를 spark **한 번**으로 받는다. 빠지거나 깨진 심볼만 `range=1d` 차트로 다시 부른다
- spark가 429면 차트를 따로 부르지 않고 관문을 쉬게 한다 — 한도 신호를 키우지 않는다
- 숫자는 `Decimal`이다(원칙 VI)
"""

from __future__ import annotations

import dataclasses
import datetime as dt
from decimal import Decimal
from pathlib import Path
from typing import Self

import pytest

from src.config.settings import load_settings
from src.ingestion.yahoo.errors import StockSourceError, StockSourceRateLimited
from src.ingestion.yahoo.gate import YahooGate
from src.ingestion.yahoo.market import YahooMarketClient, failure_kind
from src.ingestion.yahoo.market_parse import MarketBodyInvalid
from src.ingestion.yahoo.market_symbols import SYMBOLS
from src.simulation.market_indicators import INDICATORS

FIX = Path(__file__).parent / "fixtures" / "market"
IDS = [i.id for i in INDICATORS]


def body(name: str) -> str:
    return (FIX / name).read_text(encoding="utf-8")


class Resp:
    def __init__(self, text: str, status: int = 200) -> None:
        self._text = text
        self.status = status

    async def text(self) -> str:
        return self._text

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *exc: object) -> None:
        return None


class Session:
    """경로로 응답을 고른다(spark·심볼별 차트). 요청을 기록한다."""

    def __init__(self, routes: dict[str, Resp]) -> None:
        self.routes = routes
        self.requests: list[tuple[str, dict[str, str]]] = []

    def get(self, url: str, *, params: dict[str, str] | None = None, **_: object) -> Resp:
        path = url.split(".com", 1)[1]
        self.requests.append((path, dict(params or {})))
        return self.routes[path]

    async def close(self) -> None:
        return None


def client(session: Session, gate: YahooGate | None = None) -> YahooMarketClient:
    settings = dataclasses.replace(load_settings(), market_retry_max_attempts=1)
    return YahooMarketClient(settings, session=session, gate=gate or YahooGate(2))  # type: ignore[arg-type]


async def test_spark_한_번으로_15개를_받는다() -> None:
    session = Session({"/v7/finance/spark": Resp(body("spark_15.json"))})
    async with client(session) as yahoo:
        fetched = await yahoo.fetch_quotes(IDS)
    assert len(session.requests) == 1
    path, params = session.requests[0]
    assert path == "/v7/finance/spark"
    assert params["range"] == "1d" and params["interval"] == "1d"
    assert sorted(params["symbols"].split(",")) == sorted(SYMBOLS.values())
    assert sorted(fetched.quotes) == sorted(IDS) and fetched.failures == {}
    kospi = fetched.quotes["kospi"]
    assert kospi.price == Decimal("6625.930000")
    assert kospi.full_day_change == Decimal("-177.970000")
    assert kospi.chart_previous_close == Decimal("6803.900000")
    assert kospi.market_time.tzinfo is dt.UTC
    assert kospi.session_start == dt.datetime(2026, 10, 8, 0, 0, tzinfo=dt.UTC)
    for quote in fetched.quotes.values():
        assert isinstance(quote.price, Decimal)


async def test_빠진_심볼만_차트로_다시_부른다() -> None:
    session = Session(
        {
            "/v7/finance/spark": Resp(body("spark_missing_shanghai.json")),
            "/v8/finance/chart/000001.SS": Resp(body("quote_000001.SS.json")),
        }
    )
    async with client(session) as yahoo:
        fetched = await yahoo.fetch_quotes(IDS)
    assert [p for p, _ in session.requests] == ["/v7/finance/spark", "/v8/finance/chart/000001.SS"]
    assert session.requests[1][1] == {"range": "1d", "interval": "1d"}
    shanghai = fetched.quotes["shanghai"]
    assert shanghai.price == Decimal("3813.791300")
    assert shanghai.full_day_change == Decimal("1.886963")
    assert shanghai.chart_previous_close == Decimal("0.000205")


async def test_다시_불러도_실패하면_그_지표만_실패다() -> None:
    session = Session(
        {
            "/v7/finance/spark": Resp(body("spark_missing_shanghai.json")),
            "/v8/finance/chart/000001.SS": Resp("not found", 404),
        }
    )
    async with client(session) as yahoo:
        fetched = await yahoo.fetch_quotes(IDS)
    assert set(fetched.failures) == {"shanghai"}
    assert fetched.failures["shanghai"].kind == "not_found"
    assert len(fetched.quotes) == 14


async def test_spark가_429면_다시_부르지_않고_관문을_쉬게_한다(no_sleep: list[float]) -> None:
    gate = YahooGate(2)
    paused: list[float] = []
    original = gate.pause

    async def spy(seconds: float) -> None:
        paused.append(seconds)
        await original(seconds)

    gate.pause = spy  # type: ignore[method-assign]
    session = Session({"/v7/finance/spark": Resp(body("rate_limited.txt"), 429)})
    async with client(session, gate) as yahoo:
        with pytest.raises(StockSourceRateLimited) as caught:
            await yahoo.fetch_quotes(IDS)
    assert len(session.requests) == 1 and len(paused) == 1
    assert failure_kind(caught.value) == "rate_limited"


@pytest.mark.parametrize(
    ("text", "status", "kind"),
    [
        ("{not json", 200, "invalid_body"),
        ('{"spark": {"result": null, "error": {"code": "x"}}}', 200, "invalid_body"),
        ("bad gateway", 502, "connection"),
        ("forbidden", 403, "blocked"),
    ],
)
async def test_실패_종류(text: str, status: int, kind: str) -> None:
    session = Session({"/v7/finance/spark": Resp(text, status)})
    async with client(session) as yahoo:
        with pytest.raises(StockSourceError) as caught:
            await yahoo.fetch_quotes(IDS)
    assert failure_kind(caught.value) == kind
    if kind == "invalid_body":
        assert isinstance(caught.value, MarketBodyInvalid)
