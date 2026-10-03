"""가상자산 출처 응답 파싱 (007 FR-006, FR-012, FR-012a, FR-021, FR-022, research R7-3·R7-4).

**화면용 문자열을 쓰지 않는다.** `last_open` 같은 값은 코인의 자릿수로 반올림되어 SHIB의 시가가
`0.0`이 된다. 원값 (`…Raw`)을 `float`을 거치지 않고 `Decimal`로 읽는다 — JSON 숫자도
`parse_float=Decimal`로 읽는다(헌법 원칙 VI).

**가격을 읽지 못한 행이 하나라도 있으면 청크 전체가 형식 오류다**(analyze M2). 그 행만 버리면 그날이
출처 결측으로 표시되고, 출처가 형식을 바꾼 사실이 드러나지 않는다.
"""

from __future__ import annotations

import datetime as dt
import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from src.ingestion.investing.errors import InvestingFormatError

#: 출처는 한 요청에서 약 5,000행(오래된 쪽부터)에서 **표시 없이** 자른다(research R7-3). 청크는
#: 730일이라 닿지 않는다 — 닿았다면 구간 일부를 받은 것으로 기록하게 되므로 형식 오류로 다룬다.
ROW_LIMIT_GUARD = 4_900

#: 시가·고가·저가·종가 순서.
_PRICE_FIELDS = ("last_openRaw", "last_maxRaw", "last_minRaw", "last_closeRaw")


@dataclass(frozen=True, slots=True)
class CoinRow:
    """목록의 코인 한 줄. **식별자는 `source_id`다** — 심볼은 유일하지 않다(FR-004, research
    R7-4)."""

    source_id: str
    symbol: str
    name: str
    rank: int | None
    slug: str | None


@dataclass(frozen=True, slots=True)
class CoinPage:
    coins: list[CoinRow]
    #: 다음 쪽 커서. 마지막 쪽이면 `None`.
    next_cursor: str | None


@dataclass(frozen=True, slots=True)
class DailyBar:
    """UTC 하루의 일봉. 거래량은 출처가 빈 값으로 준 날 `None`이다 — 0이 아니다(FR-012a)."""

    day: dt.date
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal | None


def _load(body: str, what: str) -> object:
    try:
        return json.loads(body, parse_float=Decimal)
    except ValueError as exc:
        raise InvestingFormatError(f"{what} 응답이 JSON이 아닙니다.") from exc


def _text(row: Mapping[str, object], key: str) -> str | None:
    value = row.get(key)
    return value.strip() or None if isinstance(value, str) else None


def _coin(item: object) -> CoinRow:
    if not isinstance(item, dict):
        raise InvestingFormatError("코인 목록의 행이 객체가 아닙니다.")
    instrument = item.get("instrument_id")
    # bool은 int의 하위형이다 — 식별자로 받지 않는다
    if isinstance(instrument, bool) or not isinstance(instrument, int | str) or not str(instrument):
        raise InvestingFormatError("코인 목록의 행에 instrument_id가 없습니다.")
    symbol, name = _text(item, "symbol"), _text(item, "name")
    if symbol is None or name is None:
        raise InvestingFormatError(f"코인 {instrument}에 심볼이나 이름이 없습니다.")
    rank = item.get("rank")
    return CoinRow(
        source_id=str(instrument), symbol=symbol, name=name,
        rank=rank if isinstance(rank, int) and not isinstance(rank, bool) else None,
        slug=_text(item, "slug"))


def parse_coin_page(body: str) -> CoinPage:
    """코인 목록 한 쪽을 읽는다. 모양이 다르면 형식 오류다 — 빈 목록으로 교체하지 않는다."""
    doc = _load(body, "코인 목록")
    if not isinstance(doc, dict) or not isinstance(doc.get("coins"), list):
        raise InvestingFormatError("코인 목록 응답에 coins 배열이 없습니다.")
    cursor = doc.get("next_page_cursor")
    return CoinPage(
        coins=[_coin(item) for item in doc["coins"]],
        next_cursor=cursor if isinstance(cursor, str) and cursor else None)


def _has_hangul(text: str) -> bool:
    return any("가" <= ch <= "힣" or "ㄱ" <= ch <= "ㆎ" for ch in text)


