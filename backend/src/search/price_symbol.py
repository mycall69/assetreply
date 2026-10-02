"""목록 종목 ↔ 005 시세 식별자 (T032) — 006 FR-010a, FR-030, FR-031, research R6-6.

**시장을 틀리면** 시세 출처가 그 종목을 찾지 못해 "시세 없음"이 되고, 사용자는 그 종목에 데이터가
없다고 읽는다. ETF·리츠는 목록에서 상품 구분이 다르지만 유가증권시장에서 거래되므로 `.KS`다 —
이 함수는 상품 구분을 받지 않는다(FR-010a).

**정방향과 역방향은 왕복해야 한다.** 목록 → 시세 식별자 → 목록이 같은 종목이 아니면, 검색에서 고른
종목은 되는데 같은 종목의 이력 재실행만 "알 수 없는 종목"이 된다(SC-007a).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True, slots=True)
class PriceSymbol:
    """005의 시세 식별자. 이력과 시뮬레이션이 이것을 쓴다."""

    market: str
    symbol: str
    currency: str


@dataclass(frozen=True, slots=True)
class ListingKey:
    """시세 식별자에서 거꾸로 찾을 목록 종목. `codes`는 앞의 것부터 찾는 후보다."""

    country: str
    codes: tuple[str, ...]


#: 국내 단위 → 시세 출처의 접미사.
_KR_SUFFIX: Final = {"KOSPI": ".KS", "KOSDAQ": ".KQ"}
#: 미국 단위. 005의 시장 이름과 같다 — 거래소가 곧 시장이다.
US_MARKETS: Final = frozenset({"NYSE", "NASDAQ", "AMEX"})

# 목록 출처의 티커 표기 다섯 갈래 (research R6-6, T005 실측 + 시세 출처 확인 2026-10-02).
#: `BASE.SUF` — 클래스·유닛 (`BH.A` → `BH-A`, `AAC.UN` → `AAC-UN`)
_DOT = re.compile(r"^([A-Z0-9]+)\.([A-Z0-9]+)$")
#: `BASE` + 소문자 — 클래스 (`BRKb` → `BRK-B`)
_LOWER = re.compile(r"^([A-Z0-9]+)([a-z]+)$")
#: `BASE-SER` — 우선주 시리즈, 시리즈가 빌 수 있다 (`ABR-D` → `ABR-PD`, `PHXE-` → `PHXE-P`)
_DASH = re.compile(r"^([A-Z0-9]+)-([A-Z]*)$")
#: `BASE_p` + 소문자 — 우선주 시리즈 (`BAC_pe` → `BAC-PE`)
_UNDERSCORE_P = re.compile(r"^([A-Z0-9]+)_p([a-z]*)$")
#: 시세 출처 표기 `BASE-SUF`
_YAHOO_DASH = re.compile(r"^([A-Z0-9]+)-([A-Z0-9]+)$")


def us_ticker(code: str) -> str:
    """목록 출처의 미국 티커를 시세 출처 표기로. 표에 없는 기호는 그대로 보낸다 — 시세 출처가
    모르면 "시세 출처에서 찾지 못함"으로 알린다(FR-032)."""
    if m := _DOT.match(code):
        return f"{m.group(1)}-{m.group(2)}"
    if m := _LOWER.match(code):
        return f"{m.group(1)}-{m.group(2).upper()}"
    if m := _DASH.match(code):
        return f"{m.group(1)}-P{m.group(2)}"
    if m := _UNDERSCORE_P.match(code):
        return f"{m.group(1)}-P{m.group(2).upper()}"
    return code


def _us_candidates(symbol: str) -> tuple[str, ...]:
    """정방향 표의 역으로 만든 후보. 목록에 있는 **첫 것**을 쓴다(research R6-6 역변환)."""
    m = _YAHOO_DASH.match(symbol)
    if m is None:
        return (symbol,)
    base, suffix = m.group(1), m.group(2)
    candidates: list[str] = []
    if suffix.startswith("P"):
        series = suffix[1:]
        candidates += [f"{base}-{series}", f"{base}_p{series.lower()}"]
    candidates += [f"{base}.{suffix}", f"{base}{suffix.lower()}", symbol]
    return tuple(dict.fromkeys(candidates))


def to_price_symbol(unit: str, code: str) -> PriceSymbol:
    """목록 종목의 시세 식별자. 모르는 단위는 거절한다 — 조용히 다른 시장으로 옮기지 않는다."""
    suffix = _KR_SUFFIX.get(unit)
    if suffix is not None:
        return PriceSymbol("KRX", f"{code}{suffix}", "KRW")
    if unit in US_MARKETS:
        return PriceSymbol(unit, us_ticker(code), "USD")
    raise ValueError(f"시세 식별자 규칙이 없는 목록 단위입니다: {unit}")


def listing_candidates(market: str, symbol: str) -> ListingKey | None:
    """시세 식별자에서 목록 종목을 찾을 후보. 목록이 없는 시장이면 `None`.

    미국은 **거래소를 보지 않는다**(FR-030a) — 같은 티커면 거래소가 달라도 같은 종목이다.
    """
    if market == "KRX":
        for suffix in _KR_SUFFIX.values():
            if symbol.endswith(suffix) and len(symbol) > len(suffix):
                return ListingKey("KR", (symbol[: -len(suffix)],))
    if market in US_MARKETS:
        return ListingKey("US", _us_candidates(symbol))
    return None
