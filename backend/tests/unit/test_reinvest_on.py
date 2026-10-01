"""배당 재투자 켜짐 (T051) — 005 FR-008, FR-027."""
from __future__ import annotations

import datetime as dt
from decimal import Decimal

from src.simulation.reinvest import Condition, DayBar, DividendOn, simulate

D = dt.date.fromisoformat


def condition(**over: object) -> Condition:
    base = dict(start=D("2021-08-01"), principal=Decimal("100000"), currency="KRW",
                reinvest=True, fee_rate=Decimal("0"), tax_rate=Decimal("0.154"))
    base.update(over)
    return Condition(**base)  # type: ignore[arg-type]


BARS = [DayBar(D("2021-08-02"), Decimal("10000")),
        DayBar(D("2021-09-01"), Decimal("10000"))]


class Test세후_배당:
    def test_세율이_적용된다(self) -> None:
        """저장은 세전이다. 세후를 저장하면 세율을 바꿨을 때 과거 행이 낡는다."""
        rows = simulate(BARS, [DividendOn(D("2021-09-01"), Decimal("1000"))], [],
                        condition(reinvest=False))
        row = next(r for r in rows if r.kind == "dividend")
        # 10주 × 1,000 × (1 - 0.154) = 8,460
        assert row.cash == Decimal("8460.000")

    def test_세율이_0이면_전액이_들어온다(self) -> None:
        rows = simulate(BARS, [DividendOn(D("2021-09-01"), Decimal("1000"))], [],
                        condition(reinvest=False, tax_rate=Decimal("0")))
        row = next(r for r in rows if r.kind == "dividend")
        assert row.cash == Decimal("10000")


class Test그날_시가로_산다:
    def test_예수금_전액으로_정수_매수한다(self) -> None:
        """FR-008 — 배당락일 당일 시가로 산다."""
        rows = simulate(
            [DayBar(D("2021-08-02"), Decimal("10000")),
             DayBar(D("2021-09-01"), Decimal("2000"))],
            [DividendOn(D("2021-09-01"), Decimal("1000"))], [], condition())
        row = next(r for r in rows if r.kind == "dividend")
        # 10주 × 1,000 × 0.846 = 8,460 → 2,000원짜리 4주
        assert row.bought_shares == 4
        assert row.held_shares == 14
        assert row.cash == Decimal("460.000")

    def test_배당이_한_주_값에_못_미치면_쌓인다(self) -> None:
        rows = simulate(BARS, [DividendOn(D("2021-09-01"), Decimal("10"))], [],
                        condition())
        row = next(r for r in rows if r.kind == "dividend")
        assert row.bought_shares == 0
        assert row.cash > 0

    def test_기존_예수금도_함께_쓴다(self) -> None:
        """"예수금 전액"이다. 배당금만 쓰면 남은 돈이 영영 놀게 된다."""
        # 원금 100,500으로 10,000원짜리 10주 → 예수금 500
        rows = simulate(
            [DayBar(D("2021-08-02"), Decimal("10000")),
             DayBar(D("2021-09-01"), Decimal("1000"))],
            [DividendOn(D("2021-09-01"), Decimal("100"))], [],
            condition(principal=Decimal("100500")))
        row = next(r for r in rows if r.kind == "dividend")
        # 배당 10주 × 100 × 0.846 = 846. 예수금 500 + 846 = 1,346 → 1,000원짜리 1주
        assert row.bought_shares == 1


class Test배당이_없을_때:
    def test_배당_이벤트가_없으면_재투자도_없다(self) -> None:
        rows = simulate(BARS, [], [], condition())
        assert all(r.kind == "month_first" for r in rows)

    def test_매수_전_배당은_반영하지_않는다(self) -> None:
        """시작일 이전에는 보유가 0이라 받을 배당도 없다."""
        rows = simulate(
            [DayBar(D("2021-07-01"), Decimal("10000")),
             DayBar(D("2021-08-02"), Decimal("10000"))],
            [DividendOn(D("2021-07-01"), Decimal("1000"))], [],
            condition(start=D("2021-08-01")))
        assert all(r.kind == "month_first" for r in rows)
