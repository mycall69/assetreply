"""대시보드 지표 응답 정규화 (014 T033·T051) — FR-009, FR-017, FR-018, research R14-1~R14-6, 헌법
원칙 II.

**출처 고유 필드명이 이 디렉터리 밖으로 나가지 않는다**(원칙 II). 시세(`spark`·`range=1d` 차트)는
`SourceQuote`로, 일봉
청크는 `DailyChunk`로 옮긴다.

- 숫자는 `json.loads(parse_float=Decimal)`로 읽는다 — `float`을 거치지 않는다(원칙 VI). 자릿수는
  저장 열과 같은 소수
  6자리로 맞춘다
- **거래일은 `zoneinfo`로 바꾼다**(R14-3) — 응답의 고정 오프셋(`gmtoffset`)은 응답 시점의 오프셋
  하나라, 겨울에 받은
  여름 자정 봉(선물·외환)이 하루 앞당겨진다
- 종가가 빈 행은 휴일 자리 표시다 — 버린다(R14-4)
- 오늘(현지) 이후의 봉은 확정 목록에 넣지 않는다 — 마감 전 값이다(원본에는 남는다)
"""

from __future__ import annotations

import datetime as dt
import json
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Final
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from src.ingestion.yahoo.errors import StockSourceUnavailable
from src.simulation.market_quote import SourceQuote

_PLACES: Final = Decimal("0.000001")


class MarketBodyInvalid(StockSourceUnavailable):
    """응답 본문을 읽을 수 없다(구조가 바뀌었거나 값이 깨졌다) — 실패 종류 `invalid_body`."""


#: 시가·고가·저가 — 출처가 주지 않거나 0이면 `None`(0으로 메우지 않는다 — 옛 일봉).
Ohlc = tuple[Decimal | None, Decimal | None, Decimal | None]


@dataclass(frozen=True, slots=True)
class DailyChunk:
    """일봉 청크 하나의 정규화 결과."""

    #: 확정 종가 — `(현지 거래일, 종가)` 날짜 차례. 오늘 이후의 봉·종가가 빈 행은 없다.
    closes: list[tuple[dt.date, Decimal]] = field(default_factory=list)
    #: 오늘(현지) 봉 — 확정이 아니다. 없으면 `None`.
    today_bar: tuple[dt.date, Decimal] | None = None
    #: 출처의 첫 거래일(발견). 응답에 없으면 `None`.
    first_trade_date: dt.date | None = None
    #: 확정 종가와 같은 날들의 시가·고가·저가(반복 2026-10-10b). 출처가 주지 않거나 0이면 `None`.
    #: 마지막 칸이다 — 앞 칸의 자리(위치 인자)를 바꾸지 않는다
    ohlc: dict[dt.date, Ohlc] = field(default_factory=dict)


def load(raw: str) -> object:
    """본문을 JSON으로 읽는다. 숫자는 `Decimal`이다. 읽지 못하면 `None`."""
    try:
        parsed: object = json.loads(raw, parse_float=Decimal)
    except ValueError:
        return None
    return parsed


def _decimal(value: object) -> Decimal | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, Decimal):
        return value.quantize(_PLACES) if value.is_finite() else None
    if isinstance(value, int):
        return Decimal(value).quantize(_PLACES)
    return None


def _price(values: object, index: int) -> Decimal | None:
    """시가·고가·저가 한 칸. 목록이 없거나 짧거나 0이면 `None`이다. 음수는 그대로다(WTI 2020-04-20
    저가)."""
    if not isinstance(values, list) or index >= len(values):
        return None
    value = _decimal(values[index])
    return None if value is None or value == 0 else value


def _instant(value: object) -> dt.datetime | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return dt.datetime.fromtimestamp(value, dt.UTC)


def _mapping(value: object) -> dict[str, object]:
    return value if isinstance(value, dict) else {}


def _first(value: object) -> dict[str, object]:
    items = value if isinstance(value, list) else []
    head = items[0] if items else None
    return head if isinstance(head, dict) else {}


def _zone(meta: dict[str, object]) -> ZoneInfo:
    name = meta.get("exchangeTimezoneName")
    if not isinstance(name, str):
        raise MarketBodyInvalid("시세 출처의 응답에 시간대가 없습니다.")
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise MarketBodyInvalid("시세 출처의 응답 시간대를 알 수 없습니다.") from exc


def quote_from_meta(meta: dict[str, object]) -> SourceQuote | None:
    """현재 시세 메타 하나. 값이나 시각이 없으면 `None`(그 지표만 실패 — FR-009)."""
    price = _decimal(meta.get("regularMarketPrice"))
    market_time = _instant(meta.get("regularMarketTime"))
    if price is None or market_time is None:
        return None
    regular = _mapping(_mapping(meta.get("currentTradingPeriod")).get("regular"))
    return SourceQuote(
        price=price,
        market_time=market_time,
        full_day_change=_decimal(meta.get("fulldayChange")),
        chart_previous_close=_decimal(meta.get("chartPreviousClose")),
        session_start=_instant(regular.get("start")),
    )


def parse_spark(body: object) -> dict[str, SourceQuote | None]:
    """spark 응답(심볼 여럿) → 심볼마다 시세. 읽을 수 없는 심볼은 `None`이다."""
    spark = _mapping(_mapping(body).get("spark"))
    results = spark.get("result")
    if not isinstance(results, list):
        raise MarketBodyInvalid("시세 출처의 응답이 유효하지 않습니다.")
    quotes: dict[str, SourceQuote | None] = {}
    for item in results:
        entry = _mapping(item)
        symbol = entry.get("symbol")
        if not isinstance(symbol, str):
            continue
        meta = _mapping(_first(entry.get("response")).get("meta"))
        quotes[symbol] = quote_from_meta(meta) if meta else None
    return quotes


