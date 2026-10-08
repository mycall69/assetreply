"""비교 표의 비용 몫 (013 T024·T047) — spec FR-011, research R13-3, data-model 3.1.

비용은 **기간 전체 비용**이다(013 명확화 4) — 기간 동안 낸 모든 수수료·세금에 기준일에 판다고 가정한
비용을 더한다. 둘로 나눈다.

- **이미 반영된 몫**(`reflected`): 현재 가치에서 이미 빠졌거나(매수 수수료·배당 소득세·이자 소득세)
  투자 원금에 들어 있는(부동산 취득 비용 — `in_principal`) 것
- **매도 가정 몫**(`sale`): 기준일에 판다고 가정한 수수료·세금. 메뉴가 매도를 가정하지 않는 자산군·
  방식(가상자산 일시금·예금)은 없다

메뉴가 비우는 항목(세법 표 밖·과세 시행일 뒤)은 `None`이고 그 몫과 전체의 합도 `None`이다 — 0으로
메우지 않는다(헌법 원칙 V). 원화 환산의 버림은 주식 적립식 `buyFeeTotal`과 같은 규칙이다.

**순수 함수 모듈이다.** `api`·`repository`·`db`를 임포트하지 않는다(헌법 원칙 IV).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal

from src.simulation.stock_sale_cost import floor_won

_ZERO = Decimal("0")


@dataclass(frozen=True, slots=True)
class CostItem:
    #: 항목 종류 — data-model 3.1 표의 글자(`buy_fee`·`dividend_tax`·…)
    kind: str
    #: 원화 금액. 메뉴가 비우는 항목이면 `None`
    amount: Decimal | None
    #: 투자 원금에 들어 있는 비용인가(부동산 취득 비용)
    in_principal: bool = False


@dataclass(frozen=True, slots=True)
class CostPart:
    items: tuple[CostItem, ...]

    @property
    def total(self) -> Decimal | None:
        """항목의 합 — 하나라도 비면 합도 비운다."""
        if any(i.amount is None for i in self.items):
            return None
        return sum((i.amount for i in self.items if i.amount is not None), _ZERO)


@dataclass(frozen=True, slots=True)
class Costs:
    reflected: CostPart
    #: 매도 가정 몫. 메뉴가 매도를 가정하지 않으면 `None`
    sale: CostPart | None = None
    #: 비운 까닭(`outside_rules`·`outside_table` 등). 비운 항목이 없으면 `None`
    blank: str | None = None

    @property
    def total(self) -> Decimal | None:
        reflected = self.reflected.total
        if reflected is None:
            return None
        if self.sale is None:
            return reflected
        sale = self.sale.total
        return None if sale is None else reflected + sale


def krw_sum(amounts: Iterable[tuple[Decimal | None, Decimal | None]], *, domestic: bool) -> Decimal:
    """(금액, 그 행의 매매기준율)의 원화 합 — 원 미만 버림.

    국내(원화 거래)는 금액의 합을, 해외는 금액 × 환율의 합을 버린다. 금액이 없는 행과(해외면) 환율이
    없는 행은 뺀다 — 주식 보드의 매도 비용(`api/services/stock_sale.sale_cost_for`)이 매수 수수료를
    더하는 규칙과 같다.
    """
    if domestic:
        return floor_won(sum((a for a, _ in amounts if a is not None), _ZERO))
    return floor_won(sum((a * r for a, r in amounts if a is not None and r is not None), _ZERO))


def _sale(fee: Decimal | None, tax: Decimal | None, tax_item: str | None,
          blank_kind: str | None) -> tuple[CostPart | None, str | None]:
    if fee is None:
        return None, None
    items = (CostItem("sale_fee", fee), CostItem(tax_item or "sale_tax", tax))
    return CostPart(items), (blank_kind if tax is None else None)


def stock_costs(*, buy_fee: Decimal, dividend_tax: Decimal, sale_fee: Decimal | None,
                sale_tax: Decimal | None, tax_kind: str | None) -> Costs:
    """주식(일시금·적립식) — 반영: 매수 수수료(재투자 매수 포함)·배당 소득세, 매도: 매도 수수료 +
    매도 세금(국내 거래세 `transaction_tax` / 해외 양도소득세 `capital_gains_tax`).

    매도 비용이 없으면(기준일 상태가 없음) 매도 몫이 없다. 세금을 모르면 비우고 까닭은 `tax_kind`다.
    """
    reflected = CostPart((CostItem("buy_fee", buy_fee), CostItem("dividend_tax", dividend_tax)))
    sale, blank = _sale(sale_fee, sale_tax, tax_kind, tax_kind)
    return Costs(reflected, sale, blank)


def crypto_costs(*, buy_fee: Decimal, sale_fee: Decimal | None = None,
                 sale_tax: Decimal | None = None, tax_kind: str | None = None) -> Costs:
    """가상자산 — 반영: 매수 수수료. 매도 몫은 적립식만(`sale_fee`를 줄 때) — 일시금은 메뉴가 매도를
    가정하지 않는다(012 US5). 시행일 뒤 세금은 비우고 까닭은 `tax_kind`(`outside_rules`)다."""
    reflected = CostPart((CostItem("buy_fee", buy_fee),))
    sale, blank = _sale(sale_fee, sale_tax, "crypto_tax", tax_kind)
    return Costs(reflected, sale, blank)


def deposit_costs(*, matured_taxes: Iterable[Decimal], open_tax: Decimal) -> Costs:
    """예금(정기예금·정기 적금) — 반영: 끝난 회차·만기 계약의 이자 소득세 합과 진행 중 회차·계약의
    경과 이자 소득세(평가액에서 이미 뺀 몫). 매도 몫이 없다."""
    matured = sum(matured_taxes, _ZERO)
    return Costs(CostPart((CostItem("interest_tax_matured", matured),
                           CostItem("interest_tax_open", open_tax))))


def realestate_costs(*, acquisition_tax: Decimal, education_tax: Decimal, rural_tax: Decimal,
                     brokerage_buy: Decimal, property_tax: Decimal, comprehensive_tax: Decimal,
                     sale_brokerage: Decimal | None, income_tax: Decimal | None,
                     local_tax: Decimal | None, sale_kind: str | None) -> Costs:
    """부동산 — 반영: 취득 비용 넷(투자 원금에 포함)·재산세·종부세, 매도: 매도 중개 보수·양도소득세·
    지방소득세. 평가액을 몰라 매도비용이 없으면 매도 몫이 없다. 세법 표 밖이면 세금을 비우고 까닭은
    `sale_kind`다."""
    reflected = CostPart((
        CostItem("acquisition_tax", acquisition_tax, in_principal=True),
        CostItem("education_tax", education_tax, in_principal=True),
        CostItem("rural_tax", rural_tax, in_principal=True),
        CostItem("brokerage_buy", brokerage_buy, in_principal=True),
        CostItem("property_tax", property_tax),
        CostItem("comprehensive_tax", comprehensive_tax)))
    if sale_brokerage is None:
        return Costs(reflected)
    sale = CostPart((CostItem("brokerage_sale", sale_brokerage),
                     CostItem("transfer_income_tax", income_tax),
                     CostItem("transfer_local_tax", local_tax)))
    blank = sale_kind if income_tax is None or local_tax is None else None
    return Costs(reflected, sale, blank)
