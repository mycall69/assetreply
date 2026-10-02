"""검색 처리 시간 (T015) — 006 SC-001, research R6-5.

SC-001의 0.5초는 화면 입력 대기 150ms를 **포함한다.** 서버 처리 예산은 그 나머지보다 훨씬
작아야 한다 — 국내·미국을 합친 색인(실측 약 16,700건)을 15,000건 합성 색인으로 흉내 낸다.
"""
from __future__ import annotations

import random
import time

from src.search.match import SearchEntry, SearchIndex

SYLLABLES = "가나다라마바사아자차카타파하삼성전자현대기아엘지에스케이하이닉스바이오로직스금융지주"
LATIN = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def synthetic_index(size: int = 15_000) -> SearchIndex:
    rng = random.Random(42)
    entries: list[SearchEntry] = []
    for i in range(size):
        name = "".join(rng.choice(SYLLABLES) for _ in range(rng.randint(2, 9)))
        if i % 3 == 0:
            name = "".join(rng.choice(LATIN) for _ in range(rng.randint(2, 4))) + name
        names: tuple[str, ...] = (name,)
        if i % 2 == 0:
            en = " ".join("".join(rng.choice(LATIN) for _ in range(rng.randint(3, 8)))
                          for _ in range(rng.randint(1, 4)))
            names = (name, en)
        code = f"{i:06d}"
        entries.append(SearchEntry(key=i, names=names, codes=(code,),
                                   market="KRX" if i % 2 else "NYSE", code=code))
    return SearchIndex(entries)


QUERIES = [
    "ㅅ", "ㅅㅅ", "ㅅㅅㅈㅈ", "ㅎㅇㄴㅅ", "ㄱ", "ㅂㅇ", "ㅈㄱ", "ㄹㅈㅅ",
    "삼", "삼성", "삼성전", "삼성전자", "삼서", "현대", "기아", "하이닉스", "바이오",
    "삼ㅅㅈ", "삼성ㅈ", "현ㄷ", "금융지주", "지주",
    "a", "ab", "abc", "sk", "apple", "kodex", "tiger",
    "0", "00", "005", "005930", "012345", "999",
]


def test_95번째_백분위가_50ms_미만이다() -> None:
    index = synthetic_index()
    durations: list[float] = []
    for i in range(100):
        query = QUERIES[i % len(QUERIES)]
        started = time.perf_counter()
        index.search(query, 20)
        durations.append(time.perf_counter() - started)
    durations.sort()
    p95 = durations[94]
    assert p95 < 0.050, f"p95 {p95 * 1000:.1f}ms"
