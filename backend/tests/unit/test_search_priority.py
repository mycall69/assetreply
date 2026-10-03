"""검색 동순위의 우선순위 (T006) — 007 FR-004, research R7-6, SC-002.

같은 일치 종류 안에서 `priority`가 작은 항목이 먼저다(코인은 시가총액 순위). 심볼이 겹치는 코인(MAX
5개)을 이름 길이로 정렬하면 작은 코인이 위에 온다. 주식은 `priority`를 주지 않아(기본 0) 006의
순서가 그대로다.
"""
from __future__ import annotations

from src.search.match import SearchEntry, SearchIndex


def entry(key: int, name: str, code: str, priority: int = 0) -> SearchEntry:
    return SearchEntry(key=key, names=(name,), codes=(code,), market="CRYPTO", code=code,
                       priority=priority)


def test_같은_종류면_우선순위가_먼저다() -> None:
    index = SearchIndex([entry(1, "MaxCoin", "MAX", 5359),
                         entry(2, "MAX Exchange Token", "MAX", 763),
                         entry(3, "MAX", "MAX", 3084)])
    # 셋 다 정확 일치(심볼 MAX)다 — 이름 길이가 아니라 시가총액 순위순(#763 → #3084 → #5359)
    assert [h.entry.key for h in index.search("max", 10).hits] == [2, 3, 1]


def test_일치_종류가_우선순위보다_먼저다() -> None:
    index = SearchIndex([entry(1, "Bitcoin Cash", "BCH", 17), entry(2, "Bitcoin", "BTC", 1),
                         entry(3, "Wrapped Bitcoin", "WBTC", 9)])
    assert [h.entry.key for h in index.search("bitcoin", 10).hits] == [2, 1, 3]


def test_우선순위가_같으면_006의_순서다() -> None:
    """주식은 모두 0 — 이름이 짧은 순 → 가나다 → 시장 → 코드."""
    stock = [SearchEntry(key=1, names=("삼성전자우",), codes=("005935",), market="KRX",
                         code="005935"),
             SearchEntry(key=2, names=("삼성전자",), codes=("005930",), market="KRX",
                         code="005930")]
    assert [h.entry.key for h in SearchIndex(stock).search("삼성", 10).hits] == [2, 1]
    assert stock[0].priority == 0
