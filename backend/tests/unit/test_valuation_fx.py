"""평가 환산 (T068) — 005 FR-041b, SC-021.

**초기 환전과 다른 환율이다.** 초기 환전은 실제로 돈을 바꾸는 1회 행위라 현금 살 때
환율에 우대가 붙고, 평가는 **값어치를 재는 것**이라 매매기준율을 쓴다.

섞으면 잔고가 매수 스프레드만큼 크게 나오는데 값은 그럴듯하다.
"""
from __future__ import annotations

from decimal import Decimal

from src.simulation.fx_convert import exchange_rate, to_principal

BASE = Decimal("1300")
CASH_BUY_SPREAD = Decimal("0.0175")


class Test매매기준율을_쓴다:
    def test_스프레드가_붙지_않는다(self) -> None:
        """SC-021 — 평가에 매수 스프레드를 얹으면 잔고가 실제보다 크게 나온다."""
        assert to_principal(Decimal("100"), BASE, "KRW") == Decimal("130000")

    def test_초기_환전_환율과_다르다(self) -> None:
        bought_at = exchange_rate(BASE, CASH_BUY_SPREAD)
        assert to_principal(Decimal("100"), BASE, "KRW") != to_principal(
            Decimal("100"), bought_at, "KRW")

    def test_평가가_환전보다_작다(self) -> None:
        """같은 수량을 샀다 바로 팔면 스프레드만큼 손해다 — 그것이 정상이다."""
        bought_at = exchange_rate(BASE, CASH_BUY_SPREAD)
        assert to_principal(Decimal("100"), BASE, "KRW") < to_principal(
            Decimal("100"), bought_at, "KRW")


class Test자릿수:
    def test_원화는_정수로_맞춘다(self) -> None:
        assert to_principal(Decimal("100.5"), Decimal("1300.4"), "KRW") == Decimal(
            "130690")

    def test_달러는_두_자리로_맞춘다(self) -> None:
        assert to_principal(Decimal("100"), Decimal("1.2345"), "USD") == Decimal(
            "123.45")


class Test환율이_1인_경우:
    def test_같은_통화면_값이_그대로다(self) -> None:
        """FR-023 — 환전이 일어나지 않는다."""
        assert to_principal(Decimal("12345"), Decimal("1"), "KRW") == Decimal("12345")
