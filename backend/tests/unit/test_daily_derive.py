"""표의 파생값이 spread_calc와 정확히 일치하는지 (T023).

FR-023·FR-027: 같은 매매기준율·스프레드에 대해 산출 결과가 항상 같아야 한다.
표와 단일 날짜 조회가 다른 계산 경로를 타면 이 보장이 조용히 깨진다. 그래서
`api/services/daily_query.py`는 계산을 **직접 하지 않고** `simulation/`을 호출만 한다
(헌법 원칙 IV).
"""
from __future__ import annotations

from decimal import Decimal

from src.api.services.daily_query import derive_for_row
from src.simulation.spread_calc import SpreadSet, derive_rates

SPREAD = SpreadSet(
    cash_buy=Decimal("0.001800"), cash_sell=Decimal("0.001800"),
    remit_send=Decimal("0.000500"), remit_receive=Decimal("0.000500"))


def test_표의_파생값이_순수함수_결과와_같다() -> None:
    base = Decimal("1354.200000")
    assert derive_for_row(base, SPREAD) == derive_rates(base, SPREAD)


def test_여러_값에_대해_일치한다() -> None:
    for raw in ("1012.300000", "1.000000", "9999.999999", "255.000000"):
        base = Decimal(raw)
        assert derive_for_row(base, SPREAD) == derive_rates(base, SPREAD), raw


def test_스프레드가_0이면_4종이_매매기준율과_같다() -> None:
    zero = SpreadSet(Decimal("0"), Decimal("0"), Decimal("0"), Decimal("0"))
    base = Decimal("1354.200000")
    d = derive_for_row(base, zero)
    assert d.cash_buy == d.cash_sell == d.remit_send == d.remit_receive
