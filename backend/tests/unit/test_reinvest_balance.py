"""잔고와 총자산 (T026) — 005 FR-013, SC-003, SC-004.

**예수금을 총자산에서 빼먹으면 수익률이 실제보다 낮게 나온다.** 정수 매수라 예수금은
거의 항상 남으므로 **모든 행에서 조금씩 틀리며**, 한 행도 0이 아니어서 눈에 띄지 않는다.
"""
from __future__ import annotations

import datetime as dt
from decimal import Decimal

from src.simulation.reinvest import Condition, DayBar, simulate

D = dt.date.fromisoformat


def condition(**over: object) -> Condition:
    base = dict(start=D("2021-08-01"), principal=Decimal("86997"), currency="KRW",
                reinvest=True, fee_rate=Decimal("0"), tax_rate=Decimal("0.154"),
                reinvest_lag_days=0)  # 지연 0 = 005의 당일 재투자(006 FR-058 이전 동작)
    base.update(over)
    return Condition(**base)  # type: ignore[arg-type]


BARS = [DayBar(D("2021-08-02"), Decimal("40000")),
        DayBar(D("2021-09-01"), Decimal("50000")),
        DayBar(D("2021-10-01"), Decimal("30000"))]


class Test잔고:
    def test_보유_주식_곱하기_그_행의_시가다(self) -> None:
        """SC-003."""
        for row in simulate(BARS, [], [], condition()):
            assert row.balance == Decimal(row.held_shares) * row.open_price

    def test_예수금을_포함하지_않는다(self) -> None:
        """FR-013 — 잔고와 총자산은 다른 값이다."""
        rows = simulate(BARS, [], [], condition())
        assert rows[0].cash > 0
        assert rows[0].balance != rows[0].balance + rows[0].cash

    def test_보유가_0이면_잔고도_0이다(self) -> None:
        rows = simulate([DayBar(D("2021-08-02"), Decimal("999999"))], [], [],
                        condition())
        assert rows[0].held_shares == 0
        assert rows[0].balance == Decimal("0")


class Test총자산과_수익:
    def test_수익은_잔고_더하기_예수금_빼기_투자금이다(self) -> None:
        """SC-004 — 예수금이 빠지면 모든 행에서 조금씩 틀린다."""
        for row in simulate(BARS, [], [], condition()):
            assert row.profit == row.balance + row.cash - row.principal

    def test_주가가_떨어지면_수익이_음수다(self) -> None:
        rows = simulate(BARS, [], [], condition())
        assert rows[-1].date == D("2021-08-02")  # 최신순이라 마지막이 가장 이르다
        october = next(r for r in rows if r.date == D("2021-10-01"))
        assert october.profit < 0
        assert october.return_rate < 0

    def test_수익률은_수익_나누기_투자금이다(self) -> None:
        for row in simulate(BARS, [], [], condition()):
            assert row.return_rate == (row.profit / row.principal).quantize(
                Decimal("0.000001"))

    def test_투자금이_0이면_수익률을_만들어내지_않는다(self) -> None:
        """0으로 나누는 경로를 두지 않는다."""
        rows = simulate(BARS, [], [], condition(principal=Decimal("0")))
        assert all(r.return_rate == Decimal("0") for r in rows)
