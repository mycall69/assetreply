"""공동주택 단지 목록·기본 정보 파서 (009 T011, FR-003, research R9-3).

둘 다 JSON이다(단지 목록은 `_type=xml`을 줘도 JSON — T001 실측).
`{"response":{"header":{"resultCode":"00"},"body":…}}`.

- 단지 목록: `items` 배열. 결과 없음은 빈 배열(오류 아님). 받은 수가 `totalCount`와 다르면 잘림 —
  형식 오류다
- 기본 정보: `item` 하나. 없는 단지 코드는 `kaptCode: null`인 항목 — 결과 없음(None)
- **세대수(`kaptdaCnt`)는 실수**(`9510.0`)이고 **0.0인 단지가 있다**(신축 더샵송파루미스타 — 호수
  183). 0이면 호수(`hoCnt`)를
  쓰고, 그것도 0이면 모른다(None — 지어내지 않는다, FR-003)
- 입주년도는 사용승인일(`YYYYMMDD`)의 연도, 지번은 지번 주소에서 본번·부번(`142-`는 부번 0)
"""

from __future__ import annotations

import datetime as dt
import json
import re
from dataclasses import dataclass
from decimal import Decimal

from src.ingestion.datagokr.errors import DataGoKrFormatError, DataGoKrUnavailable
from src.ingestion.protocols import ComplexBasis, ComplexListing

_OK = "00"
#: 지번 주소의 본번-부번 — `가락동 161-3 …`, `가락동 142- …`, `가락동 479 …`
_JIBUN = re.compile(r"\s(?:산\s?)?(\d+)(?:-(\d*))?(?=\s|$)")


@dataclass(frozen=True, slots=True)
class ComplexListPage:
    total_count: int
    complexes: tuple[ComplexListing, ...]


def _response(body: str) -> dict[str, object]:
    try:
        data = json.loads(body, parse_float=Decimal)
        response = data["response"]
        code = response["header"]["resultCode"]
    except json.JSONDecodeError as exc:
        raise DataGoKrUnavailable("단지 자료 응답이 JSON이 아닙니다") from exc
    except (KeyError, TypeError) as exc:
        raise DataGoKrFormatError("단지 자료 응답의 모양이 다릅니다") from exc
    if code != _OK:
        raise DataGoKrFormatError(f"단지 자료 결과 코드 {code}")
    body_part = response.get("body")
    if not isinstance(body_part, dict):
        raise DataGoKrFormatError("단지 자료 응답에 body가 없습니다")
    return body_part


def parse_complex_list(body: str) -> ComplexListPage:
    part = _response(body)
    items = part.get("items") or []
    if not isinstance(items, list):
        raise DataGoKrFormatError("단지 목록의 items가 배열이 아닙니다")
    try:
        total = int(str(part.get("totalCount")))
        complexes = tuple(
            ComplexListing(str(i["kaptCode"]), str(i["kaptName"]).strip(), str(i["bjdCode"]))
            for i in items)
    except (KeyError, TypeError, ValueError) as exc:
        raise DataGoKrFormatError("단지 목록 항목을 읽을 수 없습니다") from exc
    if len(complexes) != total:
        raise DataGoKrFormatError(f"단지 목록이 잘렸습니다(받은 {len(complexes)} / 전체 {total})")
    return ComplexListPage(total, complexes)


def _count(value: object) -> int | None:
    """양의 정수로 읽히면 그 값, 0이나 비어 있으면 None."""
    if value is None or value == "":
        return None
    try:
        number = Decimal(str(value))
    except ArithmeticError as exc:
        raise DataGoKrFormatError(f"세대수·호수를 읽을 수 없습니다: {value!r}") from exc
    if number != number.to_integral_value() or number < 0:
        raise DataGoKrFormatError(f"세대수·호수가 자연수가 아닙니다: {value!r}")
    return int(number) or None


def _year(value: object) -> int | None:
    if not isinstance(value, str) or len(value) != 8 or not value.isdigit():
        return None
    try:
        return dt.date(int(value[:4]), int(value[4:6]), int(value[6:])).year
    except ValueError:
        return None


def parse_complex_basis(body: str) -> ComplexBasis | None:
    part = _response(body)
    item = part.get("item")
    if not isinstance(item, dict) or item.get("kaptCode") is None:
        return None
    households = _count(item.get("kaptdaCnt")) or _count(item.get("hoCnt"))
    address = str(item.get("kaptAddr") or "")
    match = _JIBUN.search(address)
    bonbun = int(match.group(1)) if match else None
    bubun = (int(match.group(2)) if match.group(2) else 0) if match else None
    return ComplexBasis(
        kapt_code=str(item["kaptCode"]), name=str(item.get("kaptName") or "").strip(),
        households=households, move_in_year=_year(item.get("kaptUsedate")),
        bjd_code=str(item.get("bjdCode") or ""),
        bonbun=bonbun, bubun=bubun,
    )
