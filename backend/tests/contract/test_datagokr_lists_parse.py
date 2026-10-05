"""행정구역·단지 목록·기본 정보 파서 계약 테스트 (T005) — 009 FR-002, FR-003, FR-015, research R9-3.

T001의 실제 응답(`fixtures/apt/README.md`)으로 본다:

- 법정동코드는 시·도 → 시·군·구 → 법정동만 쓴다. **리(`ri_cd ≠ 00`)는 뺀다**
- 일반시 아래 구(수원시 장안구 …)는 **구를 시·군·구로** 보이고 이름을 "수원시 장안구"로 붙인다. 상위
  시(41110)는 시·군·구 목록에서
  뺀다. 구 행의 상위 코드는 시가 아니라 도(4100000000)라 이름으로 판정한다(T001 실측)
- 출처는 폐지 코드를 주지 않는다 — 옛 "강원도"는 `INFO-3`(결과 없음, 오류가 아니다)
- 단지 목록은 JSON이고 코드는 문자열이다. 결과 없음은 `items: []`
- 기본 정보의 세대수는 실수(`9510.0`)다. **0.0이면 호수(`hoCnt`)**, 그것도 0이면 모른다(None —
  지어내지 않는다)
"""
from __future__ import annotations

import json

import pytest

from src.ingestion.datagokr.errors import DataGoKrFormatError, DataGoKrUnavailable
from src.ingestion.datagokr.kapt_parse import parse_complex_basis, parse_complex_list
from src.ingestion.datagokr.region_parse import build_regions, parse_regions

from .conftest import load


class TestRegionPage:
    def test_서울_한_쪽(self) -> None:
        page = parse_regions(load("apt/region_seoul.json"))
        assert page.total_count == 493
        assert len(page.rows) == 493
        songpa = next(r for r in page.rows if r.code == "1171000000")
        assert (songpa.full_name, songpa.low_name, songpa.high_code) == (
            "서울특별시 송파구", "송파구", "1100000000")

    def test_폐지된_지역은_결과_없음(self) -> None:
        """옛 "강원도"(2023 강원특별자치도로 개편)는 `INFO-3` — 오류가 아니라 빈 결과다."""
        page = parse_regions(load("apt/region_gangwon_old.json"))
        assert (page.total_count, page.rows) == (0, ())

    def test_JSON이_아니면_연결_오류(self) -> None:
        with pytest.raises(DataGoKrUnavailable):
            parse_regions("<html>점검 중</html>")

    def test_모르는_결과_코드는_형식_오류(self) -> None:
        with pytest.raises(DataGoKrFormatError):
            parse_regions('{"RESULT":{"resultCode":"INFO-9","resultMsg":"?"}}')

    def test_상위_코드가_빈_행도_읽는다(self) -> None:
        """2026-10-05 전국 15쪽 실측(T027) — 리 행 둘(영덕군 영해면 대동리 `4777036039`, 통영시
        산양읍 당포리 `4822025032`)의 `locathigh_cd`가 공백 한 칸이다. 리는 쓰지 않는 단계라 그 쪽
        전체를 형식 오류로 버리면 행정구역을 끝내 받지 못한다. 법정동 행이 비면 상위는 코드에서
        정한다(시·군·구 = 앞 5자리)."""
        data = json.loads(load("apt/region_chuncheon.json"))
        rows = data["StanReginCd"][1]["row"]
        ri = next(r for r in rows if r["ri_cd"] != "00")
        umd = next(r for r in rows if r["ri_cd"] == "00" and r["umd_cd"] != "000")
        ri["locathigh_cd"] = umd["locathigh_cd"] = " "
        page = parse_regions(json.dumps(data, ensure_ascii=False))
        assert len(page.rows) == len(rows)
        regions = {r.code: r for r in build_regions(page.rows)}
        assert ri["region_cd"] not in regions
        assert regions[umd["region_cd"]].parent_code == umd["region_cd"][:5] + "00000"


