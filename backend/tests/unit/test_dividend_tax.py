"""배당 소득세 (T053) — 005 FR-016, data-model `stock_dividend`.

**저장은 세전이다.** 세율은 설정이라 바뀌며, 세후를 저장하면 세율을 바꿨을 때 과거
행이 낡아 FR-017이 요구하는 재산출이 불가능해진다.
"""
from __future__ import annotations

import datetime as dt
from decimal import Decimal

from src.simulation.reinvest import Condition, DayBar, DividendOn, simulate

D = dt.date.fromisoformat
BARS = [DayBar(D("2021-08-02"), Decimal("10000")),
        DayBar(D("2021-09-01"), Decimal("10000"))]
DIVIDENDS = [DividendOn(D("2021-09-01"), Decimal("1000"))]


def condition(tax: str) -> Condition:
    return Condition(start=D("2021-08-01"), principal=Decimal("100000"),
                     currency="KRW", reinvest=False, fee_rate=Decimal("0"),
                     tax_rate=Decimal(tax))


def cash_after_dividend(tax: str) -> Decimal:
    rows = simulate(BARS, DIVIDENDS, [], condition(tax))
    return next(r for r in rows if r.kind == "dividend").cash


class Test세율_적용:
    def test_기본_세율_15_4퍼센트(self) -> None:
        # 10주 × 1,000 × (1 - 0.154) = 8,460
        assert cash_after_dividend("0.154") == Decimal("8460.000")

    def test_세율이_0이면_전액이다(self) -> None:
        assert cash_after_dividend("0") == Decimal("10000")

    def test_세율을_바꾸면_결과가_달라진다(self) -> None:
        """FR-017 — 설정 변경이 결과에 반영되는 근거다."""
        assert cash_after_dividend("0.154") != cash_after_dividend("0.22")

    def test_세율이_높을수록_받는_돈이_적다(self) -> None:
        assert cash_after_dividend("0.22") < cash_after_dividend("0.154")


class Test세전_저장의_귀결:
    def test_같은_배당에_다른_세율을_적용할_수_있다(self) -> None:
        """세후를 저장했다면 이 테스트가 성립하지 않는다 — 과거 행이 낡는다."""
        same_dividend = DIVIDENDS
        low = simulate(BARS, same_dividend, [], condition("0.1"))
        high = simulate(BARS, same_dividend, [], condition("0.3"))
        low_cash = next(r for r in low if r.kind == "dividend").cash
        high_cash = next(r for r in high if r.kind == "dividend").cash
        assert low_cash > high_cash
