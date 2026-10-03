"""검색 일치·순위 (T031) — 006 FR-020, FR-021, FR-023, FR-024, research R6-5.

**순서가 결정적이어야 한다**(SC-003). 정확 일치 → 앞부분 일치 → 포함. 같은 순위 안에서는 항목의
우선순위(007 — 코인의 시가총액 순위, 주식은 모두 0) → 일치한 이름이 짧은 순 → 정규화한 이름의 코드
포인트 순(가나다·알파벳) → 시장 → 코드. 색인을 만든 순서가 결과에 새어 나오면 같은 검색어가 매번
다른 종목을 맨 위에 둔다.

**빠르게 후보를 거른다.** 이름마다 초성 열을 미리 만들어 두고, 검색어의 초성 열이 들어 있는
위치만 글자 규칙으로 확인한다. 초성 열이 맞지 않는 위치는 어떤 규칙으로도 맞지 않는다 —
검색어의 초성 자모·음절·그 밖의 글자 모두 그 위치 이름 글자의 초성 열 값과 같아야 하기 때문이다.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Final, Literal

from src.search.hangul import char_matches, choseong_string, is_syllable, normalize

MatchKind = Literal["exact", "prefix", "contains"]

_RANK: Final[dict[str, int]] = {"exact": 0, "prefix": 1, "contains": 2}


@dataclass(frozen=True, slots=True)
class SearchEntry:
    """색인 한 항목. `names`는 찾을 이름들(한글명·영문명), `codes`는 코드·티커다."""

    key: int
    names: tuple[str, ...]
    codes: tuple[str, ...]
    market: str
    code: str
    #: 같은 일치 종류 안에서 먼저 볼 순서. 작을수록 먼저다 — 코인은 시가총액 순위(007 FR-004,
    #: research R7-6). 심볼이 겹치는 코인(MAX 5개)을 이름 길이로 정렬하면 작은 코인이 위에 온다.
    #: 주식은 주지 않는다(0) — 006의 순서다.
    priority: int = 0


@dataclass(frozen=True, slots=True)
class Hit:
    entry: SearchEntry
    match: MatchKind
    #: 일치한 이름(또는 코드)의 정규화한 값. 순위의 근거다.
    matched: str


@dataclass(frozen=True, slots=True)
class SearchOutcome:
    hits: tuple[Hit, ...]
    #: 상한에서 잘렸는가 (FR-024).
    truncated: bool


@dataclass(frozen=True, slots=True)
class _Prepared:
    entry: SearchEntry
    #: (정규화한 이름, 초성 열)
    names: tuple[tuple[str, str], ...]
    codes: tuple[str, ...]


def _verify(query: str, name: str, start: int) -> bool:
    """초성 열로 고른 위치를 글자 규칙으로 확인한다. 음절 글자만 다시 보면 된다."""
    last = len(query) - 1
    for j, qch in enumerate(query):
        if is_syllable(qch) and not char_matches(qch, name[start + j], last=j == last):
            return False
    return True


def _match_prepared(query: str, query_cho: str, name: str, name_cho: str) -> MatchKind | None:
    if len(query) > len(name):
        return None
    pos = name_cho.find(query_cho)
    while pos != -1:
        if _verify(query, name, pos):
            if pos == 0:
                return "exact" if len(query) == len(name) else "prefix"
            return "contains"
        pos = name_cho.find(query_cho, pos + 1)
    return None


def match_text(query: str, text: str) -> MatchKind | None:
    """검색어가 이름과 어떻게 맞는가. 둘 다 정규화한 뒤 판정한다."""
    q, t = normalize(query), normalize(text)
    if not q:
        return None
    return _match_prepared(q, choseong_string(q), t, choseong_string(t))


class SearchIndex:
    """메모리 색인. 일치용 문자열을 미리 만든다. DB가 원본이고 이것은 사본이다."""

    __slots__ = ("_items",)

    def __init__(self, entries: Iterable[SearchEntry]) -> None:
        items: list[_Prepared] = []
        for entry in entries:
            names = tuple(
                (n, choseong_string(n))
                for n in (normalize(name) for name in entry.names) if n)
            codes = tuple(c for c in (normalize(code) for code in entry.codes) if c)
            items.append(_Prepared(entry, names, codes))
        self._items = tuple(items)

    def __len__(self) -> int:
        return len(self._items)

    def search(self, query: str, limit: int) -> SearchOutcome:
        q = normalize(query)
        if not q:
            return SearchOutcome((), False)
        q_cho = choseong_string(q)

        ranked: list[tuple[int, int, int, str, str, str, int, Hit]] = []
        for item in self._items:
            best: tuple[int, int, str] | None = None
            best_kind: MatchKind | None = None
            for name, name_cho in item.names:
                kind = _match_prepared(q, q_cho, name, name_cho)
                if kind is not None:
                    candidate = (_RANK[kind], len(name), name)
                    if best is None or candidate < best:
                        best, best_kind = candidate, kind
            for code in item.codes:
                # 코드는 정확·앞부분만 — 중간 숫자로 맞으면 짧은 숫자가 무관한 종목을 쏟아낸다.
                if code.startswith(q):
                    kind = "exact" if code == q else "prefix"
                    candidate = (_RANK[kind], len(code), code)
                    if best is None or candidate < best:
                        best, best_kind = candidate, kind
            if best is not None and best_kind is not None:
                entry = item.entry
                kind_rank, length, matched = best
                ranked.append((kind_rank, entry.priority, length, matched, entry.market,
                               entry.code, entry.key, Hit(entry, best_kind, matched)))

        ranked.sort(key=lambda r: r[:7])
        hits = tuple(r[7] for r in ranked[:limit])
        return SearchOutcome(hits, len(ranked) > limit)