def korean_names(english: Iterable[CoinRow], korean: Iterable[CoinRow]) -> dict[str, str]:
    """한국어 판에서 한글 이름을 뽑는다(FR-006). **식별자로만 짝짓는다** — 이름·심볼로 짝지으면 같은
    심볼의 다른 코인과 섞인다(FR-004).

    한국어 판도 대부분 영문 이름 그대로다(BNB·XRP). 영문과 다르고 한글을 담은 이름만 한글 이름이다 —
    그렇지 않으면 영문 이름이 한글 이름 자리에 들어가 검색 순위가 두 번 매겨진다.
    """
    by_id = {c.source_id: c.name for c in english}
    return {
        c.source_id: c.name for c in korean
        if c.source_id in by_id and c.name != by_id[c.source_id] and _has_hangul(c.name)}


def _day(row: Mapping[str, object]) -> dt.date:
    stamp = row.get("rowDateTimestamp")
    if not isinstance(stamp, str):
        raise InvestingFormatError("일봉 행에 rowDateTimestamp가 없습니다.")
    try:
        moment = dt.datetime.fromisoformat(stamp)
    except ValueError as exc:
        raise InvestingFormatError(f"일봉 날짜를 읽지 못했습니다: {stamp[:32]!r}") from exc
    # 일봉 기준 시각은 UTC 00:00이다(헌법 원칙 V). 다른 시각이면 날짜를 하루 밀어 읽게 된다
    if moment.utcoffset() != dt.timedelta(0) or moment.time() != dt.time(0):
        raise InvestingFormatError(f"일봉 기준 시각이 UTC 00:00이 아닙니다: {stamp[:32]!r}")
    return moment.date()


def _price(row: Mapping[str, object], field: str, day: dt.date) -> Decimal:
    raw = row.get(field)
    try:
        if isinstance(raw, bool) or not isinstance(raw, str | int | Decimal):
            raise InvalidOperation
        value = Decimal(raw)
    except InvalidOperation as exc:
        raise InvestingFormatError(f"{day} 일봉의 {field}를 읽지 못했습니다.") from exc
    if not value.is_finite() or value < 0:
        raise InvestingFormatError(f"{day} 일봉의 {field}가 유효한 가격이 아닙니다.")
    return value


def _volume(row: Mapping[str, object]) -> Decimal | None:
    """출처는 거래량이 없는 날을 `volume: ""`·`volumeRaw: 0`으로 준다 — 0으로 저장하면 거래가 없던
    날이 된다."""
    if row.get("volume") in ("", None):
        return None
    raw = row.get("volumeRaw")
    if isinstance(raw, bool) or not isinstance(raw, str | int | Decimal):
        return None
    try:
        value = Decimal(raw)
    except InvalidOperation:
        return None
    return value if value.is_finite() and value >= 0 else None


def parse_daily(body: str, *, last_day: dt.date) -> list[DailyBar]:
    """일봉 응답을 날짜 오름차순으로 읽는다.

    `last_day`(계산 끝, UTC 어제)보다 뒤의 행은 버린다 — 출처는 마감 전인 UTC 오늘의 일봉도
    준다(FR-022). 일봉이 없는 코인은 `"data": null`로 온다(research R7-3) — 빈 목록이다.
    """
    doc = _load(body, "일봉")
    if not isinstance(doc, dict) or "data" not in doc:
        raise InvestingFormatError("일봉 응답에 data가 없습니다.")
    rows = doc["data"]
    if rows is None:
        return []
    if not isinstance(rows, list):
        raise InvestingFormatError("일봉 응답의 data가 배열이 아닙니다.")
    if len(rows) >= ROW_LIMIT_GUARD:
        raise InvestingFormatError(
            f"일봉 응답이 {len(rows)}행입니다 — 출처의 행 상한에서 잘렸을 수 있습니다.")

    bars: dict[dt.date, DailyBar] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise InvestingFormatError("일봉 행이 객체가 아닙니다.")
        day = _day(row)
        if day in bars:
            raise InvestingFormatError(f"{day} 일봉이 두 번 왔습니다.")
        open_, high, low, close = (_price(row, field, day) for field in _PRICE_FIELDS)
        bars[day] = DailyBar(
            day=day, open=open_, high=high, low=low, close=close, volume=_volume(row))
    return [bars[d] for d in sorted(bars) if d <= last_day]
