"""배당락 행 (T050) — 005 FR-025, FR-026, FR-027."""
from __future__ import annotations

import datetime as dt
from decimal import Decimal

from src.simulation.reinvest import Condition, DayBar, DividendOn, simulate

D = dt.date.fromisoformat


def condition(**over: object) -> Condition:
    base = dict(start=D("2021-08-01"), principal=Decimal("100000"), currency="KRW",
                reinvest=True, fee_rate=Decimal("0"), tax_rate=Decimal("0.154"),
                reinvest_lag_days=0)  # 지연 0 = 005의 당일 재투자(006 FR-058 이전 동작)
    base.update(over)
    return Condition(**base)  # type: ignore[arg-type]


BARS = [DayBar(D("2021-08-02"), Decimal("10000"), Decimal("10000")),
        DayBar(D("2021-09-01"), Decimal("10000"), Decimal("10000")),
        DayBar(D("2021-09-15"), Decimal("10000"), Decimal("10000")),
        DayBar(D("2021-10-01"), Decimal("10000"), Decimal("10000"))]


class Test배당락_행:
    def test_배당이_있는_날에_행이_생긴다(self) -> None:
        rows = simulate(BARS, [DividendOn(D("2021-09-15"), Decimal("300"))], [],
                        condition())
        assert any(r.date == D("2021-09-15") and r.kind == "dividend" for r in rows)

    def test_배당이_없으면_그_날의_행이_없다(self) -> None:
        """9월 15일은 월 첫 거래일도 아니다. 행이 생기면 값을 지어낸 것이다."""
        rows = simulate(BARS, [], [], condition())
        assert all(r.date != D("2021-09-15") for r in rows)

    def test_주당_배당금과_배당율이_채워진다(self) -> None:
        rows = simulate(BARS, [DividendOn(D("2021-09-15"), Decimal("300"))], [],
                        condition())
        row = next(r for r in rows if r.kind == "dividend")
        assert row.dividend_per_share == Decimal("300")
        assert row.dividend_yield == Decimal("0.030000")  # 300 / 10,000

    def test_월_행에는_배당_값이_없다(self) -> None:
        """FR-026 — 0을 넣으면 "배당이 0원"과 "배당이 없음"을 구별할 수 없다."""
        rows = simulate(BARS, [DividendOn(D("2021-09-15"), Decimal("300"))], [],
                        condition())
        for row in rows:
            if row.kind == "month_first":
                assert row.dividend_per_share is None
                assert row.dividend_yield is None

    def test_같은_날_월_행과_배당락_행이_둘_다_생긴다(self) -> None:
        """9월 1일은 월 첫 거래일이자 배당락일이다. 둘은 다른 사실이다."""
        rows = simulate(BARS, [DividendOn(D("2021-09-01"), Decimal("300"))], [],
                        condition())
        same_day = [r for r in rows if r.date == D("2021-09-01")]
        assert {r.kind for r in same_day} == {"month_first", "dividend"}


class Test재투자_반영:
    def test_배당락_행이_재투자까지_반영한_상태다(self) -> None:
        """FR-027 — 배당만 받고 아직 안 산 상태를 보여주면 중간 상태가 남는다."""
        rows = simulate(BARS, [DividendOn(D("2021-09-15"), Decimal("5000"))], [],
                        condition())
        before = next(r for r in rows if r.date == D("2021-09-01"))
        dividend = next(r for r in rows if r.kind == "dividend")
        # 10주 × 5,000원 × (1-0.154) = 42,300원 → 4주 추가
        assert dividend.held_shares > before.held_shares
        assert dividend.bought_shares > 0
