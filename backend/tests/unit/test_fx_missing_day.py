"""환율 결측일 (T069) — 005 FR-041c, research R5-6.

**주식 거래일과 환율 고시일은 일치하지 않는다.** 미국 증시가 열린 날이 한국 공휴일이면
그 날짜의 환율이 없다.

가장 가까운 **이전** 고시일을 쓰되 **그 날짜를 함께 돌려준다.** 값을 만들어내는 것이
아니라 "어느 날짜의 값을 썼는지 밝히고 쓰는 것"이라는 점이 원칙 V와의 경계다. 밝히지
않으면 곧바로 위반이다.
"""
from __future__ import annotations

import datetime as dt
from decimal import Decimal

from src.simulation.fx_convert import RateLookup, resolve_rate

D = dt.date.fromisoformat

QUOTES = {
    D("2021-09-30"): Decimal("1184.0"),
    D("2021-10-01"): Decimal("1188.5"),
    D("2021-10-05"): Decimal("1191.0"),
}
LOOKUP = RateLookup(QUOTES)


class Test고시가_있는_날:
    def test_그날_값을_쓴다(self) -> None:
        got = resolve_rate(LOOKUP, D("2021-10-01"))
        assert got == (Decimal("1188.5"), D("2021-10-01"))

    def test_쓴_날짜가_요청한_날짜와_같다(self) -> None:
        _, used = resolve_rate(LOOKUP, D("2021-10-05"))
        assert used == D("2021-10-05")


class Test고시가_없는_날:
    def test_가장_가까운_이전_고시일을_쓴다(self) -> None:
        """10-04는 한국 개천절 대체휴일. 미국 증시는 열렸다."""
        got = resolve_rate(LOOKUP, D("2021-10-04"))
        assert got == (Decimal("1188.5"), D("2021-10-01"))

    def test_쓴_날짜가_드러난다(self) -> None:
        """FR-041c — 밝히지 않으면 원칙 V 위반이다."""
        _, used = resolve_rate(LOOKUP, D("2021-10-04"))
        assert used != D("2021-10-04")
        assert used == D("2021-10-01")

    def test_이후_고시일을_쓰지_않는다(self) -> None:
        """미래 값으로 과거를 평가하면 그날 몰랐던 정보가 섞인다."""
        rate, used = resolve_rate(LOOKUP, D("2021-10-04"))
        assert used < D("2021-10-04")
        assert rate != Decimal("1191.0")


class Test고시가_아예_없는_구간:
    def test_이전_고시일이_없으면_없다고_답한다(self) -> None:
        """값을 만들어내지 않는다. 환산할 수 없다는 사실이 드러나야 한다."""
        assert resolve_rate(LOOKUP, D("2021-01-01")) is None

    def test_빈_조회표도_없다고_답한다(self) -> None:
        assert resolve_rate(RateLookup({}), D("2021-10-01")) is None
