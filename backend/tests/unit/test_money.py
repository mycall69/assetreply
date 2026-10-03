"""정밀도 규칙 (T005) — 005 data-model 4절, 헌법 원칙 VI.

**참조 구현이 JavaScript `number`로 모든 금액을 계산한다.** 옮기는 과정 전체가 원칙 VI
위반 구간이며, float로 계산해도 오류가 나지 않고 숫자도 그럴듯하다.

통화별 자릿수를 **한 곳에 모으는** 이유는 흩뿌리면 한 군데만 틀려도 그 통화만 조용히
어긋나기 때문이다.
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from src.simulation.money import (
    CURRENCY_SCALE,
    RATE_SCALE,
    buy_quantity,
    quantize_money,
    quantize_rate,
)


class Test통화별_자릿수:
    def test_원화와_엔화는_소수점이_없다(self) -> None:
        """원화·엔화에 소수점 금액은 존재하지 않는다."""
        assert CURRENCY_SCALE["KRW"] == 0
        assert CURRENCY_SCALE["JPY"] == 0

    def test_달러와_유로는_두_자리다(self) -> None:
        assert CURRENCY_SCALE["USD"] == 2
        assert CURRENCY_SCALE["EUR"] == 2

    def test_원화_금액을_정수로_맞춘다(self) -> None:
        assert quantize_money(Decimal("86997.4"), "KRW") == Decimal("86997")

    def test_달러_금액을_두_자리로_맞춘다(self) -> None:
        assert quantize_money(Decimal("1356.1049"), "USD") == Decimal("1356.10")

    def test_알_수_없는_통화는_거절한다(self) -> None:
        """조용히 기본값을 쓰면 그 통화만 다른 자릿수로 계산된다."""
        with pytest.raises(KeyError):
            quantize_money(Decimal("1"), "XXX")


class Test비율_자릿수:
    def test_수익률은_여섯_자리다(self) -> None:
        assert RATE_SCALE == 6
        assert quantize_rate(Decimal("1.3883004999")) == Decimal("1.388300")

    def test_음수_수익률도_같은_자릿수다(self) -> None:
        assert quantize_rate(Decimal("-0.0825123456")) == Decimal("-0.082512")


class Test매수_수량:
    """FR-007a — 수수료를 포함한 총액이 예수금을 넘지 않는 최대 정수."""

    def test_수수료가_없으면_단순_나눗셈의_몫이다(self) -> None:
        assert buy_quantity(Decimal("86997"), Decimal("113500"), Decimal("0")) == 0
        assert buy_quantity(Decimal("300000"), Decimal("113500"), Decimal("0")) == 2

    def test_수수료를_포함한_총액이_예수금을_넘지_않는다(self) -> None:
        # 시가 100, 예수금 201, 수수료 1% → 1주에 101원. 2주는 202원이라 못 산다.
        assert buy_quantity(Decimal("201"), Decimal("100"), Decimal("0.01")) == 1

    def test_수수료_때문에_한_주_줄어드는_경계(self) -> None:
        # 시가 100, 예수금 200, 수수료 0.015% → 2주에 200.03원. 1주만 산다.
        assert buy_quantity(Decimal("200"), Decimal("100"), Decimal("0.00015")) == 1

    def test_예수금이_한_주에_못_미치면_사지_않는다(self) -> None:
        assert buy_quantity(Decimal("99"), Decimal("100"), Decimal("0")) == 0

    def test_수량은_언제나_정수다(self) -> None:
        """FR-007 — 소수점 주식을 만들지 않는다."""
        qty = buy_quantity(Decimal("1000000"), Decimal("113500"), Decimal("0.00015"))
        assert isinstance(qty, int)

    def test_시가가_0이면_사지_않는다(self) -> None:
        """0으로 나누는 경로를 만들지 않는다."""
        assert buy_quantity(Decimal("1000"), Decimal("0"), Decimal("0")) == 0

    def test_예수금이_음수가_될_수_없다(self) -> None:
        """SC-024 — 수량을 시가로만 정하고 수수료를 나중에 빼면 음수가 된다."""
        cash, price, fee = Decimal("200"), Decimal("100"), Decimal("0.00015")
        qty = buy_quantity(cash, price, fee)
        spent = Decimal(qty) * price * (Decimal("1") + fee)
        assert spent <= cash
        assert cash - spent >= 0


class Test분할_반영:
    """FR-010 — 결과가 정수로 떨어지지 않으면 버린다."""

    def test_분할은_보유_주식을_배수로_늘린다(self) -> None:
        from src.simulation.money import apply_split

        assert apply_split(3, 50, 1) == 150

    def test_역분할에서_단수주는_버린다(self) -> None:
        """올리거나 반올림하면 없던 주식이 생긴다."""
        from src.simulation.money import apply_split

        assert apply_split(15, 1, 10) == 1

    def test_분수_비율도_정수로_떨어지지_않는_몫은_버린다(self) -> None:
        """버그 `fractional-split-ratio` — 출처가 준 0.985:1(→197:200)을 그대로 적용한다(FR-010a).

        100주 × 197/200 = 98.5주 → 98주. 반올림하면 없던 주식이 생긴다.
        """
        from src.simulation.money import apply_split

        assert apply_split(100, 197, 200) == 98

    def test_역분할이_딱_떨어지면_그대로다(self) -> None:
        from src.simulation.money import apply_split

        assert apply_split(20, 1, 10) == 2

    def test_보유가_0이면_분할해도_0이다(self) -> None:
        from src.simulation.money import apply_split

        assert apply_split(0, 50, 1) == 0
