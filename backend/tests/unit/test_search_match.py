"""검색 일치·순위 (T014) — 006 FR-020, FR-022, FR-023, FR-024, SC-002, SC-003.

quickstart 3의 표를 그대로 옮긴다. **순서가 결정적이어야 한다** — 같은 검색어로 다른 순서가
나오면 같은 검색에서 다른 종목을 고르게 된다.
"""
from __future__ import annotations

import random

import pytest

from src.search.match import SearchEntry, SearchIndex, match_text


def kr(key: int, name: str, code: str) -> SearchEntry:
    return SearchEntry(key=key, names=(name,), codes=(code,), market="KRX", code=code)


ENTRIES = [
    kr(1, "삼성전자", "005930"),
    kr(2, "삼성전자우", "005935"),
    kr(3, "삼성SDI", "006400"),
    kr(4, "삼성물산", "028260"),
    kr(5, "삼성바이오로직스", "207940"),
    kr(6, "SK하이닉스", "000660"),
    kr(7, "KODEX 200", "069500"),
    kr(8, "TIGER 200", "102110"),
    kr(9, "쌍방울", "102280"),
    kr(10, "NAVER", "035420"),
    kr(11, "LG에너지솔루션", "373220"),
    kr(12, "신한지주", "055550"),
    kr(13, "대신밸류리츠", "0030R0"),
    kr(14, "한화생명", "088350"),
]


def names(index: SearchIndex, query: str, limit: int = 20) -> list[str]:
    return [h.entry.names[0] for h in index.search(query, limit).hits]


@pytest.fixture
def index() -> SearchIndex:
    return SearchIndex(ENTRIES)


class Test대표_검색어:
    """quickstart 3 — 기대 종목이 첫 화면 결과에 있어야 한다."""

    @pytest.mark.parametrize(("query", "expected"), [
        ("삼성전자", "삼성전자"),
        ("ㅅㅅㅈㅈ", "삼성전자"),
        ("ㅅㅅㅈㅈ", "삼성전자우"),
        ("삼ㅅㅈ", "삼성전자"),
        ("삼성ㅈ", "삼성전자"),
        ("삼성 전자", "삼성전자"),
        ("005930", "삼성전자"),
        ("sk하이닉스", "SK하이닉스"),
        ("SK하이닉스", "SK하이닉스"),
        ("ㅎㅇㄴㅅ", "SK하이닉스"),
        ("kodex 200", "KODEX 200"),
        ("KODEX200", "KODEX 200"),
        ("naver", "NAVER"),
        ("ㅇㄴㅈ", "LG에너지솔루션"),
        ("0030r0", "대신밸류리츠"),
    ])
    def test_찾는다(self, index: SearchIndex, query: str, expected: str) -> None:
        assert expected in names(index, query)

    def test_정확_일치가_맨_위다(self, index: SearchIndex) -> None:
        assert names(index, "삼성전자")[:2] == ["삼성전자", "삼성전자우"]

    def test_보통주와_우선주가_구별되어_함께_나온다(self, index: SearchIndex) -> None:
        got = names(index, "ㅅㅅㅈㅈ")
        assert got[:2] == ["삼성전자", "삼성전자우"]

    def test_받침_대기(self, index: SearchIndex) -> None:
        """"삼성"을 치는 도중의 "삼서"에서 결과가 사라지면 안 된다 (FR-022)."""
        got = names(index, "삼서")
        assert {"삼성전자", "삼성전자우", "삼성SDI", "삼성물산", "삼성바이오로직스"} <= set(got)

    def test_받침_대기는_마지막_글자만이다(self, index: SearchIndex) -> None:
        assert names(index, "서전") == []

    def test_쌍자음은_홑자음과_다르다(self, index: SearchIndex) -> None:
        got = names(index, "ㅆ")
        assert "쌍방울" in got
        assert not any(n.startswith("삼") or n.startswith("신") for n in got)

    def test_홑자음은_쌍자음과_맞지_않는다(self, index: SearchIndex) -> None:
        assert "쌍방울" not in names(index, "ㅅㅂ")

    def test_없으면_비어_있다(self, index: SearchIndex) -> None:
        outcome = index.search("ㅋㅋㅋㅋ", 20)
        assert outcome.hits == () and outcome.truncated is False


