"""Npay 부동산 단지 자동완성 응답 파싱 (010 반복 3, research R10-19).

출처 키 이름(`complexNumber`·`legalDivisionNumber` 등)은 이 파일 밖으로 나가지 않는다 — 밖에는 후보
(`NaverComplexCandidate`)만 보인다(헌법 원칙 II). 모양이 다르면 **그 후보만 버리지 않고** 응답
전체를 형식 오류로 본다 — 일부만 고르면 맞는 단지가 빠진 채 다른 단지가 골라진다.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

from src.ingestion.naver_land.errors import NaverLandFormatError

#: 법정동 코드 10자리 — 우리 `apt_complex.umd_code`와 같은 체계다.
_UMD_CODE = re.compile(r"^\d{10}$")


@dataclass(frozen=True, slots=True)
class NaverComplexCandidate:
    """자동완성 후보 하나 — 네이버 단지 번호·이름·법정동 코드·유형(A01 아파트, A04 재건축 등)."""

    number: int
    name: str
    legal_division_code: str
    type: str


def parse_complexes(raw: str) -> list[NaverComplexCandidate]:
    """응답 본문 → 후보 목록(응답 순서). 빈 결과는 빈 목록이다."""
    try:
        body = json.loads(raw)
    except ValueError as exc:
        raise NaverLandFormatError("단지 자동완성 응답이 JSON이 아닙니다.") from exc
    if not isinstance(body, dict) or body.get("isSuccess") is not True:
        raise NaverLandFormatError("단지 자동완성이 실패를 알렸습니다.")
    result = body.get("result")
    items = result.get("list") if isinstance(result, dict) else None
    if not isinstance(items, list):
        raise NaverLandFormatError("단지 자동완성 응답에 목록이 없습니다.")
    return [_candidate(item) for item in items]


def _candidate(item: object) -> NaverComplexCandidate:
    if not isinstance(item, dict):
        raise NaverLandFormatError("단지 자동완성 후보의 모양이 다릅니다.")
    number, name = item.get("complexNumber"), item.get("complexName")
    code, kind = item.get("legalDivisionNumber"), item.get("type")
    if (not isinstance(number, int) or isinstance(number, bool)
            or not isinstance(name, str) or not name):
        raise NaverLandFormatError("단지 자동완성 후보에 번호나 이름이 없습니다.")
    if not isinstance(code, str) or not _UMD_CODE.match(code):
        raise NaverLandFormatError("단지 자동완성 후보의 법정동 코드 형식이 다릅니다.")
    return NaverComplexCandidate(number=number, name=name, legal_division_code=code,
                                 type=kind if isinstance(kind, str) else "")
