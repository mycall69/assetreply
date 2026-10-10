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
from collections.abc import Iterable
from dataclasses import dataclass, field, replace
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from fractions import Fraction
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from src.ingestion.yahoo.errors import StockSourceUnavailable

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
    """정규화된 시세 묶음. 시가·종가·배당은 `restore_unadjusted`를 거친 뒤에 원주가다."""

    currency: str
    first_trade_date: dt.date | None
    prices: list[DailyPrice] = field(default_factory=list)
    dividends: list[DividendEvent] = field(default_factory=list)
    splits: list[SplitEvent] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class RawBody:
    """출처가 보낸 본문 하나. 받은 그대로 보관한다 (헌법 시계열 불변식)."""

    #: `chart`(일봉 청크) · `splits`(원주가를 되살리는 데 쓴 분할 기록)
    kind: str
    body: str
    status: int
    requested_from: dt.date
    requested_to: dt.date


@dataclass(frozen=True, slots=True)
class ChartFetch:
    """청크 한 번의 결과 — 정규화한 시세와, 그것을 만드는 데 쓴 **원본 전부**(006 FR-034)."""

    data: ChartData
    raws: list[RawBody]


def _decimal(value: object) -> Decimal | None:
    """출처의 숫자를 `Decimal`로 바꾼다.

    `str()`을 거치는 이유는 JSON이 준 `float`을 `Decimal`에 직접 넣으면 이진 표현의
    오차가 그대로 들어오기 때문이다 — `Decimal(0.1)`은 `0.1`이 아니다.
    """
    if value is None:
        return None
    return Decimal(str(value))


#: 분할 비율을 담는 열(`stock_split.numerator`·`denominator`, `INT`)의 최댓값.
_RATIO_MAX = 2_147_483_647


def _ratio_part(value: object) -> Fraction:
    """분할 비율의 한쪽을 정확한 유리수로 읽는다. 양의 유한한 수가 아니면 거절한다.

    **실제 응답은 실수로 준다**(`5.0`, 006 T090에서 발견). `str()`을 거쳐 `Decimal`로 읽으므로
    JSON이 준 자릿수 그대로다 — 이진 부동소수의 오차가 들어오지 않는다.
    """
    try:
        number = Decimal(str(value))
    except InvalidOperation:
        number = Decimal("NaN")
    if not number.is_finite() or number <= 0:
        raise StockSourceUnavailable("시세 출처의 응답이 유효하지 않습니다.")
    return Fraction(number)


def _split_ratio(numerator: object, denominator: object) -> tuple[int, int]:
    """분할 비율을 **기약 정수 쌍**으로 — `5.0:1.0` → `5:1`, `0.985:1` → `197:200`.

    출처는 정수가 아닌 비율도 준다(삼성물산 2020-05-13 `0.985:1`, 버그 `fractional-split-ratio`).
    006 T103은 정수만 받아 그 날짜를 포함한 수집이 매번 실패했다. **반올림하지 않는다** — `2.5`를
    2나 3으로 바꾸면 보유 수량이 조용히 틀린다(헌법 원칙 V·VI). 정확한 분수로 다루면 반올림이
    필요 없다. 저장 열을 넘는 분수는 줄이지 않고 거절한다.
    """
    ratio = _ratio_part(numerator) / _ratio_part(denominator)
    if ratio.numerator > _RATIO_MAX or ratio.denominator > _RATIO_MAX:
        raise StockSourceUnavailable("시세 출처의 응답이 유효하지 않습니다.")
    return ratio.numerator, ratio.denominator


def _local_date(epoch_seconds: int, gmt_offset: int) -> dt.date:
    """거래소 현지 날짜.

    UTC로 두면 한국 장 시작(09:00 KST = 00:00 UTC)이 전날로 밀린다.
    """
    moment = dt.datetime.fromtimestamp(epoch_seconds + gmt_offset, tz=dt.UTC)
    return moment.date()


def _first_result(body: object) -> tuple[dict[str, object], dict[str, object], int]:
    """응답의 첫 결과, 그 메타, 거래소 시간대 오프셋(초)."""
    root = body if isinstance(body, dict) else {}
    chart = root.get("chart")
    chart_map = chart if isinstance(chart, dict) else {}
    result = chart_map.get("result")
    entries = result if isinstance(result, list) else []
    first = entries[0] if entries and isinstance(entries[0], dict) else {}
    meta = first.get("meta")
    meta_map = meta if isinstance(meta, dict) else {}
    offset = int(str(meta_map.get("gmtoffset") or 0))
    return first, meta_map, offset


def _split_events(first: dict[str, object], offset: int) -> list[SplitEvent]:
    """결과의 분할 이벤트. 키는 봉의 시각이라(월봉이면 월 시작) **`date`를 읽는다**."""
    raw_events = first.get("events")
    events = raw_events if isinstance(raw_events, dict) else {}
    splits: list[SplitEvent] = []
    for item in _event_items(events.get("splits")):
        numerator, denominator = _split_ratio(item["numerator"], item["denominator"])
        splits.append(SplitEvent(
            effective_date=_local_date(int(str(item["date"])), offset),
            numerator=numerator,
            denominator=denominator,
        ))
    return sorted(splits, key=lambda s: s.effective_date)


