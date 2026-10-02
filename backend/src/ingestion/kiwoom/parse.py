"""키움 목록 응답 파싱 (T033) — 006 FR-010, FR-012, data-model 1절 검증 규칙, research R6-2.

**출처 필드명은 이 파일에만 둔다**(헌법 원칙 II). 밖으로는 출처와 무관한 `ListingRow`만 나간다.

**가격·상장주식수를 싣지 않는다**(FR-012). 정렬에 가격을 쓰지 않기로 했고, 실으면 시세가 두 출처에서
섞일 자리가 생긴다.

**한 행이라도 이상하면 단위 전체가 실패다.** 한 행을 조용히 버리면 그 종목만 "목록에서 빠짐"이 되고,
처음 보는 `marketName`을 조용히 빼면 출처가 이름을 바꿨을 때 주식 916건이 오류 없이 빠진다 — 그
감소(57%)는 축소 검사(50%)로도 잡히지 않는다.
"""

from __future__ import annotations

import datetime as dt
import json
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

from src.ingestion.kiwoom.errors import KiwoomInvalidResponse

SOURCE_DOMESTIC: Final = "kiwoom:ka10099"

#: 국내 단위 → {marketName: 종류}. 실측(T005, 2026-10-02)에서 본 값만 둔다.
_KEEP: Final[dict[str, dict[str, str]]] = {
    "KOSPI": {"거래소": "stock", "ETF": "etf", "리츠": "reit"},
    "KOSDAQ": {"코스닥": "stock"},
}
#: 범위 밖이라 남기지 않는 marketName — ETN 세 종류(Clarifications Q1), 인프라투자금융·뮤추얼펀드.
_SKIP: Final = frozenset({"ETN", "ETN(변동성)", "ETN(손실제한)", "인프라투자금융", "뮤추얼펀드"})
_KR_CODE_LENGTH: Final = 6


@dataclass(frozen=True, slots=True)
class ListingRow:
    """검색용 종목 한 행. 출처와 무관한 모양이다."""

    country: str
    code: str
    unit: str
    name_ko: str | None
    name_en: str | None
    kind: str
    listed_on: dt.date | None


def _rows_of(body: str) -> list[object]:
    try:
        parsed: object = json.loads(body)
    except ValueError as exc:
        raise KiwoomInvalidResponse("목록 응답이 JSON이 아닙니다.") from exc
    rows = parsed.get("list") if isinstance(parsed, dict) else None
    if not isinstance(rows, list):
        raise KiwoomInvalidResponse("목록 응답에 종목 목록이 없습니다.")
    return rows


def _text(value: object) -> str | None:
    text = value.strip() if isinstance(value, str) else ""
    return text or None


def _date(value: object) -> dt.date | None:
    """`YYYYMMDD`. 읽을 수 없으면 `None` — 상장일은 하한일 뿐이라 지어내지 않는다(원칙 V)."""
    if not isinstance(value, str) or len(value.strip()) != 8:
        return None
    try:
        return dt.datetime.strptime(value.strip(), "%Y%m%d").date()
    except ValueError:
        return None


def parse_domestic(unit: str, bodies: Sequence[str]) -> list[ListingRow]:
    """국내 목록(`ka10099`)의 모든 쪽을 한 단위의 종목으로."""
    keep = _KEEP.get(unit)
    if keep is None:
        raise ValueError(f"국내 목록 단위가 아닙니다: {unit}")

    rows: list[ListingRow] = []
    seen: set[str] = set()
    for body in bodies:
        for raw in _rows_of(body):
            if not isinstance(raw, dict):
                raise KiwoomInvalidResponse(f"{unit} 목록에 형식이 다른 행이 있습니다.")
            market_name = _text(raw.get("marketName")) or ""
            if market_name in _SKIP:
                continue
            kind = keep.get(market_name)
            if kind is None:
                raise KiwoomInvalidResponse(
                    f"{unit} 목록에 처음 보는 시장 구분이 있습니다: {market_name!r}")
            code = _text(raw.get("code")) or ""
            if len(code) != _KR_CODE_LENGTH:
                raise KiwoomInvalidResponse(
                    f"{unit} 목록에 6자리가 아닌 종목코드가 있습니다: {code!r}")
            if code in seen:
                raise KiwoomInvalidResponse(f"{unit} 목록에 같은 종목코드가 두 번 있습니다: {code}")
            seen.add(code)
            rows.append(ListingRow(
                country="KR", code=code, unit=unit, name_ko=_text(raw.get("name")),
                name_en=None, kind=kind, listed_on=_date(raw.get("regDay"))))
    return rows


def parse_listing(unit: str, bodies: Sequence[str]) -> list[ListingRow]:
    """단위에 맞는 파서를 고른다."""
    if unit in _KEEP:
        return parse_domestic(unit, bodies)
    raise ValueError(f"파서가 없는 목록 단위입니다: {unit}")


def source_of(unit: str) -> str:
    """`stock_listing.source`에 남길 출처 이름."""
    if unit in _KEEP:
        return SOURCE_DOMESTIC
    raise ValueError(f"출처 이름이 없는 목록 단위입니다: {unit}")
