"""대시보드 장중 시세 계약 (014 반복 2026-10-10b T102) — FR-028, research R14-19.

**네트워크를 쓰지 않는다**(원칙 III). 실측 본문(`fixtures/market/intraday_*`)을 쓴다.

- 일(`1d`)은 5분, 주(`5d`)는 30분 질의다 — 같은 차트 엔드포인트(005 이탈)
- 점은 `(UTC 시각, 값)`이고 빈 종가는 건너뛴다(선을 끊지 않는다 — spec FR-014). 엔은 100엔당이다
- 429는 요청 제한이다(관문 전체가 물러선다)
"""

from __future__ import annotations

import dataclasses
import datetime as dt
from decimal import Decimal
from pathlib import Path
from typing import Self

import pytest

from src.config.settings import load_settings
from src.ingestion.yahoo.errors import StockSourceRateLimited
from src.ingestion.yahoo.gate import YahooGate
from src.ingestion.yahoo.market import YahooMarketClient

FIX = Path(__file__).parent / "fixtures" / "market"
SIX = Decimal("0.000001")


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
    def __init__(self, name: str, status: int = 200) -> None:
        self.text = (FIX / name).read_text(encoding="utf-8") if status == 200 else name
        self.status = status
        self.requests: list[tuple[str, dict[str, str]]] = []

    def get(self, url: str, *, params: dict[str, str] | None = None, **_: object) -> Resp:
        self.requests.append((url.split(".com", 1)[1], dict(params or {})))
        return Resp(self.text, self.status)

    async def close(self) -> None:
        return None


def client(session: Session) -> YahooMarketClient:
    settings = dataclasses.replace(
        load_settings(), market_retry_max_attempts=1, market_retry_base_delay_ms=1
    )
    return YahooMarketClient(settings, session=session, gate=YahooGate(2))  # type: ignore[arg-type]


async def test_일은_5분_질의다() -> None:
    session = Session("intraday_GSPC_1d_5m.json")
    async with client(session) as yahoo:
        fetched = await yahoo.fetch_intraday("sp500", "1d")
    # 014 승인 2026-10-10(반복 2026-10-10c T132) — 일은 최근 5세션을 받는다(`range=1d` → `5d`).
    # 본문 해석은 같다
    assert session.requests[0] == ("/v8/finance/chart/^GSPC", {"range": "5d", "interval": "5m"})
    assert len(fetched.points) == 79
    assert fetched.points[0] == (
        dt.datetime(2026, 10, 9, 13, 30, tzinfo=dt.UTC),
        Decimal("7792.56005859375").quantize(SIX),
    )
    assert fetched.points[-1][0] == dt.datetime(2026, 10, 9, 20, 0, tzinfo=dt.UTC)
    times = [t for t, _ in fetched.points]
    assert times == sorted(times)


async def test_주는_30분_질의다() -> None:
    session = Session("intraday_GSPC_5d_30m.json")
    async with client(session) as yahoo:
        fetched = await yahoo.fetch_intraday("sp500", "5d")
    # 014 승인 2026-10-10(반복 2026-10-10c T132) — 주는 최근 1개월을 받는다(`range=5d` → `1mo`)
    assert session.requests[0][1] == {"range": "1mo", "interval": "30m"}
    assert len(fetched.points) == 66
    assert fetched.points[0][0] == dt.datetime(2026, 10, 5, 13, 30, tzinfo=dt.UTC)


async def test_빈_종가는_건너뛴다() -> None:
    session = Session("intraday_KRW_X_5d_30m.json")
    async with client(session) as yahoo:
        fetched = await yahoo.fetch_intraday("usd", "5d")
    assert session.requests[0][0] == "/v8/finance/chart/KRW=X"
    assert len(fetched.points) == 240 - 24
    assert all(value is not None for _, value in fetched.points)


async def test_엔은_100엔당이다() -> None:
    session = Session("intraday_JPYKRW_X_1d_5m.json")
    async with client(session) as yahoo:
        fetched = await yahoo.fetch_intraday("jpy", "1d")
    assert session.requests[0][0] == "/v8/finance/chart/JPYKRW=X"
    assert fetched.points[0][1] == Decimal("8.477999687194824").quantize(SIX) * 100
    assert len(fetched.points) == 288 - 114


async def test_429는_요청_제한이다() -> None:
    session = Session("Edge: Too Many Requests", status=429)
    async with client(session) as yahoo:
        with pytest.raises(StockSourceRateLimited):
            await yahoo.fetch_intraday("sp500", "1d")


# 반복 2026-10-10c(T129) — 왼쪽으로 끌면 앞 구간이 보이도록 받는 범위를 넓힌다(spec FR-028).
# 실측 본문(T128)


async def test_일은_최근_5세션_5분을_받는다() -> None:
    session = Session("intraday_GSPC_5d_5m.json")
    async with client(session) as yahoo:
        fetched = await yahoo.fetch_intraday("sp500", "1d")
    assert session.requests[0] == ("/v8/finance/chart/^GSPC", {"range": "5d", "interval": "5m"})
    assert len(fetched.points) == 391
    assert fetched.points[0] == (
        dt.datetime(2026, 10, 5, 13, 30, tzinfo=dt.UTC),
        Decimal("7738.31005859375").quantize(SIX),
    )
    assert fetched.points[-1][0] == dt.datetime(2026, 10, 9, 20, 0, tzinfo=dt.UTC)


async def test_주는_최근_1개월_30분을_받는다() -> None:
    session = Session("intraday_GSPC_1mo_30m.json")
    async with client(session) as yahoo:
        fetched = await yahoo.fetch_intraday("sp500", "5d")
    assert session.requests[0][1] == {"range": "1mo", "interval": "30m"}
    assert len(fetched.points) == 287
    assert fetched.points[0][0] == dt.datetime(2026, 9, 10, 13, 30, tzinfo=dt.UTC)


async def test_환율_1개월은_빈_종가를_건너뛴다() -> None:
    session = Session("intraday_KRW_X_1mo_30m.json")
    async with client(session) as yahoo:
        fetched = await yahoo.fetch_intraday("usd", "5d")
    assert len(fetched.points) == 1056 - 38
    assert fetched.points[0] == (
        dt.datetime(2026, 9, 9, 23, 0, tzinfo=dt.UTC),  # 런던 09-10 0시(서머타임)
        Decimal("1339.5").quantize(SIX),
    )
