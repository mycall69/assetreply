"""한글 정규화와 초성 판정 (T030) — 006 FR-022, research R6-5.

**글자마다 판정 방식이 다르다.** "삼성ㅈ"의 "삼"·"성"은 그 음절이어야 하고 "ㅈ"은 초성이 ㅈ인 아무
음절이면 된다. 한 컬럼에 대한 `LIKE` 하나로 표현할 수 없고, DB마다 다른 문법에 기대면 헌법 DB 운영
규약을 어긴다 — 그래서 순수 함수로 둔다(헌법 원칙 IV).

| 검색어 글자 | 맞는 조건 |
|-------------|-----------|
| 초성 자모(쌍자음 포함) | 그 위치 음절의 초성이 같다. **ㅆ과 ㅅ은 다르다** |
| 완성 음절, 마지막이 아님 | 음절이 같다 |
| 완성 음절, **마지막이고 받침 없음** | 초성·중성이 같다("서"는 "성"과 맞는다 — 받침 입력 대기) |
| 완성 음절, 마지막이고 받침 있음 | 음절이 같다 |
| 그 밖 | 같은 글자 |
"""

from __future__ import annotations

import unicodedata
from typing import Final

#: 초성 19자(한글 호환 자모). 음절의 초성 번호 순서와 같다.
CHOSEONG: Final = "ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ"
_CHOSEONG_SET: Final = frozenset(CHOSEONG)

_SYLLABLE_FIRST: Final = 0xAC00
_SYLLABLE_LAST: Final = 0xD7A3
_JUNG_COUNT: Final = 21
_JONG_COUNT: Final = 28
#: 첫가끝 초성(U+1100~U+1112). 하나만 오면 NFC로도 합쳐지지 않는다.
_CONJOINING_CHO_FIRST: Final = 0x1100


def _conjoining_to_compat(ch: str) -> str:
    code = ord(ch)
    if _CONJOINING_CHO_FIRST <= code < _CONJOINING_CHO_FIRST + len(CHOSEONG):
        return CHOSEONG[code - _CONJOINING_CHO_FIRST]
    return ch


def normalize(text: str) -> str:
    """NFC로 합치고, 공백을 지우고, 라틴 문자를 소문자로 바꾼다.

    입력기에 따라 한글이 자모로 풀려 온다(NFD). 합치지 않으면 화면에는 같은 글자가 다른 글자로
    판정된다. 대소문자는 가리지 않는다(FR-021).
    """
    composed = unicodedata.normalize("NFC", text)
    return "".join(_conjoining_to_compat(ch) for ch in composed if not ch.isspace()).casefold()


def is_syllable(ch: str) -> bool:
    return len(ch) == 1 and _SYLLABLE_FIRST <= ord(ch) <= _SYLLABLE_LAST


def is_choseong(ch: str) -> bool:
    return ch in _CHOSEONG_SET


def _offset(ch: str) -> int:
    return ord(ch) - _SYLLABLE_FIRST


def choseong_of(ch: str) -> str:
    """음절이면 그 초성, 아니면 글자 그대로."""
    if not is_syllable(ch):
        return ch
    return CHOSEONG[_offset(ch) // (_JUNG_COUNT * _JONG_COUNT)]


def has_final(ch: str) -> bool:
    """음절에 받침이 있는가. 음절이 아니면 거짓."""
    return is_syllable(ch) and _offset(ch) % _JONG_COUNT != 0


def choseong_string(text: str) -> str:
    """음절은 초성으로, 그 밖의 글자는 그대로 둔 열. 정규화한 문자열에 쓴다."""
    return "".join(choseong_of(ch) for ch in text)


def char_matches(query_ch: str, name_ch: str, *, last: bool) -> bool:
    """검색어 글자 하나가 이름 글자 하나와 맞는가 (모듈 설명의 표)."""
    if is_choseong(query_ch):
        return choseong_of(name_ch) == query_ch
    if is_syllable(query_ch):
        if query_ch == name_ch:
            return True
        if last and not has_final(query_ch) and is_syllable(name_ch):
            # 받침 입력 대기 — 초성·중성이 같으면 맞는다. 받침 번호를 뺀 값이 같다는 뜻이다.
            return _offset(name_ch) - _offset(name_ch) % _JONG_COUNT == _offset(query_ch)
        return False
    return query_ch == name_ch
