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
from decimal import Decimal
from typing import Final

from src.ingestion.yahoo.errors import StockSourceUnavailable
from src.simulation.market_quote import SourceQuote

_PLACES: Final = Decimal("0.000001")


class MarketBodyInvalid(StockSourceUnavailable):
    """응답 본문을 읽을 수 없다(구조가 바뀌었거나 값이 깨졌다) — 실패 종류 `invalid_body`."""


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
