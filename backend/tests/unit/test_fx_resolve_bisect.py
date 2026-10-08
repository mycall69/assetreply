"""환율 찾기의 이분 탐색 (013 T004) — research R13-13, SC-004, SC-009.

`resolve_rate`가 그날 고시가 없을 때 모든 날짜를 훑던 것을 이분 탐색으로 바꾼다.
돌려주는 값(환율, 쓴 날짜)은 옛 방식과 같아야 한다 — 다르면 메뉴의 평가 값이 바뀐다(FR-020).

옛 방식의 참조 구현을 이 파일에 둔다. 무작위 날짜는 시드를 고정한다.
"""

from __future__ import annotations

import datetime as dt
import random
from decimal import Decimal

from src.simulation.fx_convert import RateLookup, resolve_rate

D = dt.date.fromisoformat


def reference(by_date: dict[dt.date, Decimal], on: dt.date) -> tuple[Decimal, dt.date] | None:
    """옛 방식 — 정확 일치, 없으면 모든 이전 고시일 가운데 가장 늦은 날."""
    exact = by_date.get(on)
    if exact is not None:
        return exact, on
    earlier = [d for d in by_date if d < on]
    if not earlier:
        return None
    used = max(earlier)
    return by_date[used], used


def quotes(seed: int, days: int = 900) -> dict[dt.date, Decimal]:
    """주말과 무작위 공휴일을 비운 고시 — 삽입 차례도 섞는다(사전 차례에 기대지 않는다)."""
    rng = random.Random(seed)
    start = D("2018-01-01")
    picked: list[tuple[dt.date, Decimal]] = []
    for offset in range(days):
        day = start + dt.timedelta(days=offset)
        if day.weekday() >= 5 or rng.random() < 0.06:
            continue
        rate = Decimal(1100 + rng.randint(0, 300)) + Decimal(rng.randint(0, 99)) / 100
        picked.append((day, rate))
    rng.shuffle(picked)
    return dict(picked)


class Test옛_방식과_같다:
    def test_무작위_날짜에서_환율과_쓴_날짜가_같다(self) -> None:
        for seed in (1, 7, 42):
            by_date = quotes(seed)
            lookup = RateLookup(by_date)
            first = min(by_date)
            last = max(by_date)
            probe = first - dt.timedelta(days=10)
            while probe <= last + dt.timedelta(days=10):
                assert resolve_rate(lookup, probe) == reference(by_date, probe), probe
                probe += dt.timedelta(days=1)

    def test_정확_일치는_그날이다(self) -> None:
        lookup = RateLookup({D("2024-01-02"): Decimal("1300"), D("2024-01-05"): Decimal("1310")})
        assert resolve_rate(lookup, D("2024-01-05")) == (Decimal("1310"), D("2024-01-05"))

    def test_두_고시일_사이는_앞_고시일이다(self) -> None:
        lookup = RateLookup({D("2024-01-02"): Decimal("1300"), D("2024-01-05"): Decimal("1310")})
        assert resolve_rate(lookup, D("2024-01-04")) == (Decimal("1300"), D("2024-01-02"))

    def test_마지막_고시일_뒤는_마지막_고시일이다(self) -> None:
        lookup = RateLookup({D("2024-01-02"): Decimal("1300"), D("2024-01-05"): Decimal("1310")})
        assert resolve_rate(lookup, D("2024-02-01")) == (Decimal("1310"), D("2024-01-05"))

    def test_이후_고시일은_쓰지_않는다(self) -> None:
        lookup = RateLookup({D("2024-01-05"): Decimal("1310")})
        assert resolve_rate(lookup, D("2024-01-04")) is None

    def test_고시가_없으면_None이다(self) -> None:
        assert resolve_rate(RateLookup({}), D("2024-01-04")) is None


class Test생성:
    def test_사전_하나로_만든다(self) -> None:
        # `api/services/stock_fx.py:80`처럼 위치 인자 사전 하나로 만든다 — 호출부는 그대로다.
        lookup = RateLookup({D("2024-01-02"): Decimal("1300")})
        assert lookup.by_date == {D("2024-01-02"): Decimal("1300")}

    def test_정렬된_날짜를_함께_든다(self) -> None:
        # 이분 탐색의 재료 — 만들 때 한 번 정렬한다(찾을 때마다 훑지 않는다).
        by_date = quotes(3)
        assert RateLookup(by_date).dates == tuple(sorted(by_date))
