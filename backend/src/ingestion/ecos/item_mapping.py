"""항목 매핑 검증·재탐색 (T046, FR-015).

출처가 통화 항목코드를 바꿔도 이름 패턴으로 다시 찾는다. 재탐색도 실패하면 중단한다 —
잘못된 통화의 값을 저장하는 것보다 낫다.

**응답 필드는 `ITEM_CODE` / `ITEM_NAME`이다.** `ITEM_CODE1`이 아니다. 기존 Apps Script
구현이 이 지점에서 자동탐지에 계속 실패했다 (contracts/ecos-adapter.md).
"""

from __future__ import annotations

import json
import re

from src.ingestion.ecos.errors import ItemMappingChanged, SourceUnavailable
from src.ingestion.protocols import ItemMapping

# 통화별 항목명 패턴. 코드가 바뀌어도 이름으로 찾아낸다.
NAME_PATTERNS: dict[str, re.Pattern[str]] = {
    "USD": re.compile(r"미국.*달러|달러화|USD", re.IGNORECASE),
    "JPY": re.compile(r"일본.*엔|엔화|JPY", re.IGNORECASE),
    "EUR": re.compile(r"유로|EUR", re.IGNORECASE),
}


def resolve_item_mapping(body: str, currency_code: str, *, known_code: str) -> ItemMapping:
    """항목 목록에서 통화의 항목코드를 확정한다.

    1. 알려진 코드가 목록에 있고 이름도 일치하면 그대로 쓴다
    2. 아니면 이름 패턴으로 재탐색한다
    3. 재탐색도 실패하면 `ItemMappingChanged`로 중단한다
    """
    pattern = NAME_PATTERNS.get(currency_code)
    if pattern is None:
        raise ItemMappingChanged(f"지원하지 않는 통화: {currency_code}")

    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        raise SourceUnavailable(f"항목 목록 응답이 JSON이 아닙니다: {body[:200]}") from exc

    container = payload.get("StatisticItemList") if isinstance(payload, dict) else None
    rows = container.get("row", []) if isinstance(container, dict) else []

    named: list[tuple[str, str]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        # ITEM_CODE / ITEM_NAME — ITEM_CODE1이 아니다
        code = str(row.get("ITEM_CODE") or "")
        name = str(row.get("ITEM_NAME") or "")
        if code and name:
            named.append((code, name))

    for code, name in named:
        if code == known_code and pattern.search(name):
            return ItemMapping(currency_code, code, name)

    for code, name in named:
        if pattern.search(name):
            return ItemMapping(currency_code, code, name)

    raise ItemMappingChanged(
        f"{currency_code}의 항목을 찾지 못했습니다. 출처의 식별 체계가 변경되었을 수 있습니다.")