def _first_trade_date(meta_map: dict[str, object], offset: int) -> dt.date | None:
    """출처가 시세를 가진 첫 날 — **거래소 시간대**의 날짜 (014 반복 2026-10-10f — FR-033, R14-26).

    응답 시점의 고정 오프셋(`gmtoffset`)으로 바꾸면 출처가 현지 자정을 줄 때 서머타임 차이로 하루
    어긋난다(014 R14-3). 시간대 이름이 없거나 모르는 이름이면 그 오프셋으로 물러난다. 출처가 주지
    않으면 `None`이다 — 지어내지 않는다(헌법 원칙 V).
    """
    raw = meta_map.get("firstTradeDate")
    if raw is None:
        return None
    epoch = int(str(raw))
    zone = meta_map.get("exchangeTimezoneName")
    if isinstance(zone, str) and zone:
        try:
            return dt.datetime.fromtimestamp(epoch, ZoneInfo(zone)).date()
        except (ZoneInfoNotFoundError, ValueError):
            pass
    return _local_date(epoch, offset)


def parse_first_trade(body: object) -> dt.date | None:
    """차트 응답의 `meta.firstTradeDate`만 읽는다 — 봉·배당·분할은 보지 않는다(014 FR-033)."""
    _, meta_map, offset = _first_result(body)
    return _first_trade_date(meta_map, offset)


def parse_splits(body: object) -> list[SplitEvent]:
    """분할 기록 응답(월봉, `events=splits`)에서 분할만 읽는다 (006 FR-034).

    봉은 읽지 않는다 — 월봉 값은 계산에 쓰지 않는다. 결과가 없으면(구간에 시세 없음) 빈 목록이다.
    """
    first, _, offset = _first_result(body)
    return _split_events(first, offset)


def parse_chart(body: object) -> ChartData:
    """일봉·배당·분할을 도메인 타입으로 바꾼다.

    값이 없는 날(출처가 `null`을 준 날)은 **행을 만들지 않는다.** 없는 값을 만들어
    채우면 헌법 원칙 V 위반이다.

    **돌려주는 시가·종가·배당은 출처가 분할을 소급 반영한 값이다**(006 T090 결함 5). 원주가로 쓰려면
    그 뒤의 분할 기록과 함께 `restore_unadjusted`를 거쳐야 한다 — 클라이언트가 한다.
    """
    first, meta_map, offset = _first_result(body)
    currency = str(meta_map.get("currency") or "")

    first_trade_date = _first_trade_date(meta_map, offset)

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

    return ChartData(
        currency=currency,
        first_trade_date=first_trade_date,
        prices=prices,
        dividends=dividends,
        splits=_split_events(first, offset),
    )


#: 되살린 값의 자릿수. 저장 열(`stock_price`·`stock_dividend`, 소수 6자리)과 같다. 병합(1:3)은
#: 나눗셈이라 맞추지 않으면 끝나지 않는다.
_RESTORED_PLACES = Decimal("0.000001")


def restore_unadjusted(chart: ChartData, later_splits: Iterable[SplitEvent]) -> ChartData:
    """출처가 분할을 소급 반영한 시가·종가·배당을 **원주가·원 배당으로 되살린다** (006 FR-034).

    날짜 d의 원주가 = 반영가 × (d **이후**에 적용된 분할·병합의 분자 곱 ÷ 분모 곱). 분할 날의 시세는
    이미 분할 뒤 값이라 곱하지 않는다 — 배당도 같다(분할 날의 배당은 분할 뒤 주식에 붙는다).

    `later_splits`는 청크 시작일부터 지금까지의 분할 기록이다. 청크 안의 분할과 같은 날이면
    비율이 같아야 한다 — 어긋나면 어느 쪽으로 되살려도 틀릴 수 있어 거절한다.

    수정종가는 되살리지 않는다. 계산에 쓰지 않으며(005 FR-011) 되살리면 그 열의 뜻이 바뀐다.
    곱할 것이 없는 값은 건드리지 않는다.
    """
    ratios: dict[dt.date, tuple[int, int]] = {}
    for split in [*chart.splits, *later_splits]:
        ratio = (split.numerator, split.denominator)
        known = ratios.setdefault(split.effective_date, ratio)
        if known != ratio:
            raise StockSourceUnavailable("시세 출처의 응답이 유효하지 않습니다.")

    def restore(value: Decimal, day: dt.date) -> Decimal:
        numerator = denominator = 1
        for effective, (num, den) in ratios.items():
            if effective > day:
                numerator *= num
                denominator *= den
        if numerator == denominator:
            return value
        return (value * numerator / denominator).quantize(_RESTORED_PLACES, ROUND_HALF_UP)

    return replace(
        chart,
        prices=[replace(p, open_raw=restore(p.open_raw, p.quote_date),
                        close_raw=restore(p.close_raw, p.quote_date))
                for p in chart.prices],
        dividends=[replace(d, amount_per_share=restore(d.amount_per_share, d.ex_date))
                   for d in chart.dividends],
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
