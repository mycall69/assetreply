"""단지 짝짓기 — 순수 함수 (009 T023, FR-003, FR-032, research R9-3).

단지 목록 자료(`kaptCode`)와 실거래 상세 자료(`aptSeq`)의 같은 단지를 찾는다. 법정동 코드가 같고
다음 중 하나면 같은 단지다:

1. 지번 본번·부번이 같다 — 그 지번의 상대가 하나뿐일 때만(여럿이면 어느 쪽인지 모른다) 2. 정규화한
이름(공백·괄호와 그 안·"아파트" 제거)이 같고 그 이름이 그 동의 **두 자료에서 하나씩뿐**이다

큰 단지는 여러 필지에 걸쳐 자료마다 대표 지번이 다르다 — 헬리오시티는 단지 목록 479, 실거래 913(T001
실측). 같은 동에 같은 이름이 여럿이면 이름으로 짝짓지 않는다 — 다른 단지를 하나로 합치는 것보다 따로
보이는 편이 덜 위험하다. 한 단지는 짝에 한 번만 나온다(행 하나에 `kapt_code`·`apt_seq`가
하나씩이다).

DB·HTTP 없이 단독으로 테스트한다(헌법 원칙 IV). 행을 고치는 일은 `worker/apt_list_runner.py`가 한다.
"""

from __future__ import annotations

import collections
import datetime as dt
import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Protocol

_DROP = re.compile(r"\([^)]*\)|\s")
_APT = "아파트"
_JIBUN = re.compile(r"(\d+)(?:-(\d*))?")


@dataclass(frozen=True, slots=True)
class KaptSide:
    """단지 목록 쪽 — 지번은 기본 정보를 받아야 안다(모르면 None)."""

    kapt_code: str
    name: str
    umd_code: str
    jibun: str | None


@dataclass(frozen=True, slots=True)
class TradeSide:
    """실거래 쪽 — `aptSeq`마다 하나, 가장 최근 거래의 이름·지번."""

    apt_seq: str
    name: str
    umd_code: str
    jibun: str
    build_year: int | None


@dataclass(frozen=True, slots=True)
class Matching:
    #: (kapt_code, apt_seq) — 단지 목록 쪽 입력 순서.
    pairs: tuple[tuple[str, str], ...]
    kapt_only: tuple[str, ...]
    trade_only: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ComplexIds:
    """단지 행의 식별자 — 합칠 행을 고를 때 쓴다."""

    id: int
    kapt_code: str | None
    apt_seq: str | None


class TradeLike(Protocol):
    @property
    def apt_seq(self) -> str: ...
    @property
    def apt_name(self) -> str: ...
    @property
    def umd_code(self) -> str: ...
    @property
    def jibun(self) -> str: ...
    @property
    def deal_date(self) -> dt.date: ...
    @property
    def build_year(self) -> int | None: ...


def normalize_name(name: str) -> str:
    return _DROP.sub("", name).replace(_APT, "")


def jibun_key(jibun: str | None) -> tuple[int, int] | None:
    """`913`·`101-1`·`142-` → (본번, 부번). 산 지번·빈 값은 None — 짝짓기 근거로 쓰지 않는다."""
    found = _JIBUN.fullmatch((jibun or "").strip())
    if found is None:
        return None
    return int(found.group(1)), int(found.group(2) or 0)


def trade_sides(trades: Iterable[TradeLike]) -> tuple[TradeSide, ...]:
    """거래들을 `aptSeq`마다 하나로 — 이름·지번·법정동은 가장 최근 거래의 것(이름이 바뀐 단지)."""
    latest: dict[str, TradeLike] = {}
    for trade in trades:
        seen = latest.get(trade.apt_seq)
        if seen is None or trade.deal_date >= seen.deal_date:
            latest[trade.apt_seq] = trade
    return tuple(TradeSide(t.apt_seq, t.apt_name, t.umd_code, t.jibun, t.build_year)
                 for t in latest.values())


def match_complexes(kapt: Sequence[KaptSide], trade: Sequence[TradeSide], *,
                    fixed: Iterable[tuple[str, str]] = ()) -> Matching:
    """짝짓는다. `fixed`는 이미 한 행인 짝 — 다시 짝짓지 않지만 이름의 유일성을 셀 때는 넣는다."""
    pairs: dict[str, str] = {}
    for kapt_code, apt_seq in fixed:
        pairs[kapt_code] = apt_seq
    taken = set(pairs.values())

    def open_trades() -> list[TradeSide]:
        return [t for t in trade if t.apt_seq not in taken]

    # 1. 지번 — 같은 동, 같은 본번·부번의 상대가 하나뿐일 때
    for side in kapt:
        key = jibun_key(side.jibun)
        if side.kapt_code in pairs or key is None:
            continue
        found = [t for t in open_trades()
                 if t.umd_code == side.umd_code and jibun_key(t.jibun) == key]
        if len(found) == 1:
            pairs[side.kapt_code] = found[0].apt_seq
            taken.add(found[0].apt_seq)

    # 2. 이름 — 그 동의 두 자료에서 하나씩뿐일 때(이미 짝지은 것까지 센다)
    kapt_names = collections.Counter((s.umd_code, normalize_name(s.name)) for s in kapt)
    trade_names = collections.Counter((t.umd_code, normalize_name(t.name)) for t in trade)
    for side in kapt:
        name = (side.umd_code, normalize_name(side.name))
        if side.kapt_code in pairs or kapt_names[name] != 1 or trade_names[name] != 1:
            continue
        found = [t for t in open_trades() if (t.umd_code, normalize_name(t.name)) == name]
        if len(found) == 1:
            pairs[side.kapt_code] = found[0].apt_seq
            taken.add(found[0].apt_seq)

    ordered = tuple((s.kapt_code, pairs[s.kapt_code]) for s in kapt if s.kapt_code in pairs)
    return Matching(
        pairs=ordered,
        kapt_only=tuple(s.kapt_code for s in kapt if s.kapt_code not in pairs),
        trade_only=tuple(t.apt_seq for t in trade if t.apt_seq not in taken),
    )


def plan_merges(rows: Iterable[ComplexIds],
                pairs: Iterable[tuple[str, str]]) -> tuple[tuple[int, int], ...]:
    """짝의 두 식별자가 서로 다른 행에 있으면 (남길 행, 합칠 행) — 먼저 만든 행(작은 id)을 남긴다.

    행을 지우지 않는다 — 합친 행은 `merged_into`로 남는다(이력이 단지 id를 저장한다, FR-032).
    """
    by_kapt = {r.kapt_code: r for r in rows if r.kapt_code is not None}
    by_seq = {r.apt_seq: r for r in [*by_kapt.values(), *rows] if r.apt_seq is not None}
    merges: list[tuple[int, int]] = []
    for kapt_code, apt_seq in pairs:
        left, right = by_kapt.get(kapt_code), by_seq.get(apt_seq)
        if left is None or right is None or left.id == right.id:
            continue
        merges.append((min(left.id, right.id), max(left.id, right.id)))
    return tuple(merges)
