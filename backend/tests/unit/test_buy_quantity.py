"""매수 수량과 예수금 (T025) — 005 FR-007a, FR-007b, SC-024, SC-025.

**수량을 시가로만 정하고 수수료를 나중에 빼는 구현은 여기서 걸린다.** 남은 돈보다
수수료가 클 때 예수금이 음수가 되는데, 음수 예수금은 총자산을 줄여 수익률이 틀리면서도
값이 작아 눈에 띄지 않는다.
"""
from __future__ import annotations

import datetime as dt
from decimal import Decimal

from src.simulation.reinvest import Condition, DayBar, DividendOn, simulate

D = dt.date.fromisoformat
FEE = Decimal("0.00015")  # 0.015%


def condition(**over: object) -> Condition:
    base = dict(start=D("2021-08-01"), principal=Decimal("200"), currency="KRW",
                reinvest=True, fee_rate=FEE, tax_rate=Decimal("0.154"),
                reinvest_lag_days=0)  # 지연 0 = 005의 당일 재투자(006 FR-058 이전 동작)
    base.update(over)
    return Condition(**base)  # type: ignore[arg-type]


class Test수수료_포함_총액:
    def test_수수료_때문에_한_주_줄어든다(self) -> None:
        """시가 100, 예수금 200, 수수료 0.015% → 2주는 200.03원이라 1주만 산다."""
        rows = simulate([DayBar(D("2021-08-02"), Decimal("100"))], [], [],
                        condition())
        assert rows[0].bought_shares == 1

    def test_수수료가_0이면_두_주를_산다(self) -> None:
        rows = simulate([DayBar(D("2021-08-02"), Decimal("100"))], [], [],
                        condition(fee_rate=Decimal("0")))
        assert rows[0].bought_shares == 2

    def test_수수료가_예수금에서_빠진다(self) -> None:
        rows = simulate([DayBar(D("2021-08-02"), Decimal("100"))], [], [],
                        condition())
        # 1주 = 100 × 1.00015 = 100.015
        assert rows[0].cash == Decimal("99.985")


class Test예수금_음수_금지:
    def test_초기_매수에서_음수가_되지_않는다(self) -> None:
        """SC-024."""
        for principal in ("100", "150", "200", "99999", "100000"):
            rows = simulate([DayBar(D("2021-08-02"), Decimal("100"))], [], [],
                            condition(principal=Decimal(principal)))
            assert rows[0].cash >= 0, f"원금 {principal}에서 예수금이 음수"

    def test_재투자_매수에서도_음수가_되지_않는다(self) -> None:
        """배당이 작을수록 수수료가 상대적으로 커져 위험한 구간이다."""
        rows = simulate(
            [DayBar(D("2021-08-02"), Decimal("100")),
             DayBar(D("2021-09-01"), Decimal("100")),
             DayBar(D("2021-10-01"), Decimal("100"))],
            [DividendOn(D("2021-09-01"), Decimal("1"))], [],
            condition(principal=Decimal("10000")))
        assert all(r.cash >= 0 for r in rows)

    def test_모든_행에서_음수가_아니다(self) -> None:
        rows = simulate(
            [DayBar(D("2021-08-02"), Decimal("7")),
             DayBar(D("2021-09-01"), Decimal("11")),
             DayBar(D("2021-10-01"), Decimal("3"))],
            [DividendOn(D("2021-09-01"), Decimal("0.5"))], [],
            condition(principal=Decimal("1000")))
        assert all(r.cash >= 0 for r in rows)


class Test수수료_적용_범위:
    def test_재투자_매수에도_수수료가_붙는다(self) -> None:
        """FR-007b — 한쪽만 적용하면 재투자 켬/끔 비교가 수수료만큼 기울어진다."""
        no_fee = simulate(
            [DayBar(D("2021-08-02"), Decimal("100")),
             DayBar(D("2021-09-01"), Decimal("100"))],
            [DividendOn(D("2021-09-01"), Decimal("50"))], [],
            condition(principal=Decimal("1000"), fee_rate=Decimal("0")))
        with_fee = simulate(
            [DayBar(D("2021-08-02"), Decimal("100")),
             DayBar(D("2021-09-01"), Decimal("100"))],
            [DividendOn(D("2021-09-01"), Decimal("50"))], [],
            condition(principal=Decimal("1000"), fee_rate=Decimal("0.5")))
        # 수수료가 50%면 같은 예수금으로 살 수 있는 주식이 줄어든다.
        assert with_fee[0].held_shares < no_fee[0].held_shares

    def test_매수가_없는_행에는_수수료가_붙지_않는다(self) -> None:
        """SC-025의 반대 조건 — 아무 때나 빠지면 예수금이 조용히 줄어든다."""
        rows = simulate(
            [DayBar(D("2021-08-02"), Decimal("100")),
             DayBar(D("2021-09-01"), Decimal("100")),
             DayBar(D("2021-10-01"), Decimal("100"))],
            [], [], condition(principal=Decimal("1000")))
        assert rows[1].cash == rows[2].cash == rows[0].cash
