"""주식 매도 수수료·세금 (010 반복 4, FR-030, research R10-20) — 순수 함수(DB·HTTP 없음, 헌법 원칙
IV).

기준일에 보유 주식을 그 날 종가로 모두 판다고 가정한 비용이다. 보드의 투자 수익·수익률에서 뺀다 —
일자별 표·차트는 보유 중 평가 그대로다.

- 국내(KRX): 증권거래세 = 매도금액 × 그 날의 실질 세율(농어촌특별세 포함). 소액주주 가정 —
  양도소득세 없음
- 해외: 양도소득세 = max(0, 원화 양도차익 − 기본공제) × 세율. 기본공제는 그해 다른 매도가 없다고
  가정한다
- 원화 금액은 **원 미만을 먼저 버린다**(매도금액·취득가·수수료) — 차익과 세금도 원 단위다

**세율 표 밖 날짜는 세금을 비운다**(`outside_table`). 가까운 해의 세율로 메우면 틀린 세금이
그럴듯하게 보인다(헌법 원칙 V — 009 세법 표와 같은 규칙). 세법이 바뀌면 규칙을 더하고 현행 규칙의
끝을 닫는다. 표는 웹 검색으로 확인한 범위만 둔다(research R10-20 — 2024년 0.18%는 직접 확인하지
못했다).

한계: 국내 ETF(거래세 면제)·국내 상장 해외형 ETF(배당소득 과세)·대주주 양도세·해외 거래소 수수료는
반영하지 않는다.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from decimal import ROUND_FLOOR, Decimal
from typing import Final

#: 국내 상장주식 증권거래세 실질 세율 — (시행일, 세율). 시행일 오름차순. 코스피(거래세 +
#: 농어촌특별세 0.15%)와 코스닥의 실질 세율은 이 기간 같다.
TRANSACTION_TAX: Final[tuple[tuple[dt.date, Decimal], ...]] = (
    (dt.date(2023, 1, 1), Decimal("0.0020")),
    (dt.date(2024, 1, 1), Decimal("0.0018")),
    (dt.date(2025, 1, 1), Decimal("0.0015")),
    (dt.date(2026, 1, 1), Decimal("0.0020")),
)

#: 해외주식 양도소득세 — (시행일, 세율(지방소득세 포함), 연간 기본공제).
CAPITAL_GAINS: Final[tuple[tuple[dt.date, Decimal, Decimal], ...]] = (
    (dt.date(2023, 1, 1), Decimal("0.22"), Decimal("2500000")),
)

TRANSACTION_KIND: Final = "transaction_tax"
CAPITAL_GAINS_KIND: Final = "capital_gains_tax"
OUTSIDE_KIND: Final = "outside_table"

_WON = Decimal("1")
_ZERO = Decimal("0")


@dataclass(frozen=True, slots=True)
class SaleCost:
    """매도 비용(원화). 세금을 모르면(표 밖) `tax`·`total`이 `None`이다 — 0이 아니다."""

    fee: Decimal
    tax: Decimal | None
    total: Decimal | None
    tax_kind: str
    tax_rate: Decimal | None
    gain: Decimal | None
    deduction: Decimal | None


def floor_won(amount: Decimal) -> Decimal:
    """원 미만을 버린다(음수는 더 작은 쪽 — 손실을 줄여 보이지 않는다)."""
    return amount.quantize(_WON, rounding=ROUND_FLOOR)


def transaction_tax_rate(day: dt.date) -> Decimal | None:
    """그 날의 증권거래세 실질 세율. 표 밖이면 `None`."""
    found: Decimal | None = None
    for start, rate in TRANSACTION_TAX:
        if day >= start:
            found = rate
    return found


def _capital_gains_rule(day: dt.date) -> tuple[Decimal, Decimal] | None:
    found: tuple[Decimal, Decimal] | None = None
    for start, rate, deduction in CAPITAL_GAINS:
        if day >= start:
            found = (rate, deduction)
    return found


def domestic_sale_cost(sale_krw: Decimal, *, fee_rate: Decimal, day: dt.date) -> SaleCost:
    """국내 종목 — 수수료 = 매도금액 × 수수료율, 증권거래세 = 매도금액 × 그 날 세율."""
    fee = floor_won(sale_krw * fee_rate)
    rate = transaction_tax_rate(day)
    if rate is None:
        return SaleCost(fee=fee, tax=None, total=None, tax_kind=OUTSIDE_KIND, tax_rate=None,
                        gain=None, deduction=None)
    tax = floor_won(sale_krw * rate)
    return SaleCost(fee=fee, tax=tax, total=fee + tax, tax_kind=TRANSACTION_KIND, tax_rate=rate,
                    gain=None, deduction=None)


def foreign_sale_cost(*, sale_krw: Decimal, sell_fee_krw: Decimal, acquisition_krw: Decimal,
                      buy_fees_krw: Decimal, day: dt.date) -> SaleCost:
    """해외 종목 — 양도차익 = 매도금액 − 취득가 − 매수·매도 수수료(모두 원화, 원 미만 버림)."""
    fee = floor_won(sell_fee_krw)
    rule = _capital_gains_rule(day)
    if rule is None:
        return SaleCost(fee=fee, tax=None, total=None, tax_kind=OUTSIDE_KIND, tax_rate=None,
                        gain=None, deduction=None)
    rate, deduction = rule
    gain = floor_won(sale_krw) - floor_won(acquisition_krw) - floor_won(buy_fees_krw) - fee
    tax = floor_won(max(gain - deduction, _ZERO) * rate)
    return SaleCost(fee=fee, tax=tax, total=fee + tax, tax_kind=CAPITAL_GAINS_KIND, tax_rate=rate,
                    gain=gain, deduction=deduction)
