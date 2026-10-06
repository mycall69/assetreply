"""가상자산 매도 비용 (011 T032) — FR-020, research R11-7.

기준일에 모두 판다고 가정한 비용이다. 매도 수수료 = ⌊평가액(원화) × 거래 수수료율⌋(원 미만 버림).
세금은 시행일 규칙 하나다 — 2027-01-01 전이면 0(`not_yet_taxed`), 그날부터는
**비운다**(`outside_rules`). 2027년 세법(22%·250만 원 공제·의제 취득가)은 계산하지 않는다. 0으로
메우면 과세된 기준일에 세금 0이 오류 없이 나온다.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

from src.simulation.crypto_sale_cost import CryptoSaleCost, crypto_sale_cost

D = dt.date.fromisoformat
M = Decimal


def test_수수료는_평가액_곱하기_수수료율의_원_미만_버림이다() -> None:
    cost = crypto_sale_cost(M("4000000.7"), fee_rate=M("0.001"), day=D("2026-10-05"))
    assert cost.fee == M("4000")
    cost = crypto_sale_cost(M("1234567.89"), fee_rate=M("0.0025"), day=D("2026-10-05"))
    assert cost.fee == M("3086")


def test_시행_전_기준일은_세금_0이다() -> None:
    assert crypto_sale_cost(M("4000000"), fee_rate=M("0.001"), day=D("2026-12-31")) == (
        CryptoSaleCost(fee=M("4000"), tax=M("0"), total=M("4000"), tax_kind="not_yet_taxed"))


def test_시행일부터는_세금을_비운다() -> None:
    cost = crypto_sale_cost(M("4000000"), fee_rate=M("0.001"), day=D("2027-01-01"))
    assert cost == CryptoSaleCost(fee=M("4000"), tax=None, total=None, tax_kind="outside_rules")


def test_팔_것이_없으면_비용이_0이다() -> None:
    cost = crypto_sale_cost(M("0"), fee_rate=M("0.001"), day=D("2026-10-05"))
    assert (cost.fee, cost.tax, cost.total) == (M("0"), M("0"), M("0"))
