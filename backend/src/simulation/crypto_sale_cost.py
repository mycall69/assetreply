"""가상자산 매도 비용 (011 T037) — FR-020, research R11-7. 순수 함수(DB·HTTP 없음, 헌법 원칙 IV).

기준일에 보유 수량을 그날 시가로 모두 판다고 가정한 비용이다. 보드의 투자 수익·수익률에서 뺀다 —
일자별 표·차트는 보유 중 평가 그대로다(주식 반복 4와 같다).

- 매도 수수료 = 평가액(원화) × 거래 수수료율, **원 미만 버림**
- 세금은 **시행일 규칙 하나**다. 기준일이 시행일 전이면 0(`not_yet_taxed`)이다. 시행일부터는
  `None`(`outside_rules`)이다
  - 2027년 세법(기타소득 22%·연 250만 원 공제·의제 취득가)은 계산하지 않는다
  - 0으로 메우면 과세된 기준일에 세금 0이 오류 없이 나온다. 시행되면 규칙을 더한다

**시행일은 법령의 사실이다** — 출처가 언제부터 값을 주는지가 아니다. 그래서 날짜 하드코딩 검사의
허용 목록(`tests/unit/test_no_hardcoded_dates.py`의 `_LEGAL_DATE_MODULES`)에 이 파일이 있다
(2026-10-06 승인). 출처의 시작일을 이 파일에 넣지 않는다.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from decimal import ROUND_FLOOR, Decimal
from typing import Final, Literal

#: 가상자산 양도·대여 소득 과세 시행일 — 현행 소득세법상 이날 이후 양도·대여분부터 과세된다. 2026
#: 세제개편안(2026-08-03)에 추가 유예가 없다는 보도가 있다(research R11-7의 근거, 2026-10-06 확인).
TAX_START: Final = dt.date(2027, 1, 1)

CryptoTaxKind = Literal["not_yet_taxed", "outside_rules"]

_WON = Decimal("1")
_ZERO = Decimal("0")


@dataclass(frozen=True, slots=True)
class CryptoSaleCost:
    """매도 비용(원화). 세금을 모르면 `tax`·`total`이 `None`이다 — 0과 "모름"을 구별한다."""

    fee: Decimal
    tax: Decimal | None
    total: Decimal | None
    tax_kind: CryptoTaxKind


def crypto_sale_cost(sale_krw: Decimal, *, fee_rate: Decimal, day: dt.date) -> CryptoSaleCost:
    """`sale_krw`는 기준일 평가액(원화), `day`는 기준일(UTC 어제 이하의 마지막 일봉)이다."""
    fee = (sale_krw * fee_rate).quantize(_WON, rounding=ROUND_FLOOR)
    if day >= TAX_START:
        return CryptoSaleCost(fee=fee, tax=None, total=None, tax_kind="outside_rules")
    return CryptoSaleCost(fee=fee, tax=_ZERO, total=fee, tax_kind="not_yet_taxed")
