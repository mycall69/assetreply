"""주식 보드의 매도 수수료·세금 입력 (010 반복 4, FR-030) — 계산 결과에서 순수 함수의 입력을 고른다.

매도 대상은 **기준일 상태**(`SimulationResult.latest` — 표의 마지막 행이 아니다)이고 매도금액은 그
상태의 잔고 (보유 × 종가)다. 해외 취득가는 표의 행마다 매수 수량 × 시가 × 그 행의 매매기준율의
합이다 — 분할은 수량만 바꾸고 취득가 합은 그대로이고, 배당 재투자 매수도 취득이다. 계산은
`simulation/stock_sale_cost`가 한다.

011 FR-037 — 세율·공제는 설정값(`SaleTaxSettings`)이다. 010 반복 4의 시행일별 법령 표를
대체한다(모든 기준일에 같은 값).
"""

from __future__ import annotations

from decimal import Decimal

from src.api.services.stock_simulation import SimulationResult
from src.repository.stock_setting import SaleTaxSettings
from src.simulation.stock_sale_cost import SaleCost, domestic_sale_cost, foreign_sale_cost

DOMESTIC_MARKET = "KRX"
_ZERO = Decimal("0")


def sale_cost_for(result: SimulationResult, *, market: str, fee_rate: Decimal,
                  sale_tax: SaleTaxSettings) -> SaleCost | None:
    """기준일에 모두 판다고 가정한 비용. 기준일 상태가 없거나 해외인데 환율을 모르면 `None`."""
    latest = result.latest
    if latest is None or result.as_of is None:
        return None
    balance = latest.row.balance
    if market == DOMESTIC_MARKET:
        return domestic_sale_cost(balance, fee_rate=fee_rate, tax_rate=sale_tax.domestic)
    if latest.fx_rate is None:
        return None
    acquisition = sum((c.row.bought_shares * c.row.open_price * c.fx_rate
                       for c in result.rows if c.row.bought_shares > 0 and c.fx_rate is not None),
                      _ZERO)
    buy_fees = sum((c.row.trade_fee * c.fx_rate for c in result.rows
                    if c.row.trade_fee is not None and c.fx_rate is not None), _ZERO)
    return foreign_sale_cost(
        sale_krw=balance * latest.fx_rate, sell_fee_krw=balance * fee_rate * latest.fx_rate,
        acquisition_krw=acquisition, buy_fees_krw=buy_fees, rate=sale_tax.foreign_rate,
        deduction=sale_tax.foreign_deduction)
