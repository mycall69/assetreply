"""같은 날 이벤트 (T054) — 005 spec Assumptions, Edge Cases.

**분할을 먼저 적용하고 배당을 계산한다.** 배당은 분할 후 주식 수에 붙는다. 순서가
바뀌면 받는 배당금이 배수로 달라지는데, 값은 그럴듯하고 오류도 나지 않는다.
"""
from __future__ import annotations

import datetime as dt
from decimal import Decimal

from src.simulation.reinvest import (
    Condition,
    DayBar,
    DividendOn,
    SplitOn,
    simulate,
)

D = dt.date.fromisoformat


def condition(**over: object) -> Condition:
    base = dict(start=D("2021-08-01"), principal=Decimal("100000"), currency="KRW",
                reinvest=False, fee_rate=Decimal("0"), tax_rate=Decimal("0"),
                reinvest_lag_days=0)  # 지연 0 = 005의 당일 재투자(006 FR-058 이전 동작)
    base.update(over)
    return Condition(**base)  # type: ignore[arg-type]


BARS = [DayBar(D("2021-08-02"), Decimal("10000"), Decimal("10000")),
        DayBar(D("2021-09-01"), Decimal("1000"), Decimal("1000"))]


class Test분할이_먼저다:
    def test_배당이_분할_후_주식_수에_붙는다(self) -> None:
        rows = simulate(
            BARS,
            [DividendOn(D("2021-09-01"), Decimal("100"))],
            [SplitOn(D("2021-09-01"), 10, 1)],
            condition())
        row = next(r for r in rows if r.kind == "dividend")
        # 10주 → 분할로 100주 → 100주 × 100원 = 10,000원
        assert row.held_shares == 100
        assert row.cash == Decimal("10000")

    def test_순서가_반대였다면_배당이_10분의_1이다(self) -> None:
        """이 값이 나오면 순서가 뒤집힌 것이다 — 오류 없이 값만 틀린다."""
        rows = simulate(
            BARS,
            [DividendOn(D("2021-09-01"), Decimal("100"))],
            [SplitOn(D("2021-09-01"), 10, 1)],
            condition())
        row = next(r for r in rows if r.kind == "dividend")
        assert row.cash != Decimal("1000")


class Test같은_날_여러_배당:
    def test_합산해_하나로_다룬다(self) -> None:
        """spec Assumptions — 행이 둘이 되면 어느 것이 그날의 배당인지 알 수 없다."""
        rows = simulate(
            BARS,
            [DividendOn(D("2021-09-01"), Decimal("100")),
             DividendOn(D("2021-09-01"), Decimal("200"))],
            [], condition())
        same_day = [r for r in rows
                    if r.date == D("2021-09-01") and r.kind == "dividend"]
        assert len(same_day) == 1
        assert same_day[0].dividend_per_share == Decimal("300")
        assert same_day[0].cash == Decimal("3000")  # 10주 × 300


class Test분할만_있는_날:
    def test_배당_없는_분할은_행을_만들지_않는다(self) -> None:
        """분할은 보유 수를 바꿀 뿐 그날의 사건으로 표에 남지 않는다."""
        rows = simulate(BARS, [], [SplitOn(D("2021-08-10"), 2, 1)], condition())
        assert all(r.date != D("2021-08-10") for r in rows)

    def test_그래도_보유_수에는_반영된다(self) -> None:
        rows = simulate(BARS, [], [SplitOn(D("2021-08-10"), 2, 1)], condition())
        assert next(r for r in rows if r.date == D("2021-09-01")).held_shares == 20
