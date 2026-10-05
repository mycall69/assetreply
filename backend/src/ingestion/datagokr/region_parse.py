"""행정안전부 법정동코드 파서 (009 T011, FR-002, FR-015, research R9-3).

응답(`type=json`)은 `{"StanReginCd":[{"head":[{"totalCount":N}, …, {"RESULT":{…}}]},
{"row":[…]}]}`이다.
결과 없음은 `{"RESULT":{"resultCode":"INFO-3"}}` — 오류가 아니라 빈 쪽이다. **출처는 폐지 코드를
주지 않는다**(옛 "강원도"는 INFO-3 — T001 실측). 그래서 갱신에서 사라진 코드가 곧 폐지다(저장 계층이
`retired_at`을 남긴다).

`build_regions`는 여러 쪽을 모은 행으로 화면용 단계를 만든다:

- 리(`ri_cd ≠ 00`)는 뺀다 — 법정동까지만 쓴다
- 일반시 아래 구(수원시 장안구 …)는 **구를 시·군·구로** 보이고 이름을 "수원시 장안구"로 붙인다. 상위
  시(41110)는 뺀다.
  구 행의 상위 코드가 시가 아니라 도(4100000000)라, 다른 시·군·구의 이름이 "경기도 수원시 "로
  시작하는지로 판정한다
- 실거래 요청 단위(`lawd_cd`)는 시·군·구 5자리다
- 시·도 행이 없는 시·군·구(세종특별자치시)는 그 이름으로 시·도를 만든다(T027 실측)
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass

from src.ingestion.datagokr.errors import DataGoKrFormatError, DataGoKrUnavailable
from src.ingestion.protocols import Region

_OK = "INFO-0"
_NO_DATA = "INFO-3"


@dataclass(frozen=True, slots=True)
class RegionRow:
    """출처의 한 행을 정규화한 것 — 단계는 아직 정하지 않았다."""

    code: str
    sido_cd: str
    sgg_cd: str
    umd_cd: str
    ri_cd: str
    full_name: str
    high_code: str
    low_name: str


@dataclass(frozen=True, slots=True)
class RegionPage:
    total_count: int
    rows: tuple[RegionRow, ...]


def _text(row: dict[str, object], key: str, length: int | None = None) -> str:
    value = row.get(key)
    if not isinstance(value, str):
        raise DataGoKrFormatError(f"법정동코드 행의 {key} 값을 읽을 수 없습니다: {value!r}")
    if length is not None and (len(value) != length or not value.isdigit()):
        raise DataGoKrFormatError(f"법정동코드 행의 {key} 값을 읽을 수 없습니다: {value!r}")
    return value


def _high_code(row: dict[str, object]) -> str:
    """상위 코드. **비어 올 수 있다** — 2026-10-05 전국 15쪽의 리 행 둘이 공백 한 칸이었다(T027
    실측). 비면 빈 문자열이고, 쓰는 쪽(`build_regions`)이 코드에서 정한다. 값이 있는데 10자리 숫자가
    아니면 형식 오류다."""
    value = row.get("locathigh_cd")
    if isinstance(value, str) and not value.strip():
        return ""
    return _text(row, "locathigh_cd", 10)


def parse_regions(body: str) -> RegionPage:
    """법정동코드 한 쪽. JSON이 아니면 연결 오류(점검 안내 등), 모르는 결과 코드는 형식 오류."""
    try:
        data = json.loads(body)
    except json.JSONDecodeError as exc:
        raise DataGoKrUnavailable("법정동코드 응답이 JSON이 아닙니다") from exc
    if isinstance(data, dict) and "RESULT" in data:
        code = str(data["RESULT"].get("resultCode", ""))
        if code == _NO_DATA:
            return RegionPage(0, ())
        raise DataGoKrFormatError(f"법정동코드 결과 코드 {code}")
    try:
        head, body_part = data["StanReginCd"][0]["head"], data["StanReginCd"][1]["row"]
        result = next(h["RESULT"] for h in head if "RESULT" in h)
        total = int(next(h["totalCount"] for h in head if "totalCount" in h))
    except (KeyError, IndexError, TypeError, StopIteration, ValueError) as exc:
        raise DataGoKrFormatError("법정동코드 응답의 모양이 다릅니다") from exc
    if result.get("resultCode") != _OK:
        raise DataGoKrFormatError(f"법정동코드 결과 코드 {result.get('resultCode')}")
    rows = tuple(
        RegionRow(
            code=_text(row, "region_cd", 10), sido_cd=_text(row, "sido_cd", 2),
            sgg_cd=_text(row, "sgg_cd", 3), umd_cd=_text(row, "umd_cd", 3),
            ri_cd=_text(row, "ri_cd", 2),
            full_name=_text(row, "locatadd_nm").strip(), high_code=_high_code(row),
            low_name=_text(row, "locallow_nm").strip(),
        )
        for row in body_part
    )
    return RegionPage(total, rows)


def build_regions(rows: Iterable[RegionRow]) -> tuple[Region, ...]:
    """여러 쪽의 행으로 시·도 → 시·군·구 → 법정동을 만든다(리 제외, 일반시 아래 구는 구를
    시·군·구로)."""
    used = [row for row in rows if row.ri_cd == "00"]
    sgg = [row for row in used if row.sgg_cd != "000" and row.umd_cd == "000"]
    cities_with_gu = {city.code for city in sgg
                      if any(other.full_name.startswith(city.full_name + " ") for other in sgg)}
    regions: list[Region] = []
    # 시·도 행이 없는 시·군·구(세종특별자치시 — 시·군·구 3611000000 하나뿐, T027 실측)는 그 이름으로
    # 시·도를 만든다. 만들지 않으면 상위가 없어 시·도 풀다운에 나오지 않는다. 전체 이름이 한 낱말인
    # 시·군·구만 — "강원특별자치도 춘천시"처럼 시·도 이름이 앞에 있으면 시·도 행이 따로 있다(일부만
    # 받은 목록일 뿐이다).
    sido_codes = {row.code for row in used if row.sgg_cd == "000"}
    for row in sgg:
        code = row.sido_cd + "00000000"
        if code not in sido_codes and len(row.full_name.split()) == 1:
            regions.append(Region(code, "sido", None, None, row.full_name, row.full_name))
            sido_codes.add(code)
    for row in used:
        if row.sgg_cd == "000":
            regions.append(Region(row.code, "sido", None, None, row.full_name, row.full_name))
        elif row.umd_cd == "000":
            if row.code in cities_with_gu:
                continue
            name = " ".join(row.full_name.split()[1:]) or row.low_name
            regions.append(Region(row.code, "sgg", row.sido_cd + "00000000", row.code[:5], name,
                                  row.full_name))
        else:
            parent = row.high_code or row.code[:5] + "00000"  # 비어 오면 그 시·군·구
            regions.append(Region(row.code, "umd", parent, row.code[:5], row.low_name,
                                  row.full_name))
    return tuple(regions)
