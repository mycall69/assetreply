"""고시 단위 반영 (T045) — 006 FR-042, SC-009, research R6-9.

외환 DB의 엔화는 **100엔당** 값이다. 005는 그 단위를 버려 원금 1,000,000원이 약 110,900엔이 아니라
1,109엔으로 환전됐다(100배). 주식을 한 주도 사지 못하고 수익률은 0%에 가깝게 나와, 그 종목이
움직이지 않았다고 읽힌다.
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from src.simulation.fx_convert import exchange_rate, per_unit, to_foreign


class Test1단위당_값:
    def test_100엔당을_1엔당으로(self) -> None:
        assert per_unit(Decimal("900.000000"), 100) == Decimal("9.000000")

    def test_단위가_1이면_그대로(self) -> None:
        assert per_unit(Decimal("1350.250000"), 1) == Decimal("1350.250000")

    def test_환율_자릿수_6자리를_지킨다(self) -> None:
        assert per_unit(Decimal("905.55"), 100) == Decimal("9.055500")
        assert str(per_unit(Decimal("1000"), 100)) == "10.000000"

    @pytest.mark.parametrize("unit", [0, -100])
    def test_단위가_양수가_아니면_거절한다(self, unit: int) -> None:
        """나눗셈 오류나 부호 반전을 조용히 결과에 섞지 않는다."""
        with pytest.raises(ValueError):
            per_unit(Decimal("900"), unit)

    def test_float를_쓰지_않는다(self) -> None:
        assert isinstance(per_unit(Decimal("900"), 100), Decimal)


def test_원화_100만원은_11만_엔대로_환전된다() -> None:
    """SC-009 — 100엔당 900원, 현금 살 때 스프레드 1.75%, 우대 90%."""
    rate = exchange_rate(per_unit(Decimal("900.000000"), 100), Decimal("0.0175"))
    yen = to_foreign(Decimal("1000000"), rate, "JPY")
    assert Decimal("110000") <= yen < Decimal("112000")
    # 005의 결함 — 단위를 버리면 1,109엔대가 나온다.
    broken = to_foreign(Decimal("1000000"),
                        exchange_rate(Decimal("900.000000"), Decimal("0.0175")), "JPY")
    assert broken < Decimal("1200")
