"""한글 정규화와 초성 판정 (T013) — 006 FR-022, research R6-5.

**글자마다 판정 방식이 다르다.** "삼성ㅈ"의 "삼"·"성"은 그 음절이어야 하고 "ㅈ"은 초성이 ㅈ인
아무 음절이면 된다. 한 규칙으로 뭉개면 혼용 입력에서 결과가 사라졌다 나타난다.
"""
from __future__ import annotations

import unicodedata

import pytest

from src.search.hangul import (
    CHOSEONG,
    char_matches,
    choseong_of,
    choseong_string,
    has_final,
    is_choseong,
    is_syllable,
    normalize,
)


class Test정규화:
    @pytest.mark.parametrize(("raw", "expected"), [
        ("삼성전자", "삼성전자"),
        ("삼성 전자", "삼성전자"),            # 공백 제거
        (" 삼성\t전자 ", "삼성전자"),
        ("SK하이닉스", "sk하이닉스"),          # 라틴 소문자화
        ("KODEX 200", "kodex200"),
        ("Apple Inc.", "appleinc."),
        ("NAVER", "naver"),
    ])
    def test_공백을_지우고_라틴을_소문자로(self, raw: str, expected: str) -> None:
        assert normalize(raw) == expected

    def test_NFD로_온_한글을_음절로_합친다(self) -> None:
        """macOS 입력기 등은 자모를 풀어 보낸다. 합치지 않으면 같은 글자가 다른 글자가 된다."""
        decomposed = unicodedata.normalize("NFD", "삼성전자")
        assert decomposed != "삼성전자"
        assert normalize(decomposed) == "삼성전자"

    def test_첫가끝_초성을_호환_자모로_바꾼다(self) -> None:
        """조합형 초성(U+1100대) 하나만 오면 NFC로도 합쳐지지 않는다."""
        assert normalize("ᄉᄉ") == "ㅅㅅ"


class Test초성:
    def test_초성은_19자다(self) -> None:
        assert len(CHOSEONG) == 19
        assert "ㅆ" in CHOSEONG and "ㄲ" in CHOSEONG
        # 겹받침용 자모는 초성이 아니다
        assert "ㄳ" not in CHOSEONG

    @pytest.mark.parametrize(("ch", "expected"), [
        ("삼", "ㅅ"), ("쌍", "ㅆ"), ("전", "ㅈ"), ("짜", "ㅉ"), ("하", "ㅎ"),
        ("가", "ㄱ"), ("까", "ㄲ"), ("힣", "ㅎ"),
        ("a", "a"), ("1", "1"), ("ㅅ", "ㅅ"),
    ])
    def test_음절의_초성(self, ch: str, expected: str) -> None:
        assert choseong_of(ch) == expected

    def test_초성_열(self) -> None:
        assert choseong_string("삼성전자") == "ㅅㅅㅈㅈ"
        assert choseong_string("sk하이닉스") == "skㅎㅇㄴㅅ"
        assert choseong_string("kodex200") == "kodex200"

    def test_판별(self) -> None:
        assert is_choseong("ㅅ") and not is_choseong("삼") and not is_choseong("a")
        assert is_syllable("삼") and not is_syllable("ㅅ") and not is_syllable("a")
        assert has_final("성") and not has_final("서") and not has_final("a")


class Test글자_일치:
    @pytest.mark.parametrize(("q", "n", "last", "expected"), [
        # 초성 자모 — 그 위치 음절의 초성이 같으면 맞는다
        ("ㅅ", "삼", False, True),
        ("ㅅ", "삼", True, True),
        ("ㅅ", "ㅅ", False, True),
        ("ㅈ", "삼", False, False),
        # **쌍자음과 홑자음은 다르다**
        ("ㅆ", "삼", False, False),
        ("ㅅ", "쌍", False, False),
        ("ㅆ", "쌍", False, True),
        # 완성 음절, 마지막이 아니면 같은 음절이어야 한다
        ("삼", "삼", False, True),
        ("서", "성", False, False),
        # **받침 대기** — 마지막 글자이고 받침이 없으면 초성·중성이 같은 음절과 맞는다
        ("서", "성", True, True),
        ("서", "서", True, True),
        ("서", "소", True, False),      # 중성이 다르다
        ("사", "성", True, False),
        # 마지막이어도 받침이 있으면 음절이 같아야 한다
        ("성", "선", True, False),
        ("성", "성", True, True),
        # 그 밖의 글자는 같아야 한다
        ("a", "a", False, True),
        ("a", "b", True, False),
        ("2", "2", True, True),
        # 라틴은 초성과 맞지 않는다
        ("ㅅ", "s", True, False),
    ])
    def test_표(self, q: str, n: str, last: bool, expected: bool) -> None:
        assert char_matches(q, n, last=last) is expected