class Test순위:
    def test_정확_앞부분_포함_순(self) -> None:
        # 이름 길이와 순위가 엇갈리게 둔다 — 길이로만 정렬하면 이 순서가 나오지 않는다.
        index = SearchIndex([
            kr(1, "삼성전자", "000003"),       # 포함 (4자)
            kr(2, "전자랜드몰", "000002"),     # 앞부분 (5자)
            kr(3, "전자", "000001"),           # 정확 (2자)
            kr(4, "전", "000004"),             # 맞지 않음
        ])
        hits = index.search("전자", 20).hits
        assert [(h.entry.key, h.match) for h in hits] == [
            (3, "exact"), (2, "prefix"), (1, "contains")]

    def test_포함_일치는_짧은_앞부분_일치보다_뒤다(self) -> None:
        index = SearchIndex([kr(1, "삼전", "000001"), kr(2, "전자기기공업사", "000002")])
        assert [h.entry.key for h in index.search("전", 20).hits] == [2, 1]

    def test_코드가_검색어와_같으면_정확_일치다(self, index: SearchIndex) -> None:
        first = index.search("005930", 20).hits[0]
        assert first.entry.code == "005930"
        assert first.match == "exact"

    def test_같은_순위_안에서는_일치한_이름이_짧은_순(self, index: SearchIndex) -> None:
        """FR-023 — 정확 일치 다음은 앞부분 일치이며, 그 안에서 짧은 이름이 먼저다."""
        got = names(index, "삼성")
        # 4자(물 < 전) → 5자(정규화한 "삼성sdi"의 s < 전) → 8자
        assert got == ["삼성물산", "삼성전자", "삼성SDI", "삼성전자우", "삼성바이오로직스"]

    def test_길이가_같으면_코드_포인트_순(self) -> None:
        index = SearchIndex([kr(1, "가나다B", "000002"), kr(2, "가나다A", "000001")])
        # 정규화하면 "가나다a" < "가나다b"
        assert names(index, "가나") == ["가나다A", "가나다B"]

    def test_이름까지_같으면_시장_다음_코드(self) -> None:
        index = SearchIndex([
            SearchEntry(key=1, names=("같은이름",), codes=("B",), market="NYSE", code="B"),
            SearchEntry(key=2, names=("같은이름",), codes=("A",), market="NYSE", code="A"),
            SearchEntry(key=3, names=("같은이름",), codes=("000001",), market="KRX",
                        code="000001"),
        ])
        assert [h.entry.key for h in index.search("같은이름", 20).hits] == [3, 2, 1]

    def test_입력_순서를_섞어도_결과_순서가_같다(self) -> None:
        """SC-003 — 색인을 만든 순서가 결과에 새어 나오면 같은 검색어가 매번 다르다."""
        base = [h.entry.key for h in SearchIndex(ENTRIES).search("ㅅ", 50).hits]
        rng = random.Random(7)
        for _ in range(10):
            shuffled = ENTRIES[:]
            rng.shuffle(shuffled)
            assert [h.entry.key for h in SearchIndex(shuffled).search("ㅅ", 50).hits] == base


class Test잘림:
    def test_상한을_넘으면_잘렸다고_알린다(self, index: SearchIndex) -> None:
        """FR-024 — 잘린 사실을 숨기면 사용자는 찾는 종목이 없다고 읽는다."""
        outcome = index.search("삼성", 2)
        assert len(outcome.hits) == 2
        assert outcome.truncated is True

    def test_상한과_같으면_잘리지_않았다(self, index: SearchIndex) -> None:
        outcome = index.search("삼성", 5)
        assert len(outcome.hits) == 5
        assert outcome.truncated is False


