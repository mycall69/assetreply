"""Npay 부동산 단지 고르기 (010 반복 3, T061) — FR-029, research R10-19. 순수 함수 — DB·HTTP 없음.

네이버의 단지 이름은 우리 이름(공동주택 단지 목록)과 다르다 — "아파트"가 없고(헬리오시티), 지역
접두가 빠지기도 한다(가락미륭 → 미륭, 잠실리센츠 → 리센츠). 그래서

1. **같은 법정동 코드**의 후보만 본다 — 같은 이름의 다른 지역 단지(송파 헬리오시티와 경기의
헬리오시티)로 가지 않는다 2. 이름을 정규화(공백·괄호와 그 안·끝의 "아파트" 뺌)해 **정확히 같은**
후보가 하나면 그것 3. 없으면 한쪽이 다른 쪽을 품는 후보가 **하나뿐일 때만** 그것 4. 그
밖(없음·여럿)은 못 찾음 — 틀린 단지로 보내느니 검색으로 연다
"""

from __future__ import annotations

import pytest

from src.api.services.apt_naver_link import (
    normalize_complex_name,
    pick_naver_complex,
    search_keywords,
)
from src.ingestion.naver_land.parse import NaverComplexCandidate

GARAK, GAEPO, JAMSIL = "1171010700", "1168010300", "1171010100"


def c(number: int, name: str, umd: str, kind: str = "A01") -> NaverComplexCandidate:
    return NaverComplexCandidate(number=number, name=name, legal_division_code=umd, type=kind)


HELIO = [c(111515, "헬리오시티", GARAK), c(130495, "헬리오시티", "4128112000")]
MIRUNG = [c(596, "미륭", GARAK, "A04")]
GAEPO_XI = [
    c(128527, "개포자이프레지던스", GAEPO),
    c(8928, "개포자이", GAEPO),
    c(145017, "개포자이르네", GAEPO),
]
RICENZ = [c(22746, "리센츠", JAMSIL), c(572526, "리센츠빌(도시형)", JAMSIL, "A06")]


@pytest.mark.parametrize(
    ("name", "umd", "candidates", "expected"),
    [
        ("헬리오시티아파트", GARAK, HELIO, 111515),
        ("가락미륭아파트", GARAK, MIRUNG, 596),
        ("개포자이프레지던스", GAEPO, GAEPO_XI, 128527),
        ("개포자이아파트", GAEPO, GAEPO_XI, 8928),
        ("개포자이르네", GAEPO, GAEPO_XI, 145017),
        ("잠실리센츠", JAMSIL, RICENZ, 22746),
    ],
    ids=[
        "헬리오시티",
        "가락미륭→미륭",
        "개포자이프레지던스",
        "개포자이(정확히 같은 이름)",
        "개포자이르네",
        "잠실리센츠→리센츠",
    ],
)
def test_참조_단지를_고른다(
    name: str, umd: str, candidates: list[NaverComplexCandidate], expected: int
) -> None:
    picked = pick_naver_complex(candidates, umd_code=umd, name=name)
    assert picked is not None and picked.number == expected


def test_다른_법정동의_같은_이름은_고르지_않는다() -> None:
    assert (
        pick_naver_complex(
            [c(130495, "헬리오시티", "4128112000")], umd_code=GARAK, name="헬리오시티아파트"
        )
        is None
    )


def test_품는_후보가_여럿이면_못_찾음이다() -> None:
    """ "개포"는 세 후보 모두에 들어 있다 — 아무거나 고르면 틀린 단지로 간다."""
    assert pick_naver_complex(GAEPO_XI, umd_code=GAEPO, name="개포") is None


def test_이름이_엇갈리면_못_찾음이다() -> None:
    assert (
        pick_naver_complex(
            [c(1, "올림픽훼밀리타운", GARAK)], umd_code=GARAK, name="헬리오시티아파트"
        )
        is None
    )


def test_후보가_없으면_못_찾음이다() -> None:
    assert pick_naver_complex([], umd_code=GARAK, name="헬리오시티아파트") is None


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("헬리오시티아파트", "헬리오시티"),
        ("리센츠빌(도시형)", "리센츠빌"),
        ("잠실 파크 리오", "잠실파크리오"),
        ("개포자이", "개포자이"),
        ("아파트", "아파트"),  # 이름 전체가 "아파트"면 지우지 않는다 — 빈 이름은 무엇이든 품는다
    ],
)
def test_이름_정규화(raw: str, expected: str) -> None:
    assert normalize_complex_name(raw) == expected


def test_검색어는_법정동_이름과_단지명_다음에_단지명만() -> None:
    assert search_keywords("가락동", "헬리오시티아파트") == ["가락동 헬리오시티", "헬리오시티"]


def test_법정동_이름을_모르면_단지명만() -> None:
    assert search_keywords("", "가락미륭아파트") == ["가락미륭"]
