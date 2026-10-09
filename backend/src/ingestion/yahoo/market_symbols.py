"""대시보드 지표 id ↔ Yahoo 심볼 (014 T013) — FR-003, FR-018, research R14-1.

**지표와 출처 심볼의 대응은 이 파일 한 곳에만 있다**(헌법 원칙 II — 011 `installment_items.py`와
같은 격리). 도메인 쪽
(`simulation/market_indicators`)은 심볼을 모른다.

엔은 출처가 **1엔당 원**(`JPYKRW=X` 실측 8.449)으로 준다. 화면·외환 메뉴는 고시 단위인 100엔당이라
100을 곱한다 — `Decimal`
곱셈이라 정확하다(반올림 없음).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Final

SYMBOLS: Final[dict[str, str]] = {
    "kospi": "^KS11",
    "kosdaq": "^KQ11",
    "dow": "^DJI",
    "nasdaq": "^IXIC",
    "sp500": "^GSPC",
    "sox": "^SOX",
    "nikkei225": "^N225",
    "hangseng": "^HSI",
    "shanghai": "000001.SS",
    "usd": "KRW=X",
    "jpy": "JPYKRW=X",
    "eur": "EURKRW=X",
    "wti": "CL=F",
    "gold": "GC=F",
    "vix": "^VIX",
}

_ONE = Decimal(1)
_MULTIPLIERS: Final[dict[str, Decimal]] = {"jpy": Decimal(100)}
_BY_SYMBOL: Final[dict[str, str]] = {symbol: id_ for id_, symbol in SYMBOLS.items()}


def symbol_of(indicator_id: str) -> str:
    """지표의 출처 심볼. 모르는 id면 `KeyError` — 목록 밖 지표를 조용히 부르지 않는다."""
    return SYMBOLS[indicator_id]


def multiplier_of(indicator_id: str) -> Decimal:
    """출처 값에 곱하는 배수(엔 100, 나머지 1)."""
    return _MULTIPLIERS.get(indicator_id, _ONE)


def id_of(symbol: str) -> str | None:
    """출처 심볼의 지표 id. 모르는 심볼이면 `None`."""
    return _BY_SYMBOL.get(symbol)
