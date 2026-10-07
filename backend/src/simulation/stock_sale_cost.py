"""주식 매도 수수료·세금 (010 반복 4 FR-030 → 011 FR-013·FR-037, research R10-20·R11-7) — 순수
함수(DB·HTTP 없음, 헌법 원칙 IV).

기준일에 보유 주식을 그 날 종가로 모두 판다고 가정한 비용이다. 보드의 투자 수익·수익률에서 뺀다 —
일자별 표·차트는 보유 중 평가 그대로다.

- 국내(KRX): 매도 세금 = 매도금액 × 국내 매도 세율(증권거래세 + 농어촌특별세 실질). 소액주주 가정 —
  양도소득세 없음
- 해외: 양도소득세 = max(0, 원화 양도차익 − 기본공제) × 세율. 기본공제는 그해 다른 매도가 없다고
  가정한다
- 원화 금액은 **원 미만을 먼저 버린다**(매도금액·취득가·수수료) — 차익과 세금도 원 단위다

**세율·공제는 인자다**(011 FR-037, 명확화 2026-10-06).
설정값(`repository/stock_setting.get_sale_tax` — 기본 0.20%·22%·2,500,000원)이 010 반복 4의 시행일별
법령 표를 대체했다. 모든 기준일에 같은 설정값을 쓰고, 세금을 비우는 갈래가 없다. 세율을 코드에
숨기지 않고 파라미터로 드러낸다 (헌법 원칙 VI).

한계: 국내 ETF(거래세 면제)·국내 상장 해외형 ETF(배당소득 과세)·대주주 양도세·해외 거래소 수수료는
반영하지 않는다.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_FLOOR, Decimal
from typing import Final

TRANSACTION_KIND: Final = "transaction_tax"
CAPITAL_GAINS_KIND: Final = "capital_gains_tax"

_WON = Decimal("1")
_ZERO = Decimal("0")


@dataclass(frozen=True, slots=True)
class SaleCost:
    """매도 비용(원화). 011부터 세금은 늘 값이 있다 — 형은 010 응답 모양(`tax`·`total`이 비는
    자리)을 그대로 둔다."""

    fee: Decimal
    tax: Decimal | None
    total: Decimal | None
    tax_kind: str
    tax_rate: Decimal | None
    gain: Decimal | None
    deduction: Decimal | None
    #: 012 US6(FR-019) — 양도차익의 구성(해외만, 원 미만을 버린 값). `gain = sale_krw −
    #: acquisition_krw − fees_krw`다 — 차익을 만든 그 값들이라
    #: 화면이 따로 빼지 않는다. 매도금액은 보유 주식만(예수금 제외), 취득가는 모든 매수(배당 재투자
    #: 포함), 수수료는 매수 + 매도다.
    sale_krw: Decimal | None = None
    acquisition_krw: Decimal | None = None
    fees_krw: Decimal | None = None


def floor_won(amount: Decimal) -> Decimal:
    """원 미만을 버린다(음수는 더 작은 쪽 — 손실을 줄여 보이지 않는다)."""
    return amount.quantize(_WON, rounding=ROUND_FLOOR)


def domestic_sale_cost(sale_krw: Decimal, *, fee_rate: Decimal, tax_rate: Decimal) -> SaleCost:
    """국내 종목 — 수수료 = 매도금액 × 수수료율, 매도 세금 = 매도금액 × 국내 매도 세율(설정)."""
    fee = floor_won(sale_krw * fee_rate)
    tax = floor_won(sale_krw * tax_rate)
    return SaleCost(fee=fee, tax=tax, total=fee + tax, tax_kind=TRANSACTION_KIND, tax_rate=tax_rate,
                    gain=None, deduction=None)


def foreign_sale_cost(*, sale_krw: Decimal, sell_fee_krw: Decimal, acquisition_krw: Decimal,
                      buy_fees_krw: Decimal, rate: Decimal, deduction: Decimal) -> SaleCost:
    """해외 종목 — 양도차익 = 매도금액 − 취득가 − 매수·매도 수수료(모두 원화, 원 미만 버림). 공제는
    **원화**다."""
    fee = floor_won(sell_fee_krw)
    sale = floor_won(sale_krw)
    acquisition = floor_won(acquisition_krw)
    fees = floor_won(buy_fees_krw) + fee
    gain = sale - acquisition - fees
    tax = floor_won(max(gain - deduction, _ZERO) * rate)
    return SaleCost(fee=fee, tax=tax, total=fee + tax, tax_kind=CAPITAL_GAINS_KIND, tax_rate=rate,
                    gain=gain, deduction=deduction, sale_krw=sale, acquisition_krw=acquisition,
                    fees_krw=fees)
