"""은행 id ↔ 출처 국가 코드 (014 반복 2026-10-11d T207) — research R14-32.

**은행과 출처 국가 코드(`nationType`)의 대응은 이 파일 한 곳에만 있다**(헌법 원칙 II —
`yahoo/market_symbols.py`와 같은
격리). 도메인 쪽(`simulation/policy_rate`)은 국가 코드를 모른다.
"""

from __future__ import annotations

from typing import Final

NATIONS: Final[dict[str, str]] = {
    "fed": "USA",
    "bok": "KOR",
    "ecb": "EUZ",
    "boe": "GBR",
    "boj": "JPN",
}

_BY_NATION: Final[dict[str, str]] = {nation: bank for bank, nation in NATIONS.items()}


def nation_of(bank_id: str) -> str:
    """은행의 출처 국가 코드. 모르는 은행은 `KeyError`다(은행은 고정 다섯 — spec FR-040)."""
    return NATIONS[bank_id]


def bank_of(nation: str) -> str | None:
    """출처 국가 코드의 은행 id. 다섯 밖이면 `None`(읽지 않는다)."""
    return _BY_NATION.get(nation)
