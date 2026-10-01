"""초기 환전 (T067) — 005 FR-019, FR-020.

**우대의 적용 대상은 스프레드다.** 90% 우대는 스프레드의 90%를 깎는다는 뜻이며,
결과적으로 스프레드의 10%만 적용된다.

방향을 반대로 잡으면(스프레드를 10%만 깎는 것으로) 환전 금액이 **조용히 달라진다.**
오류도 나지 않고 자릿수도 비슷해 검산하지 않으면 알 수 없다.
"""
from __future__ import annotations

from decimal import Decimal

from src.simulation.fx_convert import SPREAD_DISCOUNT, exchange_rate

BASE = Decimal("1300")
CASH_BUY_SPREAD = Decimal("0.0175")  # 1.75%


class Test우대_적용:
    def test_스프레드의_10퍼센트만_적용된다(self) -> None:
        """1,300 × (1 + 0.0175 × 0.1) = 1,302.275"""
        assert exchange_rate(BASE, CASH_BUY_SPREAD) == Decimal("1302.275000")

    def test_우대_비율이_90퍼센트다(self) -> None:
        assert SPREAD_DISCOUNT == Decimal("0.9")

    def test_우대가_없으면_스프레드_전액이다(self) -> None:
        assert exchange_rate(BASE, CASH_BUY_SPREAD, discount=Decimal("0")) == Decimal(
            "1322.750000")

    def test_우대가_100퍼센트면_매매기준율이다(self) -> None:
        assert exchange_rate(BASE, CASH_BUY_SPREAD, discount=Decimal("1")) == Decimal(
            "1300.000000")


class Test방향_오류_감지:
    def test_우대를_반대로_잡으면_값이_다르다(self) -> None:
        """스프레드의 10%만 깎는 것(= 90% 적용)과 구별되어야 한다."""
        correct = exchange_rate(BASE, CASH_BUY_SPREAD)
        reversed_discount = exchange_rate(
            BASE, CASH_BUY_SPREAD, discount=Decimal("0.1"))
        assert correct != reversed_discount
        assert correct < reversed_discount  # 우대가 클수록 싸게 산다

    def test_환전_환율은_언제나_매매기준율보다_크거나_같다(self) -> None:
        """현금을 **사는** 것이므로 가산이다. 차감하면 방향이 뒤집힌 것이다."""
        assert exchange_rate(BASE, CASH_BUY_SPREAD) >= BASE


class Test환전_금액:
    def test_원금을_종목_통화로_바꾼다(self) -> None:
        from src.simulation.fx_convert import to_foreign

        # 1,000,000원 ÷ 1,302.275 = 767.89...
        got = to_foreign(Decimal("1000000"), exchange_rate(BASE, CASH_BUY_SPREAD), "USD")
        assert got == Decimal("767.89")

    def test_통화_자릿수로_맞춘다(self) -> None:
        from src.simulation.fx_convert import to_foreign

        # 엔화에 소수점 금액은 존재하지 않는다.
        got = to_foreign(Decimal("1000000"), Decimal("9.5"), "JPY")
        assert got == Decimal("105263")