class Test여러_이름:
    def test_어느_이름으로든_찾는다(self) -> None:
        """미국 종목은 한글명·영문명·티커로 찾는다 (FR-021)."""
        apple = SearchEntry(key=1, names=("애플", "APPLE INC"), codes=("AAPL",),
                            market="NASDAQ", code="AAPL")
        index = SearchIndex([apple])
        for query in ("애플", "ㅇㅍ", "apple", "Apple", "AAPL", "aapl"):
            assert [h.entry.key for h in index.search(query, 20).hits] == [1], query

    def test_코드는_포함으로_찾지_않는다(self) -> None:
        """코드 중간의 숫자로 맞으면 짧은 숫자 검색어가 무관한 종목을 쏟아낸다."""
        index = SearchIndex([kr(1, "삼성전자", "005930")])
        assert index.search("5930", 20).hits == ()


class Test일치_판정:
    @pytest.mark.parametrize(("query", "text", "expected"), [
        ("삼성전자", "삼성전자", "exact"),
        ("ㅅㅅㅈㅈ", "삼성전자", "exact"),
        ("삼성", "삼성전자", "prefix"),
        ("전자", "삼성전자", "contains"),
        ("ㅈㅈ", "삼성전자", "contains"),
        ("삼서", "삼성전자", "prefix"),
        ("전자우", "삼성전자", None),
        ("", "삼성전자", None),
    ])
    def test_표(self, query: str, text: str, expected: str | None) -> None:
        assert match_text(query, text) == expected



# ── 미국 (T067) ──────────────────────────────────────────────────────

def us(key: int, name_ko: str | None, name_en: str, code: str, symbol: str | None = None,
       market: str = "NASDAQ") -> SearchEntry:
    """색인이 만드는 모양 — 한글명·영문명, 목록 티커와 시세 출처 티커."""
    names = tuple(n for n in (name_ko, name_en) if n)
    codes = (code,) if symbol is None or symbol == code else (code, symbol)
    return SearchEntry(key=key, names=names, codes=codes, market=market, code=code)


US = [
    us(1, "애플", "APPLE INC", "AAPL"),
    us(2, "테슬라", "TESLA INC", "TSLA"),
    us(3, "엔비디아", "NVIDIA CORP", "NVDA"),
    us(4, "버크셔 해서웨이 B", "BERKSHIRE HATHAWAY INC", "BRKb", "BRK-B", "NYSE"),
    us(5, None, "ACME WIDGETS CORP", "ACMW", market="AMEX"),
    us(6, "애플릭 디지털", "APPLIED DIGITAL CORP", "APLD"),
]


class Test미국_검색어:
    """quickstart 5 — 애플·ㅇㅍ·apple·AAPL 네 경우 모두 애플이 나온다 (FR-021, SC-002)."""

    @pytest.mark.parametrize("query", ["애플", "ㅇㅍ", "apple", "Apple", "AAPL", "aapl"])
    def test_애플(self, query: str) -> None:
        hits = SearchIndex(US).search(query, 20).hits
        assert hits and hits[0].entry.key == 1, [h.entry.names for h in hits]

    @pytest.mark.parametrize(("query", "key"), [
        ("테슬라", 2), ("ㅌㅅㄹ", 2), ("tesla", 2), ("엔비디아", 3), ("nvda", 3)])
    def test_테슬라_엔비디아(self, query: str, key: int) -> None:
        assert SearchIndex(US).search(query, 20).hits[0].entry.key == key

    def test_한글명이_없으면_영문명과_티커로만_찾는다(self) -> None:
        index = SearchIndex(US)
        assert index.search("acme", 20).hits[0].entry.key == 5
        assert index.search("ACMW", 20).hits[0].entry.key == 5

    def test_클래스_주식을_시세_출처_표기로도_찾는다(self) -> None:
        index = SearchIndex(US)
        for query in ("BRK-B", "brkb", "버크셔"):
            assert index.search(query, 20).hits[0].entry.key == 4, query
