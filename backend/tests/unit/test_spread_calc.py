"""파생 환율 산출 테스트 (T060, T061, T062).

FR-023: 매입 방향은 가산, 매도 방향은 차감.
FR-027: 동일 입력에 동일 출력 (재현성).
헌법 원칙 VI: 전 계산 `Decimal`, 반올림은 표시 단계 1회 (research R7).
"""
from __future__ import annotations

from dataclasses import astuple
from decimal import ROUND_HALF_UP, Decimal

import pytest

from src.simulation.spread_calc import DerivedRates, SpreadSet, derive_rates

# contracts/rest-api.md의 예시값 — 손으로 계산해 검증한 참조값
BASE = Decimal("1012.30")
USD_SPREAD = SpreadSet(
    cash_buy=Decimal("0.0018"),
    cash_sell=Decimal("0.0018"),
    remit_send=Decimal("0.0005"),
    remit_receive=Decimal("0.0005"),
)


class Test참조값:
    """1012.30 기준 손계산 결과와 대조한다."""

    def test_현금_살_때는_가산한다(self) -> None:
        # 1012.30 × 1.0018 = 1014.12214 → 1014.12
        assert derive_rates(BASE, USD_SPREAD).cash_buy == Decimal("1014.12")

    def test_현금_팔_때는_차감한다(self) -> None:
        # 1012.30 × 0.9982 = 1010.47786 → 1010.48
        assert derive_rates(BASE, USD_SPREAD).cash_sell == Decimal("1010.48")

    def test_송금_보낼_때는_가산한다(self) -> None:
        # 1012.30 × 1.0005 = 1012.80615 → 1012.81
        assert derive_rates(BASE, USD_SPREAD).remit_send == Decimal("1012.81")

    def test_송금_받을_때는_차감한다(self) -> None:
        # 1012.30 × 0.9995 = 1011.79385 → 1011.79
        assert derive_rates(BASE, USD_SPREAD).remit_receive == Decimal("1011.79")

    def test_매입가가_매도가보다_높다(self) -> None:
        d = derive_rates(BASE, USD_SPREAD)
        assert d.cash_buy > d.cash_sell
        assert d.remit_send > d.remit_receive

    def test_송금_스프레드가_현금보다_좁다(self) -> None:
        d = derive_rates(BASE, USD_SPREAD)
        assert (d.cash_buy - d.cash_sell) > (d.remit_send - d.remit_receive)


class Test스프레드_0:
    """FR-011의 경계 — 스프레드가 0이면 4종이 모두 매매기준율과 같다."""

    ZERO = SpreadSet(Decimal("0"), Decimal("0"), Decimal("0"), Decimal("0"))

    def test_네_값이_모두_기준율과_같다(self) -> None:
        d = derive_rates(BASE, self.ZERO)
        expected = BASE.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        assert d.cash_buy == d.cash_sell == d.remit_send == d.remit_receive == expected


class Test반올림:
    """research R7: 소수 2자리 ROUND_HALF_UP, 중간 반올림 없음."""

    def test_소수_2자리로_반올림한다(self) -> None:
        for value in astuple(derive_rates(BASE, USD_SPREAD)):
            assert value.as_tuple().exponent == -2

    def test_반올림은_사사오입이다(self) -> None:
        # 100 × 1.0005 = 100.05 정확히 → 그대로
        s = SpreadSet(Decimal("0.0005"), Decimal("0"), Decimal("0"), Decimal("0"))
        assert derive_rates(Decimal("100"), s).cash_buy == Decimal("100.05")

    def test_반올림_경계값(self) -> None:
        # 1000 × 1.000005 = 1000.005 → HALF_UP이면 1000.01
        s = SpreadSet(Decimal("0.000005"), Decimal("0"), Decimal("0"), Decimal("0"))
        assert derive_rates(Decimal("1000"), s).cash_buy == Decimal("1000.01")

    def test_중간_반올림을_하지_않는다(self) -> None:
        """기준율을 먼저 2자리로 깎고 계산하면 결과가 달라진다."""
        base = Decimal("1012.304999")
        got = derive_rates(base, USD_SPREAD).cash_buy
        naive = (base.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                 * (Decimal("1") + USD_SPREAD.cash_buy)).quantize(
                     Decimal("0.01"), rounding=ROUND_HALF_UP)
        exact = (base * (Decimal("1") + USD_SPREAD.cash_buy)).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP)
        assert got == exact
        assert got != naive


class Test재현성:
    """FR-027: 동일 입력에 동일 출력."""

    def test_반복_호출이_같은_값을_준다(self) -> None:
        assert derive_rates(BASE, USD_SPREAD) == derive_rates(BASE, USD_SPREAD)

    def test_결과가_전부_Decimal이다(self) -> None:
        """헌법 원칙 VI: float 금지."""
        for value in astuple(derive_rates(BASE, USD_SPREAD)):
            assert isinstance(value, Decimal)

    def test_결과는_불변이다(self) -> None:
        d = derive_rates(BASE, USD_SPREAD)
        with pytest.raises((AttributeError, TypeError)):
            d.cash_buy = Decimal("1")  # type: ignore[misc]


class Test계층_경계:
    def test_simulation은_repository와_api를_임포트하지_않는다(self) -> None:
        """헌법 원칙 IV: DB·HTTP 없이 단독 테스트가 가능해야 한다."""
        import pathlib

        src = pathlib.Path(__file__).resolve().parents[2] / "src" / "simulation"
        for path in src.rglob("*.py"):
            body = path.read_text(encoding="utf-8")
            assert "from src.repository" not in body, f"{path.name}이 repository를 임포트"
            assert "from src.api" not in body, f"{path.name}이 api를 임포트"
            assert "from src.db" not in body, f"{path.name}이 db를 임포트"


def test_DerivedRates가_공개된다() -> None:
    assert DerivedRates is not None
