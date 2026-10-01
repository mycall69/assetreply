"""배당 재투자 꺼짐 (T052) — 005 FR-009."""
from __future__ import annotations

import datetime as dt
from decimal import Decimal

from src.simulation.reinvest import Condition, DayBar, DividendOn, simulate

D = dt.date.fromisoformat

BARS = [DayBar(D("2021-08-02"), Decimal("10000")),
        DayBar(D("2021-09-01"), Decimal("10000")),
        DayBar(D("2021-10-01"), Decimal("10000"))]
DIVIDENDS = [DividendOn(D("2021-09-01"), Decimal("1000"))]


def condition(reinvest: bool) -> Condition:
    return Condition(start=D("2021-08-01"), principal=Decimal("100000"),
                     currency="KRW", reinvest=reinvest, fee_rate=Decimal("0"),
                     tax_rate=Decimal("0.154"))


class Test쌓이기만_한다:
    def test_보유_주식이_늘지_않는다(self) -> None:
        rows = simulate(BARS, DIVIDENDS, [], condition(reinvest=False))
        assert all(r.held_shares == 10 for r in rows)

    def test_구매_주식수가_0이다(self) -> None:
        rows = simulate(BARS, DIVIDENDS, [], condition(reinvest=False))
        row = next(r for r in rows if r.kind == "dividend")
        assert row.bought_shares == 0

    def test_예수금이_늘어난다(self) -> None:
        rows = simulate(BARS, DIVIDENDS, [], condition(reinvest=False))
        row = next(r for r in rows if r.kind == "dividend")
        assert row.cash == Decimal("8460.000")

    def test_배당락_행은_여전히_생긴다(self) -> None:
        """재투자를 꺼도 배당은 일어났다. 행이 없으면 그 사실이 사라진다."""
        rows = simulate(BARS, DIVIDENDS, [], condition(reinvest=False))
        assert any(r.kind == "dividend" for r in rows)


class Test켬_끔의_차이:
    def test_보유_주식_수가_다르다(self) -> None:
        """SC-011 — 사용자가 차이를 확인할 수 있어야 한다."""
        on = simulate(
            [DayBar(D("2021-08-02"), Decimal("10000")),
             DayBar(D("2021-09-01"), Decimal("1000"))],
            [DividendOn(D("2021-09-01"), Decimal("1000"))], [],
            condition(reinvest=True))
        off = simulate(
            [DayBar(D("2021-08-02"), Decimal("10000")),
             DayBar(D("2021-09-01"), Decimal("1000"))],
            [DividendOn(D("2021-09-01"), Decimal("1000"))], [],
            condition(reinvest=False))
        assert on[0].held_shares > off[0].held_shares

    def test_총자산은_수수료가_없으면_같다(self) -> None:
        """재투자는 자산의 **형태**를 바꿀 뿐이다 — 현금이 주식이 된다."""
        bars = [DayBar(D("2021-08-02"), Decimal("10000")),
                DayBar(D("2021-09-01"), Decimal("1000"))]
        div = [DividendOn(D("2021-09-01"), Decimal("1000"))]
        on = simulate(bars, div, [], condition(reinvest=True))[0]
        off = simulate(bars, div, [], condition(reinvest=False))[0]
        assert on.balance + on.cash == off.balance + off.cash

    def test_배당이_없으면_결과가_같다(self) -> None:
        """spec Edge Cases — 배당이 한 번도 없는 종목."""
        on = simulate(BARS, [], [], condition(reinvest=True))
        off = simulate(BARS, [], [], condition(reinvest=False))
        assert on == off
