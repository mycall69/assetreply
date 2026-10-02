"""목록 종목 ↔ 005 시세 식별자 (T032) — 006 FR-010a, FR-030, FR-031, research R6-6.

**시장을 틀리면** 시세 출처가 그 종목을 찾지 못해 "시세 없음"이 되고, 사용자는 그 종목에 데이터가
없다고 읽는다. ETF·리츠는 목록에서 상품 구분이 다르지만 유가증권시장에서 거래되므로 `.KS`다 —
이 함수는 상품 구분을 받지 않는다(FR-010a).

**정방향과 역방향은 왕복해야 한다.** 목록 → 시세 식별자 → 목록이 같은 종목이 아니면, 검색에서 고른
종목은 되는데 같은 종목의 이력 재실행만 "알 수 없는 종목"이 된다(SC-007a).
"""

from __future__ import annotations

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


def to_price_symbol(unit: str, code: str) -> PriceSymbol:
    """목록 종목의 시세 식별자. 모르는 단위는 거절한다 — 조용히 다른 시장으로 옮기지 않는다."""
    suffix = _KR_SUFFIX.get(unit)
    if suffix is not None:
        return PriceSymbol("KRX", f"{code}{suffix}", "KRW")
    raise ValueError(f"시세 식별자 규칙이 없는 목록 단위입니다: {unit}")


def listing_candidates(market: str, symbol: str) -> ListingKey | None:
    """시세 식별자에서 목록 종목을 찾을 후보. 목록이 없는 시장이면 `None`."""
    if market == "KRX":
        for suffix in _KR_SUFFIX.values():
            if symbol.endswith(suffix) and len(symbol) > len(suffix):
                return ListingKey("KR", (symbol[: -len(suffix)],))
    return None
