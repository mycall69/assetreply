"""시세 출처 클라이언트 계약 (T105) — 006 FR-034, research R6-18, 헌법 원칙 II·III·V.

**네트워크를 쓰지 않는다**(헌법 원칙 III). 세션을 흉내 내고 응답은 실제 응답 픽스처를 쓴다.

출처의 시세는 **받는 시점까지의 분할을 소급 반영한 값**이다. 청크 하나만 보면 그 뒤의 분할을 알 수
없으므로, 청크마다 **청크 시작일부터 지금까지의 분할 기록**을 함께 받아 원주가로 되살린다. 두 응답을
모두 원본으로 남긴다 — 되살린 값이 틀렸을 때 되짚을 수단이다.
"""
from __future__ import annotations

import dataclasses
import datetime as dt
from decimal import Decimal
from pathlib import Path
from typing import Self

import pytest

from src.config.settings import load_settings
from src.ingestion.yahoo.client import YahooStockClient
from src.ingestion.yahoo.errors import StockSourceUnavailable

FIXTURES = Path(__file__).parent / "fixtures" / "stock"
NOW = dt.datetime(2026, 10, 3, 0, 0, tzinfo=dt.UTC)


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def epoch(day: dt.date) -> int:
    return int(dt.datetime.combine(day, dt.time.min, dt.UTC).timestamp())


class Resp:
    def __init__(self, body: str, status: int = 200) -> None:
        self._body = body
        self.status = status

    async def text(self) -> str:
        return self._body

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *exc: object) -> None:
        return None


class Session:
    """`interval`별로 정해 둔 응답을 돌려준다(일봉 청크 `1d`, 분할 기록 `1mo`). 요청을 기록한다."""

    def __init__(self, routes: dict[str, Resp]) -> None:
        self.routes = routes
        self.requests: list[tuple[str, dict[str, str]]] = []
        self.closed = False

    def get(self, url: str, *, params: dict[str, str] | None = None, **_: object) -> Resp:
        params = dict(params or {})
        self.requests.append((url.split(".com", 1)[1], params))
        return self.routes[params["interval"]]

    async def close(self) -> None:
        self.closed = True


def client(session: Session) -> YahooStockClient:
    settings = dataclasses.replace(load_settings(), stock_retry_max_attempts=1)
    return YahooStockClient(settings, session=session, now=lambda: NOW)  # type: ignore[arg-type]


TOYOTA = (dt.date(2021, 9, 1), dt.date(2021, 10, 29))


async def test_청크와_분할_기록을_함께_받는다() -> None:
    session = Session({"1d": Resp(fixture("chart_split_float.json")),
                       "1mo": Resp(fixture("splits_toyota_since_2021_09.json"))})
    async with client(session) as yahoo:
        await yahoo.fetch_chart("7203.T", *TOYOTA)
    (chunk_path, chunk), (history_path, history) = session.requests
    assert chunk_path == history_path == "/v8/finance/chart/7203.T"
    assert chunk == {"period1": str(epoch(TOYOTA[0])),
                     "period2": str(epoch(TOYOTA[1]) + 86_399),
                     "interval": "1d", "events": "div,splits"}
    # 분할 기록은 **청크 시작일부터 지금까지**다 — 그 뒤의 분할이 청크의 값을 바꿨다.
    assert history == {"period1": str(epoch(TOYOTA[0])),
                       "period2": str(int(NOW.timestamp())),
                       "interval": "1mo", "events": "splits"}


async def test_되살린_원주가를_돌려준다() -> None:
    session = Session({"1d": Resp(fixture("chart_split_float.json")),
                       "1mo": Resp(fixture("splits_toyota_since_2021_09.json"))})
    async with client(session) as yahoo:
        fetched = await yahoo.fetch_chart("7203.T", *TOYOTA)
    prices = {p.quote_date: p.open_raw for p in fetched.data.prices}
    assert prices[dt.date(2021, 9, 28)] == Decimal("10420.000000")
    assert prices[dt.date(2021, 9, 29)] == Decimal("2052.0")
    assert [(s.effective_date, s.numerator, s.denominator) for s in fetched.data.splits] == [
        (dt.date(2021, 9, 29), 5, 1)]


async def test_두_응답을_모두_원본으로_돌려준다() -> None:
    """헌법 시계열 불변식 — 원본과 정규화를 분리 저장. 되살리는 데 쓴 기록도 원본이다."""
    session = Session({"1d": Resp(fixture("chart_split_float.json")),
                       "1mo": Resp(fixture("splits_toyota_since_2021_09.json"))})
    async with client(session) as yahoo:
        fetched = await yahoo.fetch_chart("7203.T", *TOYOTA)
    assert [(r.kind, r.status, r.requested_from, r.requested_to) for r in fetched.raws] == [
        ("chart", 200, *TOYOTA),
        ("splits", 200, TOYOTA[0], NOW.date()),
    ]
    assert fetched.raws[0].body == fixture("chart_split_float.json")
    assert fetched.raws[1].body == fixture("splits_toyota_since_2021_09.json")


async def test_분할_기록이_빈_구간이면_되살릴_것이_없다() -> None:
    """상장 폐지 등으로 청크 이후 시세가 없으면 출처는 400 "Data doesn't exist"를 준다(T097)."""
    session = Session({"1d": Resp(fixture("chart_aapl_2012_08.json")),
                       "1mo": Resp(fixture("chart_no_data_in_range.json"), 400)})
    async with client(session) as yahoo:
        fetched = await yahoo.fetch_chart("AAPL", dt.date(2012, 8, 1), dt.date(2012, 8, 31))
    assert fetched.data.prices[0].open_raw == Decimal("21.99678611755371")
    assert [r.status for r in fetched.raws] == [200, 400]


async def test_분할_기록을_받지_못하면_청크도_돌려주지_않는다() -> None:
    """되살리지 못한 값을 원주가로 저장하면 분할이 두 번 들어간다 — 일부만 돌려주지 않는다."""
    session = Session({"1d": Resp(fixture("chart_split_float.json")),
                       "1mo": Resp("{}", 503)})
    async with client(session) as yahoo:
        with pytest.raises(StockSourceUnavailable):
            await yahoo.fetch_chart("7203.T", *TOYOTA)


async def test_넘겨받은_세션은_닫지_않는다() -> None:
    session = Session({})
    async with client(session):
        pass
    assert session.closed is False
