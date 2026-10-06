"""주식 매도 수수료·세금 (010 반복 4, T069) — FR-030, research R10-20. 순수 함수 — DB·HTTP 없음(헌법
원칙 IV).

기준일에 보유 주식을 모두 판다고 가정한 비용이다.

- 국내(KRX): 수수료 = 매도금액 × 매매 수수료율, 증권거래세 = 매도금액 × 그 날의 세율(시행일별 표 —
  2026-01-01부터 0.20%)
- 해외: 양도소득세 = max(0, 원화 양도차익 − 250만 원) × 22%, 양도차익 = 원화 매도금액 − 원화 취득가
  − 매수·매도 수수료
- 원화 금액은 원 미만을 버린다. **표 밖 날짜는 세금을 비운다** — 가까운 해의 세율로 메우면 틀린
  세금이 그럴듯하게 보인다(헌법 원칙 V)
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest

from src.simulation.stock_sale_cost import (
    domestic_sale_cost,
    foreign_sale_cost,
    transaction_tax_rate,
)

D = dt.date.fromisoformat
M = Decimal


@pytest.mark.parametrize(
    ("day", "rate"),
    [
        ("2022-12-31", None),
        ("2023-01-01", "0.0020"),
        ("2023-12-31", "0.0020"),
        ("2024-01-01", "0.0018"),
        ("2025-01-01", "0.0015"),
        ("2025-12-31", "0.0015"),
        ("2026-01-01", "0.0020"),
        ("2026-10-02", "0.0020"),
    ],
)
def test_증권거래세는_그_날의_시행_세율이다(day: str, rate: str | None) -> None:
    assert transaction_tax_rate(D(day)) == (None if rate is None else M(rate))


class Test국내:
    def test_수수료와_증권거래세는_원_미만을_버린다(self) -> None:
        cost = domestic_sale_cost(M("56304000"), fee_rate=M("0.000150"), day=D("2026-10-02"))
        # 56,304,000 × 0.015% = 8,445.6 → 8,445, × 0.20% = 112,608
        assert (cost.fee, cost.tax, cost.total) == (M("8445"), M("112608"), M("121053"))
        assert (cost.tax_kind, cost.tax_rate, cost.gain, cost.deduction) == (
            "transaction_tax",
            M("0.0020"),
            None,
            None,
        )

    def test_매도금액에_소수가_있어도_원화_금액은_정수다(self) -> None:
        cost = domestic_sale_cost(M("1234567.89"), fee_rate=M("0.000150"), day=D("2025-03-04"))
        assert (cost.fee, cost.tax) == (M("185"), M("1851"))  # 185.18…, 1,851.85…

    def test_표_밖_날짜는_세금을_비운다(self) -> None:
        cost = domestic_sale_cost(M("56304000"), fee_rate=M("0.000150"), day=D("2021-11-30"))
        assert (cost.fee, cost.tax, cost.total, cost.tax_kind, cost.tax_rate) == (
            M("8445"),
            None,
            None,
            "outside_table",
            None,
        )


class Test해외:
    def test_공제를_넘는_차익의_22퍼센트다(self) -> None:
        cost = foreign_sale_cost(
            sale_krw=M("53289965"),
            sell_fee_krw=M("7993.49"),
            acquisition_krw=M("10000000"),
            buy_fees_krw=M("1500.3"),
            day=D("2026-10-02"),
        )
        # 원화 금액마다 원 미만을 먼저 버린다 — 차익 = 53,289,965 − 10,000,000 − 1,500 − 7,993 =
        # 43,280,472 세금 = (43,280,472 − 2,500,000) × 22% = 8,971,703.84 → 8,971,703
        assert (cost.gain, cost.deduction, cost.tax_rate) == (
            M("43280472"),
            M("2500000"),
            M("0.22"),
        )
        assert (cost.fee, cost.tax, cost.total) == (M("7993"), M("8971703"), M("8979696"))
        assert cost.tax_kind == "capital_gains_tax"

    def test_차익이_공제_이하면_세금이_없다(self) -> None:
        cost = foreign_sale_cost(
            sale_krw=M("12000000"),
            sell_fee_krw=M("1800"),
            acquisition_krw=M("10000000"),
            buy_fees_krw=M("1500"),
            day=D("2026-10-02"),
        )
        assert (cost.gain, cost.tax, cost.total) == (M("1996700"), M("0"), M("1800"))

    def test_손실이면_세금이_없다(self) -> None:
        cost = foreign_sale_cost(
            sale_krw=M("8000000"),
            sell_fee_krw=M("1200"),
            acquisition_krw=M("10000000"),
            buy_fees_krw=M("1500"),
            day=D("2026-10-02"),
        )
        assert (cost.gain, cost.tax, cost.total) == (M("-2002700"), M("0"), M("1200"))

    def test_표_밖_날짜는_세금을_비운다(self) -> None:
        cost = foreign_sale_cost(
            sale_krw=M("53289965"),
            sell_fee_krw=M("8000"),
            acquisition_krw=M("10000000"),
            buy_fees_krw=M("1500"),
            day=D("2022-06-30"),
        )
        assert (cost.fee, cost.tax, cost.total, cost.tax_kind) == (
            M("8000"),
            None,
            None,
            "outside_table",
        )
