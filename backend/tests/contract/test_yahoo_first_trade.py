"""Yahoo 차트 meta의 첫 거래일 (014 반복 2026-10-10f T159) — FR-033, research R14-26.

**네트워크를 쓰지 않는다**(헌법 원칙 III). 응답은 T158에 받은 본문
픽스처(`fixtures/stock/chart_meta_*`)다.

- 차트 `range=1d&interval=1d` 한 번 — 일봉·배당·분할을 받지 않는다(meta만 쓴다)
- 날짜는 **거래소 시간대**(`exchangeTimezoneName` — `zoneinfo`)의 날짜다. 응답 시점의 고정
  오프셋(`gmtoffset`)으로 바꾸면 출처가 현지 자정을 줄 때 서머타임 차이로 하루 어긋난다(014 R14-3과
  같다)
- 출처가 `firstTradeDate`를 주지 않으면 `None`이다 — 지어내지 않는다(헌법 원칙 V)
"""
from __future__ import annotations

import dataclasses
import datetime as dt
import json
from pathlib import Path
from typing import Self

import pytest

from src.config.settings import load_settings
from src.ingestion.yahoo.client import YahooStockClient
from src.ingestion.yahoo.errors import StockSourceRateLimited, StockSymbolNotFound
from src.ingestion.yahoo.parse import parse_chart

FIXTURES = Path(__file__).parent / "fixtures" / "stock"
D = dt.date.fromisoformat


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


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
    """정해 둔 응답 하나를 돌려주고 요청을 기록한다."""

    def __init__(self, resp: Resp) -> None:
        self.resp = resp
        self.requests: list[tuple[str, dict[str, str]]] = []

    def get(self, url: str, *, params: dict[str, str] | None = None, **_: object) -> Resp:
        self.requests.append((url.split(".com", 1)[1], dict(params or {})))
        return self.resp

    async def close(self) -> None:
        return None


def client(session: Session) -> YahooStockClient:
    settings = dataclasses.replace(load_settings(), stock_retry_max_attempts=1)
    return YahooStockClient(settings, session=session)  # type: ignore[arg-type]


def with_meta(name: str, **meta: object) -> str:
    """픽스처의 meta 칸을 바꾼 본문. 값이 `None`이면 그 칸을 지운다."""
    body = json.loads(fixture(name))
    target = body["chart"]["result"][0]["meta"]
    for key, value in meta.items():
        if value is None:
            target.pop(key, None)
        else:
            target[key] = value
    return json.dumps(body)


@pytest.mark.parametrize(("name", "symbol", "expected"), [
    ("chart_meta_VOO.json", "VOO", "2010-09-09"),
    ("chart_meta_005930_KS.json", "005930.KS", "2000-01-04"),
    ("chart_meta_7203_T.json", "7203.T", "1999-05-06"),
])
async def test_meta만_한_번_받아_거래소_날짜로_읽는다(
        name: str, symbol: str, expected: str) -> None:
    session = Session(Resp(fixture(name)))
    async with client(session) as c:
        day = await c.fetch_first_trade_date(symbol)
    assert day == D(expected)
    assert session.requests == [
        (f"/v8/finance/chart/{symbol}", {"range": "1d", "interval": "1d"})]


async def test_날짜는_고정_오프셋이_아니라_거래소_시간대다() -> None:
    """2010-01-04T04:30Z는 뉴욕 겨울(EST)의 1월 3일 23:30이다.

    응답 시점의 여름 오프셋(-4h)으로 바꾸면 1월 4일이 된다.
    """
    stamp = int(dt.datetime(2010, 1, 4, 4, 30, tzinfo=dt.UTC).timestamp())
    body = with_meta("chart_meta_VOO.json", firstTradeDate=stamp, gmtoffset=-14400)
    async with client(Session(Resp(body))) as c:
        assert await c.fetch_first_trade_date("VOO") == D("2010-01-03")
    # 일봉 청크 파서도 같은 규칙이다(같은 함수를 쓴다)
    assert parse_chart(json.loads(body)).first_trade_date == D("2010-01-03")


async def test_firstTradeDate가_없으면_None이다() -> None:
    body = with_meta("chart_meta_VOO.json", firstTradeDate=None)
    async with client(Session(Resp(body))) as c:
        assert await c.fetch_first_trade_date("VOO") is None


async def test_시간대가_없으면_응답의_오프셋으로_읽는다() -> None:
    body = with_meta("chart_meta_005930_KS.json", exchangeTimezoneName=None)
    async with client(Session(Resp(body))) as c:
        assert await c.fetch_first_trade_date("005930.KS") == D("2000-01-04")


async def test_없는_티커는_404_오류다() -> None:
    async with client(Session(Resp(fixture("chart_not_found.json"), status=404))) as c:
        with pytest.raises(StockSymbolNotFound):
            await c.fetch_first_trade_date("NOSUCHTICKERX")


async def test_요청_제한은_429_오류다() -> None:
    async with client(Session(Resp("Too Many Requests", status=429))) as c:
        with pytest.raises(StockSourceRateLimited):
            await c.fetch_first_trade_date("VOO")
