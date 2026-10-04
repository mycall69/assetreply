"""예금 투자처 ↔ ECOS 통계표·항목 (008 T009, FR-008, research R8-1).

**투자처 ↔ 출처 항목의 대응은 이 파일에만 있다**(헌법 원칙 II). 도메인은 투자처 키만 안다.

| 투자처 | 통계표 | 항목(2026-10-04 실측) |
|--------|--------|----------------------|
| 시중은행 | 121Y002 예금은행 수신금리(신규취급액) | `BEABAA2118` 정기예금(1년) — 2012-01~ |
| 저축은행 | 121Y004 비은행금융기관 수신금리(신규취급액) | `BEBBBE01` 상호저축은행-정기예금(1년) |
| 신협 | 121Y004 | `BEBBBG01` 신협-정기예탁금(1년) |
| 상호금융 | 121Y004 | `BEBBBI01` 정기예탁금(1년만기) — 이름에 기관명이 없다 |
| 새마을금고 | 121Y004 | `BEBBA000` 새마을금고-정기예탁금(1년) |

항목 코드가 바뀌어도 **이름 패턴으로 다시 찾는다** — 출처는 계속적 제공을 보장하지 않는다(약관 제9조
⑤). 다시 찾지 못하면 멈춘다 — 다른 항목의 금리를 저장하는 것보다 낫다. 상호금융의 패턴은 정확히
일치해야 한다 — 상위 항목 "정기예탁금"(만기 구분 없음)이 걸리면 1년 상품이 아닌 금리로 계산된다.
"""

from __future__ import annotations

import datetime as dt
import json
import re
from dataclasses import dataclass
from typing import Final

from src.ingestion.ecos.deposit_parse import fail_for
from src.ingestion.ecos.errors import ItemMappingChanged, SourceUnavailable

# 화면 순서다(FR-003). 기본 선택은 첫째.
INSTITUTIONS: Final = (
    "commercial_bank", "savings_bank", "credit_union", "mutual_finance", "saemaul")

BANK_TABLE: Final = "121Y002"
NON_BANK_TABLE: Final = "121Y004"

TABLE_OF: Final[dict[str, str]] = {
    "commercial_bank": BANK_TABLE,
    "savings_bank": NON_BANK_TABLE,
    "credit_union": NON_BANK_TABLE,
    "mutual_finance": NON_BANK_TABLE,
    "saemaul": NON_BANK_TABLE,
}

# 알려진 항목 코드 — 이름이 맞으면 이 코드를 먼저 쓴다.
KNOWN_CODES: Final[dict[str, str]] = {
    "commercial_bank": "BEABAA2118",
    "savings_bank": "BEBBBE01",
    "credit_union": "BEBBBG01",
    "mutual_finance": "BEBBBI01",
    "saemaul": "BEBBA000",
}

NAME_PATTERNS: Final[dict[str, re.Pattern[str]]] = {
    "commercial_bank": re.compile(r"^정기예금\(1년\)$"),
    "savings_bank": re.compile(r"상호저축은행.*정기예금\(1년\)"),
    "credit_union": re.compile(r"신협.*정기예탁금\(1년\)"),
    "mutual_finance": re.compile(r"^정기예탁금\(1년만기\)$"),
    "saemaul": re.compile(r"새마을금고.*정기예탁금\(1년\)"),
}

_MONTHLY: Final = "M"


@dataclass(frozen=True, slots=True)
class DepositItem:
    """투자처 하나의 월 시계열 손잡이. 상위 계층은 `institution`·`source_ref`·`start_month`만
    쓴다."""

    institution: str
    table: str
    item_code: str
    item_name: str
    start_month: dt.date

    @property
    def source_ref(self) -> str:
        """원본에 남기는 불투명한 참조 — 저장소는 해석하지 않는다(data-model 2절)."""
        return f"{self.table}/{self.item_code}"


def _month(raw: str) -> dt.date | None:
    if len(raw) != 6 or not raw.isdigit():
        return None
    year, month = int(raw[:4]), int(raw[4:])
    return dt.date(year, month, 1) if 1 <= month <= 12 else None


def resolve_deposit_items(body: str, table: str) -> dict[str, DepositItem]:
    """항목 목록에서 그 통계표에 속한 투자처들의 항목을 확정한다.

    1. 알려진 코드의 월 항목이 이름 패턴과 맞으면 그것을 쓴다
    2. 아니면 이름 패턴으로 월 항목을 다시 찾는다
    3. 찾지 못하면 `ItemMappingChanged`(형식 오류)로 멈춘다
    """
    wanted = [inst for inst in INSTITUTIONS if TABLE_OF[inst] == table]
    if not wanted:
        raise ItemMappingChanged(f"예금 투자처가 없는 통계표입니다: {table}")

    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        raise SourceUnavailable(f"항목 목록 응답이 JSON이 아닙니다: {body[:200]}") from exc
    if not isinstance(payload, dict):
        raise SourceUnavailable(f"예상하지 못한 항목 목록 응답: {body[:200]}")
    result = payload.get("RESULT")
    if isinstance(result, dict):
        raise fail_for(str(result.get("CODE", "")), str(result.get("MESSAGE", "")))

    container = payload.get("StatisticItemList")
    rows = container.get("row", []) if isinstance(container, dict) else []
    monthly: list[tuple[str, str, dt.date]] = []
    for row in rows:
        if not isinstance(row, dict) or row.get("CYCLE") != _MONTHLY:
            continue
        code = str(row.get("ITEM_CODE") or "")
        name = str(row.get("ITEM_NAME") or "").strip()
        start = _month(str(row.get("START_TIME") or ""))
        if code and name and start is not None:
            monthly.append((code, name, start))

    items: dict[str, DepositItem] = {}
    for inst in wanted:
        pattern = NAME_PATTERNS[inst]
        found = next(((c, n, s) for c, n, s in monthly
                      if c == KNOWN_CODES[inst] and pattern.search(n)), None)
        if found is None:
            found = next(((c, n, s) for c, n, s in monthly if pattern.search(n)), None)
        if found is None:
            raise ItemMappingChanged(
                f"{inst}의 항목을 찾지 못했습니다. 출처의 항목 체계가 바뀌었을 수 있습니다.")
        code, name, start = found
        items[inst] = DepositItem(inst, table, code, name, start)
    return items