def _chart_result(body: object) -> dict[str, object]:
    chart = _mapping(_mapping(body).get("chart"))
    result = _first(chart.get("result"))
    if not result:
        raise MarketBodyInvalid("시세 출처의 응답이 유효하지 않습니다.")
    return result


def parse_quote_chart(body: object) -> SourceQuote | None:
    """차트 응답(`range=1d`) 하나 → 시세."""
    return quote_from_meta(_mapping(_chart_result(body).get("meta")))


def parse_daily(body: object, *, current_date: dt.date) -> DailyChunk:
    """일봉 청크 → 확정 종가·오늘 봉·첫 거래일.

    `current_date`는 그 시장의 지금 거래일이다(`simulation/market_session.trading_date`) — 이 날
    이후의 봉은 확정이 아니다.
    구간에 시세가 없으면(상장 전) 빈 결과다.
    """
    if body is None:
        raise MarketBodyInvalid("시세 출처의 응답이 유효하지 않습니다.")
    chart = _mapping(_mapping(body).get("chart"))
    results = chart.get("result")
    if results is None and chart.get("error") is None:
        raise MarketBodyInvalid("시세 출처의 응답이 유효하지 않습니다.")
    result = _first(results)
    if not result:
        return DailyChunk()
    meta = _mapping(result.get("meta"))
    zone = _zone(meta)
    first_trade = _instant(meta.get("firstTradeDate"))
    timestamps = result.get("timestamp")
    quote = _first(_mapping(result.get("indicators")).get("quote"))
    closes_raw = quote.get("close")
    if timestamps is None:
        return DailyChunk(
            first_trade_date=None if first_trade is None else first_trade.astimezone(zone).date()
        )
    if (
        not isinstance(timestamps, list)
        or not isinstance(closes_raw, list)
        or len(timestamps) != len(closes_raw)
    ):
        raise MarketBodyInvalid("시세 출처의 일봉이 유효하지 않습니다.")
    current = current_date
    by_day: dict[dt.date, Decimal] = {}
    ohlc: dict[dt.date, Ohlc] = {}
    today_bar: tuple[dt.date, Decimal] | None = None
    for index, (stamp, raw_close) in enumerate(zip(timestamps, closes_raw, strict=True)):
        instant = _instant(stamp)
        close = _decimal(raw_close)
        if instant is None or close is None:
            continue
        day = instant.astimezone(zone).date()
        if day >= current:
            if day == current:
                today_bar = (day, close)
            continue
        by_day[day] = close
        ohlc[day] = _ohlc_at(quote, index)
    return DailyChunk(
        closes=sorted(by_day.items()),
        ohlc=ohlc,
        today_bar=today_bar,
        first_trade_date=None if first_trade is None else first_trade.astimezone(zone).date(),
    )


def _ohlc_at(quote: dict[str, object], index: int) -> Ohlc:
    return (
        _price(quote.get("open"), index),
        _price(quote.get("high"), index),
        _price(quote.get("low"), index),
    )


def parse_intraday(body: object) -> list[tuple[dt.datetime, Decimal]]:
    """장중 차트 → `(UTC 시각, 종가)` 시각 차례(반복 2026-10-10b).

    빈 종가는 건너뛴다 — 값을 지어 넣지 않고 그 점이 없을 뿐이다(원칙 V).
    """
    if body is None:
        raise MarketBodyInvalid("시세 출처의 응답이 유효하지 않습니다.")
    result = _first(_mapping(_mapping(body).get("chart")).get("result"))
    if not result:
        return []
    timestamps = result.get("timestamp")
    closes_raw = _first(_mapping(result.get("indicators")).get("quote")).get("close")
    if not isinstance(timestamps, list) or not isinstance(closes_raw, list):
        return []
    points: list[tuple[dt.datetime, Decimal]] = []
    for stamp, raw_close in zip(timestamps, closes_raw, strict=False):
        instant = _instant(stamp)
        close = _decimal(raw_close)
        if instant is not None and close is not None:
            points.append((instant, close))
    points.sort(key=lambda p: p[0])
    return points


def ohlc_from_raw(raw: str) -> dict[dt.date, Ohlc]:
    """저장해 둔 원본 본문 → 날마다의 시가·고가·저가(종가가 있는 날만). 읽지 못하면 빈 결과다.

    원본에서 되살리기(반복 2026-10-10b — research R14-18)가 쓴다. 오늘 봉도 들어 있을 수 있지만
    되살리기는 저장된
    확정 날만 채우므로 상관없다.
    """
    try:
        result = _first(_mapping(_mapping(load(raw)).get("chart")).get("result"))
        if not result:
            return {}
        zone = _zone(_mapping(result.get("meta")))
        timestamps = result.get("timestamp")
        quote = _first(_mapping(result.get("indicators")).get("quote"))
        closes_raw = quote.get("close")
    except MarketBodyInvalid:
        return {}
    if not isinstance(timestamps, list) or not isinstance(closes_raw, list):
        return {}
    out: dict[dt.date, Ohlc] = {}
    for index, (stamp, raw_close) in enumerate(zip(timestamps, closes_raw, strict=False)):
        instant = _instant(stamp)
        if instant is None or _decimal(raw_close) is None:
            continue
        out[instant.astimezone(zone).date()] = _ohlc_at(quote, index)
    return out
