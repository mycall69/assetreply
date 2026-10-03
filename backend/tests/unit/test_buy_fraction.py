"""소수 수량 매수 (T022) — 007 FR-026, research R7-7.

`수량 = ⌊예수금 ÷ (시가 × (1 + 수수료율))⌋₈` — 소수 8자리에서 **버린다.** 올리거나 반올림하면
수수료를 포함한 총액이 예수금을 넘어 예수금이 음수가 된다 — 값이 작아 눈에 띄지 않는다(SC-004).
주식의 정수 수량 함수(`buy_quantity`)는 그대로다.
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from src.simulation.money import QUANTITY_PLACES, buy_fraction, buy_quantity

D = Decimal


def test_소수_8자리에서_버린다() -> None:
    # 10,000 ÷ (7,196.39111328125 × 1.001) = 10,000 ÷ 7,203.58750439453125 = 1.388197199506…
    # → 8자리에서 버려 1.38819719 (반올림하면 1.38819720 — 총액이 예수금을 넘는다)
    q = buy_fraction(D("10000"), D("7196.39111328125"), D("0.001"))
    assert q == D("1.38819719")
    assert -q.as_tuple().exponent == QUANTITY_PLACES == 8


def test_총액이_예수금을_넘지_않는다() -> None:
    cash, price, fee = D("10000"), D("7196.39111328125"), D("0.001")
    q = buy_fraction(cash, price, fee)
    assert q * price * (1 + fee) <= cash
    # 한 단위(1e-8)만 더 사도 넘는다 — 최대 수량이다
    assert (q + D("0.00000001")) * price * (1 + fee) > cash


@pytest.mark.parametrize(("cash", "price"), [
    (D("0"), D("100")), (D("-1"), D("100")), (D("100"), D("0")), (D("100"), D("-5"))])
def test_예수금이나_시가가_0_이하면_사지_않는다(cash: Decimal, price: Decimal) -> None:
    assert buy_fraction(cash, price, D("0.001")) == 0


def test_정수_수량_함수는_그대로다() -> None:
    """주식은 정수 수량이다(005 FR-007) — 소수 수량이 주식 경로에 새면 안 된다."""
    assert buy_quantity(D("10000"), D("7196.39111328125"), D("0.001")) == 1
