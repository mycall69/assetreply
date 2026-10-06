"""정기적금 금리 계열 ↔ ECOS 통계표·항목 (011 T046, FR-029, research R11-1·R11-2).

**계열 키 ↔ 출처 항목의 대응은 이 파일에만 있다**(헌법 원칙 II). 도메인은 계열 키만 안다 —
(투자처, 상품) → 계열 키의 대응은 예금 서비스에 있다.

항목(2026-10-06 실측):
- `commercial_bank_isav` — 시중은행. 121Y002 예금은행 수신금리(신규취급액)의 `BEABAA2122`
  정기적금(1-2년), 2003-01~
- `mutual_finance_isav` — 상호금융. 121Y004 비은행금융기관 수신금리(신규취급액)의 `BEBB0200`
  정기적금(만기 구분 없음), 2012-01~

- 시중은행에는 정확히 1년인 적금 항목이 없다. 1년을 담는 가장 좁은 만기 구간이 `1-2년`이다 —
  전체(`정기적금`)는 3~4년이 섞인다
- 상호금융의 하위는 `정기적금(3년만기)`뿐이라 만기 구분 없는 전체를 쓴다. 패턴은 **정확히
  일치**해야 한다 — 하위가 걸리면 3년 상품의 금리로 계산된다
- 저축은행·신협·새마을금고는 출처에 적금 항목이 없다 — 계열이 없다(정기예금 금리로 대신하지
  않는다)

008의 투자처 항목(`deposit_items`)과 같은 규칙으로 찾는다 — 알려진 코드 + 이름 패턴이고, 못 찾으면
멈춘다(약관 제9조 ⑤ — 출처는 계속적 제공을 보장하지 않는다).
"""

from __future__ import annotations

import re
from typing import Final

from src.ingestion.ecos.deposit_items import (
    BANK_TABLE,
    NON_BANK_TABLE,
    DepositItem,
    monthly_items,
    pick_item,
)
from src.ingestion.ecos.errors import ItemMappingChanged

INSTALLMENT_SERIES: Final = ("commercial_bank_isav", "mutual_finance_isav")

SERIES_TABLE: Final[dict[str, str]] = {
    "commercial_bank_isav": BANK_TABLE,
    "mutual_finance_isav": NON_BANK_TABLE,
}

KNOWN_CODES: Final[dict[str, str]] = {
    "commercial_bank_isav": "BEABAA2122",
    "mutual_finance_isav": "BEBB0200",
}

NAME_PATTERNS: Final[dict[str, re.Pattern[str]]] = {
    "commercial_bank_isav": re.compile(r"^정기적금\(1-2년\)$"),
    "mutual_finance_isav": re.compile(r"^정기적금$"),
}


def resolve_installment_items(body: str, table: str) -> dict[str, DepositItem]:
    """항목 목록에서 그 통계표에 속한 적금 계열의 항목을 확정한다. 계열이 없는 통계표면 멈춘다."""
    wanted = [key for key in INSTALLMENT_SERIES if SERIES_TABLE[key] == table]
    if not wanted:
        raise ItemMappingChanged(f"정기적금 계열이 없는 통계표입니다: {table}")
    monthly = monthly_items(body)
    return {key: pick_item(monthly, key, table, KNOWN_CODES[key], NAME_PATTERNS[key])
            for key in wanted}
