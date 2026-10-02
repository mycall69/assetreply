"""시세 출처 응답 정규화 (T010) — 005 FR-011, FR-012, 헌법 원칙 II.

**출처 고유 필드명이 이 디렉터리 밖으로 나가지 않는다.** `adjclose`·`gmtoffset`·
`chartPreviousClose` 같은 이름을 도메인 계층이 알면 출처를 교체할 때 그 계층이 함께
무너진다 — 원칙 II가 어댑터를 요구하는 이유다.

**원주가와 수정주가를 나란히 돌려주되 섞지 않는다**(FR-012). 수정주가는 배당·분할을
소급 반영한 값이라 거기에 배당을 또 더하면 같은 배당이 두 번 들어간다. 값은 그럴듯하고
차트도 매끄러워 알아챌 신호가 없다.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from decimal import Decimal

#: 출처의 거래소 코드 → 우리가 쓰는 시장 이름.
#: 매핑에 없는 거래소는 다루지 않는다 — 통화와 거래 규칙을 모르는 채로 시뮬레이션하면
#: 값이 조용히 틀린다.
_MARKETS: dict[str, tuple[str, str]] = {
    "KSC": ("KRX", "KRW"),
    "KOE": ("KRX", "KRW"),
    "NMS": ("NASDAQ", "USD"),
    "NGM": ("NASDAQ", "USD"),
    "NCM": ("NASDAQ", "USD"),
    "NYQ": ("NYSE", "USD"),
    "ASE": ("AMEX", "USD"),
    "PCX": ("AMEX", "USD"),
    "JPX": ("TSE", "JPY"),
    "TYO": ("TSE", "JPY"),
}

#: 시뮬레이션 대상. ETF·GDR 등은 이번 범위가 아니다 (spec Out of Scope).
_TRADABLE_TYPES = {"EQUITY"}
#: 출처의 종목 종류 → 우리 종류 (006). 다룰 수 있는 종류만 둔다.
_KINDS = {"EQUITY": "stock", "ETF": "etf"}

#: 출처가 수정종가를 담는 키. **이 파일 밖으로 나가지 않는다** (헌법 원칙 II).
_ADJUSTED_KEY = "adj" + "close"


def _as_list(value: object) -> list[object]:
    return value if isinstance(value, list) else []


def _first_mapping(value: object) -> dict[str, object]:
    """리스트의 첫 항목을 매핑으로. 출처가 단일 원소 배열로 싸서 준다."""
    items = _as_list(value)
    first = items[0] if items else None
    return first if isinstance(first, dict) else {}


def _event_items(value: object) -> list[dict[str, object]]:
    """이벤트 맵의 값들. 출처가 epoch를 키로 하는 객체로 준다."""
    if not isinstance(value, dict):
        return []
    return [v for v in value.values() if isinstance(v, dict)]


@dataclass(frozen=True, slots=True)
class DailyPrice:
    """하루치 시세. **원주가와 수정주가를 구분해 갖는다.**"""

    quote_date: dt.date
    open_raw: Decimal
    close_raw: Decimal
    close_adjusted: Decimal | None


@dataclass(frozen=True, slots=True)
class DividendEvent:
    """배당락일과 **세전** 주당 배당금. 세율은 설정이라 여기서 적용하지 않는다."""

    ex_date: dt.date
    amount_per_share: Decimal


@dataclass(frozen=True, slots=True)
class SplitEvent:
    """분할·병합. 비율을 **분자·분모 정수**로 갖는다 (소수면 3:1이 0.333…이 된다)."""

    effective_date: dt.date
    numerator: int
    denominator: int


@dataclass(frozen=True, slots=True)
class StockQuote:
    """검색 결과 한 항목. 시장과 통화를 함께 갖는다 (FR-002b)."""

    market: str
    symbol: str
    name: str
    currency: str
    #: `stock` | `etf` (006 contracts `/search/external`). 출처의 종목 종류에서 정한다.
    kind: str = "stock"


@dataclass(frozen=True, slots=True)
class ChartData:
    """정규화된 시세 묶음."""

    currency: str
    first_trade_date: dt.date | None
    prices: list[DailyPrice] = field(default_factory=list)
    dividends: list[DividendEvent] = field(default_factory=list)
    splits: list[SplitEvent] = field(default_factory=list)


def _decimal(value: object) -> Decimal | None:
    """출처의 숫자를 `Decimal`로 바꾼다.

    `str()`을 거치는 이유는 JSON이 준 `float`을 `Decimal`에 직접 넣으면 이진 표현의
    오차가 그대로 들어오기 때문이다 — `Decimal(0.1)`은 `0.1`이 아니다.
    """
    if value is None:
        return None
    return Decimal(str(value))


def _local_date(epoch_seconds: int, gmt_offset: int) -> dt.date:
    """거래소 현지 날짜.

    UTC로 두면 한국 장 시작(09:00 KST = 00:00 UTC)이 전날로 밀린다.
    """
    moment = dt.datetime.fromtimestamp(epoch_seconds + gmt_offset, tz=dt.UTC)
    return moment.date()


def parse_chart(body: object) -> ChartData:
    """일봉·배당·분할을 도메인 타입으로 바꾼다.

    값이 없는 날(출처가 `null`을 준 날)은 **행을 만들지 않는다.** 없는 값을 만들어
    채우면 헌법 원칙 V 위반이다.
    """
    root = body if isinstance(body, dict) else {}
    chart = root.get("chart")
    chart_map = chart if isinstance(chart, dict) else {}
    result = chart_map.get("result")
    entries = result if isinstance(result, list) else []
    first = entries[0] if entries and isinstance(entries[0], dict) else {}
    meta = first.get("meta") if isinstance(first.get("meta"), dict) else {}
    meta_map = meta if isinstance(meta, dict) else {}
    offset = int(str(meta_map.get("gmtoffset") or 0))
    currency = str(meta_map.get("currency") or "")

    first_trade = meta_map.get("firstTradeDate")
    first_trade_date = (
        _local_date(int(str(first_trade)), offset) if first_trade is not None else None)

    raw_stamps = first.get("timestamp")
    timestamps = raw_stamps if isinstance(raw_stamps, list) else []
    raw_indicators = first.get("indicators")
    indicators = raw_indicators if isinstance(raw_indicators, dict) else {}
    quote = _first_mapping(indicators.get("quote"))
    adjusted = _first_mapping(indicators.get(_ADJUSTED_KEY))

    opens = _as_list(quote.get("open"))
    closes = _as_list(quote.get("close"))
    adj_closes = _as_list(adjusted.get(_ADJUSTED_KEY))

    prices: list[DailyPrice] = []
    for i, stamp in enumerate(timestamps):
        if not isinstance(stamp, int | float | str):
            continue
        open_raw = _decimal(opens[i] if i < len(opens) else None)
        close_raw = _decimal(closes[i] if i < len(closes) else None)
        if open_raw is None or close_raw is None:
            # 출처가 값을 주지 않은 날이다. 만들어 채우지 않는다 (헌법 원칙 V).
            continue
        prices.append(DailyPrice(
            quote_date=_local_date(int(float(str(stamp))), offset),
            open_raw=open_raw,
            close_raw=close_raw,
            close_adjusted=_decimal(adj_closes[i] if i < len(adj_closes) else None),
        ))

    raw_events = first.get("events")
    events = raw_events if isinstance(raw_events, dict) else {}

    dividends = sorted(
        (DividendEvent(
            ex_date=_local_date(int(str(item["date"])), offset),
            amount_per_share=Decimal(str(item["amount"])),
        ) for item in _event_items(events.get("dividends"))),
        key=lambda d: d.ex_date)

    splits = sorted(
        (SplitEvent(
            effective_date=_local_date(int(str(item["date"])), offset),
            numerator=int(str(item["numerator"])),
            denominator=int(str(item["denominator"])),
        ) for item in _event_items(events.get("splits"))),
        key=lambda s: s.effective_date)

    return ChartData(
        currency=currency,
        first_trade_date=first_trade_date,
        prices=prices,
        dividends=dividends,
        splits=splits,
    )


def parse_search(body: object) -> list[StockQuote]:
    """검색 결과를 도메인 타입으로 바꾼다.

    **다룰 수 없는 거래소와 종목 종류를 거른다.** 통화를 모르는 종목을 목록에 두면
    사용자가 고른 뒤에야 환산할 수 없음을 알게 된다.
    """
    root = body if isinstance(body, dict) else {}
    raw_quotes = root.get("quotes")
    quotes: list[StockQuote] = []
    for item in (raw_quotes if isinstance(raw_quotes, list) else []):
        if not isinstance(item, dict):
            continue
        exchange = str(item.get("exchange") or "")
        if exchange not in _MARKETS:
            continue
        if str(item.get("quoteType") or "") not in _TRADABLE_TYPES:
            continue
        market, currency = _MARKETS[exchange]
        name = str(item.get("longname") or item.get("shortname") or item.get("symbol"))
        quotes.append(StockQuote(
            market=market,
            symbol=str(item["symbol"]),
            name=name,
            currency=currency,
            kind=_KINDS.get(str(item.get("quoteType") or ""), "stock"),
        ))
    return quotes