class TestBuildRegions:
    def test_서울은_시도_하나_구_25_동_467(self) -> None:
        regions = build_regions(parse_regions(load("apt/region_seoul.json")).rows)
        levels = [r.level for r in regions]
        assert (levels.count("sido"), levels.count("sgg"), levels.count("umd")) == (1, 25, 467)
        seoul = next(r for r in regions if r.level == "sido")
        assert (seoul.code, seoul.name, seoul.parent_code, seoul.lawd_cd) == (
            "1100000000", "서울특별시", None, None)

    def test_시군구와_법정동(self) -> None:
        rows = parse_regions(load("apt/region_seoul.json")).rows
        regions = {r.code: r for r in build_regions(rows)}
        songpa, garak = regions["1171000000"], regions["1171010700"]
        assert (songpa.level, songpa.name, songpa.parent_code, songpa.lawd_cd) == (
            "sgg", "송파구", "1100000000", "11710")
        assert (garak.level, garak.name, garak.parent_code, garak.lawd_cd) == (
            "umd", "가락동", "1171000000", "11710")
        assert garak.full_name == "서울특별시 송파구 가락동"

    def test_일반시_아래_구는_구를_시군구로(self) -> None:
        regions = build_regions(parse_regions(load("apt/region_suwon.json")).rows)
        sgg = {r.code: r for r in regions if r.level == "sgg"}
        assert "4111000000" not in sgg  # 상위 시(수원시)는 뺀다
        assert {r.name for r in sgg.values()} == {
            "수원시 장안구", "수원시 권선구", "수원시 팔달구", "수원시 영통구"}
        jangan = sgg["4111100000"]
        assert (jangan.parent_code, jangan.lawd_cd) == ("4100000000", "41111")
        wonchon = next(r for r in regions if r.code == "4111710200")
        assert (wonchon.level, wonchon.parent_code, wonchon.lawd_cd) == (
            "umd", "4111700000", "41117")

    def test_리는_뺀다(self) -> None:
        rows = parse_regions(load("apt/region_chuncheon.json")).rows
        assert sum(1 for r in rows if r.ri_cd != "00") == 78
        regions = build_regions(rows)
        assert len(regions) == len(rows) - 78
        chuncheon = next(r for r in regions if r.code == "5111000000")
        assert (chuncheon.level, chuncheon.name, chuncheon.lawd_cd) == ("sgg", "춘천시", "51110")


class TestComplexList:
    def test_가락동_단지_23개(self) -> None:
        page = parse_complex_list(load("apt/kapt_list_1171010700.json"))
        assert page.total_count == 23 and len(page.complexes) == 23
        helio = next(c for c in page.complexes if c.kapt_code == "A10025850")
        assert (helio.name, helio.bjd_code) == ("헬리오시티아파트", "1171010700")

    def test_결과_없음(self) -> None:
        page = parse_complex_list(load("apt/kapt_list_empty.json"))
        assert (page.total_count, page.complexes) == (0, ())

    def test_받은_수가_전체와_다르면_잘림(self) -> None:
        body = load("apt/kapt_list_1171010700.json").replace('"totalCount":23', '"totalCount":24')
        with pytest.raises(DataGoKrFormatError):
            parse_complex_list(body)

    def test_결과_코드가_00이_아니면_형식_오류(self) -> None:
        body = load("apt/kapt_list_empty.json").replace('"resultCode":"00"', '"resultCode":"03"')
        with pytest.raises(DataGoKrFormatError):
            parse_complex_list(body)


class TestComplexBasis:
    def test_헬리오시티(self) -> None:
        basis = parse_complex_basis(load("apt/kapt_basis_A10025850.json"))
        assert basis is not None
        assert (basis.kapt_code, basis.households, basis.move_in_year) == ("A10025850", 9510, 2018)
        assert (basis.bjd_code, basis.bonbun, basis.bubun) == ("1171010700", 479, 0)

    def test_세대수가_0이면_호수(self) -> None:
        """더샵송파루미스타(2026-05 사용승인) — `kaptdaCnt 0.0`, `hoCnt 183`."""
        basis = parse_complex_basis(load("apt/kapt_basis_A10020074.json"))
        assert basis is not None
        assert (basis.households, basis.move_in_year) == (183, 2026)
        assert (basis.bonbun, basis.bubun) == (161, 3)

    def test_세대수와_호수가_모두_0이면_모른다(self) -> None:
        body = load("apt/kapt_basis_A10020074.json").replace('"hoCnt":183', '"hoCnt":0')
        basis = parse_complex_basis(body)
        assert basis is not None and basis.households is None

    def test_부번이_비면_0(self) -> None:
        """`가락동 142- 가락풍림아파트`."""
        basis = parse_complex_basis(load("apt/kapt_basis_A10021256.json"))
        assert basis is not None and (basis.bonbun, basis.bubun) == (142, 0)

    def test_사용승인일이_비면_입주년도를_모른다(self) -> None:
        body = load("apt/kapt_basis_A10025850.json").replace(
            '"kaptUsedate":"20181228"', '"kaptUsedate":""')
        basis = parse_complex_basis(body)
        assert basis is not None and basis.move_in_year is None

    def test_없는_단지_코드는_결과_없음(self) -> None:
        assert parse_complex_basis(load("apt/kapt_basis_unknown.json")) is None

    @pytest.mark.parametrize("name", [
        "A10020074", "A10021256", "A10021390", "A10025850", "A13816001", "A13816002", "A13816005",
        "A13816101", "A13816202", "A13880105", "A13880201", "A13880204", "A13880406", "A13880407",
        "A13880602", "A13880603", "A13880701", "A13880806", "A13881005", "A13881103", "A13895501",
        "A13895502", "A13895503",
    ])
    def test_가락동_단지_모두_읽힌다(self, name: str) -> None:
        basis = parse_complex_basis(load(f"apt/kapt_basis_{name}.json"))
        assert basis is not None and basis.kapt_code == name
        assert basis.households is not None and basis.households > 0
        assert basis.move_in_year is not None and basis.bonbun is not None
