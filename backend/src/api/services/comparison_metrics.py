"""비교 경로의 정규화 블록 (013 T025·T048·T090) — spec FR-011·FR-011a·FR-015, research R13-4·R13-5·
R13-18, data-model 3.

메뉴 요약(그 메뉴의 요약 JSON 함수가 낸 문자열)과 비용 몫(`simulation/comparison_costs`)에서
비교 표의 칸을 만든다. **주 값**(투자 수익·수익률)은 각 메뉴 보드의 규칙 그대로다.

| 갈래 | 주 값 |
|------|-------|
| 주식 일시금·부동산 | 매도 비용이 있고 매도 후 값 둘이 다 있으면 매도 후, 아니면 보유 중 |
| 주식·가상자산 적립식 | 매도 후, 비면 값 없음(물러나지 않는다) |
| 가상자산 일시금·정기예금·정기 적금 | 보유 중 |

화면은 이 값을 보이고 견주기만 한다 — 합·차이를 계산하지 않는다(헌법 원칙 VI).

**순수 함수 모듈이다.** DB·HTTP·저장소·경로 모듈을 부르지 않는다(헌법 원칙 IV).
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

from src.simulation.comparison_costs import CostPart, Costs
from src.simulation.listing_date import ListingDate
from src.simulation.unit_price import PricePoint, UnitPrice

Json = dict[str, object]
Family = Literal["stock_lump", "crypto_lump", "deposit", "realestate", "stock_recurring",
                 "crypto_recurring", "installment"]

#: 평가 환율의 출처 — 외환 매매기준율(001, `FxRate.source`).
FX_SOURCE = "ECOS:731Y001"

_AFTER_SALE_FALLBACK: frozenset[Family] = frozenset({"stock_lump", "realestate"})
_AFTER_SALE_ONLY: frozenset[Family] = frozenset({"stock_recurring", "crypto_recurring"})


@dataclass(frozen=True, slots=True)
class FxInfo:
    """외화 대상의 원화 평가 환율(기준일 행)과 원금 환전(메뉴 응답의 `exchange`)."""

    currency: str
    valuation_rate: Decimal
    valuation_rate_date: dt.date
    exchange: Json | None = None


def _dec(value: Decimal) -> str:
    """금액·비율 문자열 — 지수 표기 없이(`Decimal("0E-12")`는 `"0"`)."""
    return "0" if value == 0 else format(value, "f")


def _text(value: object) -> str | None:
    """요약의 값을 지수 표기 없는 문자열로. 비어 있으면 `None`."""
    if value is None:
        return None
    return _dec(Decimal(str(value)))


def _money(value: Decimal | None) -> str | None:
    return None if value is None else _dec(value)


def _part_json(part: CostPart) -> Json:
    return {"total": _money(part.total),
            "items": [{"kind": i.kind, "amount": _money(i.amount), "inPrincipal": i.in_principal}
                      for i in part.items]}


def costs_json(costs: Costs) -> Json:
    return {"total": _money(costs.total), "reflected": _part_json(costs.reflected),
            "sale": None if costs.sale is None else {**_part_json(costs.sale),
                                                      "blank": costs.blank}}


def _main(family: Family, summary: Json) -> tuple[str, str | None, str | None]:
    """(기준, 투자 수익, 수익률) — 보드 규칙(모듈 머리말 표)."""
    profit, rate = _text(summary.get("profit")), _text(summary.get("returnRate"))
    after_profit = _text(summary.get("profitAfterSale"))
    after_rate = _text(summary.get("returnRateAfterSale"))
    if family in _AFTER_SALE_ONLY:
        if after_profit is None or after_rate is None:
            return "unavailable", None, None
        return "after_sale", after_profit, after_rate
    if (family in _AFTER_SALE_FALLBACK and summary.get("saleCost") is not None
            and after_profit is not None and after_rate is not None):
        return "after_sale", after_profit, after_rate
    if profit is None or rate is None:
        return "unavailable", None, None
    return "holding", profit, rate


def _principal(family: Family, summary: Json, principal_currency: str) -> Json:
    if family == "realestate":
        invested = _text(summary.get("invested"))
        return {"amount": invested, "currency": "KRW", "krw": invested}
    if family in ("stock_recurring", "crypto_recurring", "installment"):
        amount = _text(summary.get("contributed"))
        krw = _text(summary.get("contributedKrw")) or amount
        return {"amount": amount, "currency": principal_currency, "krw": krw}
    amount = _text(summary.get("principal"))
    krw = _text(summary.get("principalKrw")) or amount
    return {"amount": amount, "currency": principal_currency, "krw": krw}


def _current_value(family: Family, summary: Json) -> str | None:
    if family == "realestate":
        return _text(summary.get("value"))
    if family == "deposit":
        # 정기예금 요약에는 잔고 키가 없다 — 원금 + 수익이 계산 모듈의 `balance`다.
        principal, profit = summary.get("principal"), summary.get("profit")
        if principal is None or profit is None:
            return None
        return _dec(Decimal(str(principal)) + Decimal(str(profit)))
    if family == "installment":
        return _text(summary.get("balance"))
    return _text(summary.get("totalKrw"))


def _provisional(family: Family, summary: Json) -> list[str]:
    kinds: list[str] = []
    if family in ("deposit", "installment") and summary.get("provisionalFrom") is not None:
        kinds.append("unpublished_rate")
    if family == "realestate":
        if summary.get("provisional"):
            kinds.append("provisional_price")
        if summary.get("estimated"):
            kinds.append("estimated_price")
    if summary.get("isFinal") is False:
        kinds.append("not_final")
    return kinds


def _fx_json(fx: FxInfo | None) -> Json | None:
    if fx is None:
        return None
    return {"currency": fx.currency, "valuationRate": _dec(fx.valuation_rate),
            "valuationRateDate": fx.valuation_rate_date.isoformat(), "source": FX_SOURCE,
            "exchange": fx.exchange}


def _point_json(point: PricePoint, *, with_missing: bool) -> Json:
    body: Json = {"date": point.date.isoformat(), "value": _money(point.value),
                  "provisional": point.provisional, "estimated": point.estimated}
    if with_missing:
        body["missing"] = point.missing
    return body


def unit_price_json(unit: UnitPrice | None) -> Json | None:
    """단가 등락(반복 2026-10-09 — data-model 3.2). 값은 서버가 계산한 문자열이다 — 화면은
    형식만 입힌다."""
    if unit is None:
        return None
    return {
        "kind": unit.kind, "basis": unit.basis, "currency": unit.currency,
        "start": _point_json(unit.start, with_missing=False),
        "asOf": _point_json(unit.as_of, with_missing=True),
        "change": _money(unit.change), "changeRate": _money(unit.change_rate),
        "split": None if unit.split_ratio is None else {"ratio": unit.split_ratio},
    }


def listing_json(listing: ListingDate | None) -> Json | None:
    """상장일과 기준 (014 반복 2026-10-10f — FR-033, contracts A10). 모르면 `None`."""
    if listing is None:
        return None
    return {"date": listing.date.isoformat(), "basis": listing.basis}


def comparison_block(family: Family, summary: Json, costs: Costs, *,
                     principal_currency: str = "KRW", fx: FxInfo | None = None,
                     unit_price: UnitPrice | None = None,
                     listing: ListingDate | None = None) -> Json:
    """비교 표 한 줄의 칸 — data-model 3. `unit_price`는 반복 2026-10-09의 단가 등락(3.2)이다.

    `listing`은 014 반복 2026-10-10f의 상장일이다 — 주식·가상자산 경로만 넘긴다(예금·부동산 `None`).
    """
    basis, profit, rate = _main(family, summary)
    holding_rate = _text(summary.get("returnRate"))
    return {
        "asOf": summary.get("asOf"),
        "isFinal": summary.get("isFinal"),
        "principal": _principal(family, summary, principal_currency),
        "currentValue": _current_value(family, summary),
        "mainBasis": basis,
        "profit": profit,
        "returnRate": rate,
        "holding": {"profit": _text(summary.get("profit")), "returnRate": holding_rate},
        "costs": costs_json(costs),
        "lineEnd": {"date": summary.get("asOf"), "holdingReturnRate": holding_rate,
                    "afterSaleReturnRate": rate if basis == "after_sale" else None},
        "provisional": _provisional(family, summary),
        "fx": _fx_json(fx),
        "unitPrice": unit_price_json(unit_price),
        "listing": listing_json(listing),
    }
