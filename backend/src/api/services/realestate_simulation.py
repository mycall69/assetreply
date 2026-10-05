"""부동산 시뮬레이션 (009 T038, FR-005~FR-007, FR-010, FR-011, FR-014, FR-023, FR-025~FR-030,
contracts/rest-api).

- 입력: 단지·평형 구분·매입일(오늘 한국 시간 이하)·매입가(선택 — 원 단위 정수, 쉼표 없음)·원금
  통화(주어지면 원화만)
- **받아 둔 시·군·구**가 아니면 202(실거래를 받는다). 받아 둔 시·군·구라도 받을 잠정 달이 있으면 202
  — 다만 오늘(한국
  시간) 그 확인 작업이 실패했으면 받아 둔 거래로 200 + `recheckFailed`(같은 날 202를 되풀이하지
  않는다, 008과 같다). 판정은 단지의 **현재** 시·군·구 코드로 하고, 그 코드가 사라졌으면 409
  `region_retired`
- 계산은 순수 함수(`simulation.apt_holding`)다 — 여기서는 저장된 거래를 그 단지·그 평형으로 골라
  넘기고, 결과를
  계약 모양(금액은 원 정수 문자열, 수익률은 소수 6자리)으로 바꾼다. 결과는 저장하지 않는다
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from src.api.errors import CurrencyNotAllowed, InvalidQuery, StartAfterEnd
from src.api.services.realestate_collect import collected, start_trade_job
from src.api.services.realestate_lists import resolve_complex
from src.config.settings import Settings
from src.db.models import AptComplex
from src.repository import apt_job, apt_region, apt_setting, apt_trade
from src.simulation.apt_area import AreaBucket, UnknownArea, bucket_by_key
from src.simulation.apt_holding import HoldingResult, TaxPayment, simulate_holding
from src.simulation.apt_price import MarketPrice, MonthTotal, Trade, aggregate
from src.simulation.apt_price import provisional_from as provisional_start
from src.simulation.apt_tax import AcquisitionCost
from src.worker.apt_trade_runner import kst_date, plan_months

Json = dict[str, object]
ALLOWED_CURRENCIES = ["KRW"]
ASSUMPTIONS = ["부부 5:5 공동 소유", "1세대 1주택", "세법: 시행일별 표"]
_PRICE = re.compile(r"[1-9]\d{0,14}")
_KST = dt.timedelta(hours=9)


@dataclass(frozen=True, slots=True)
class SimulationQuery:
    complex_id: int
    area: AreaBucket
    buy_date: dt.date
    buy_price: int | None


def parse_query(complex_id: str, area: str, buy_date: str, buy_price: str | None,
                principal_currency: str | None, *, today: dt.date) -> SimulationQuery:
    """질의를 읽는다. 형식이 틀리면 400 — 조용히 고쳐 읽지 않는다(쉼표·0·음수 매입가 포함)."""
    if principal_currency is not None and principal_currency != "KRW":
        raise CurrencyNotAllowed("부동산은 원화(KRW)로만 계산합니다.", ALLOWED_CURRENCIES)
    if not complex_id.isdigit():
        raise InvalidQuery(f"단지 id가 올바르지 않습니다: {complex_id}")
    try:
        bucket = bucket_by_key(area)
    except UnknownArea as exc:
        raise InvalidQuery(str(exc)) from exc
    try:
        day = dt.date.fromisoformat(buy_date)
    except ValueError as exc:
        raise InvalidQuery(f"매입일은 YYYY-MM-DD입니다: {buy_date}") from exc
    if day > today:
        raise StartAfterEnd(today, f"매입일은 오늘({today.isoformat()}) 이전이어야 합니다.")
    price: int | None = None
    if buy_price is not None:
        if not _PRICE.fullmatch(buy_price):
            raise InvalidQuery("매입가는 0보다 큰 원 단위 정수입니다(쉼표 없이).")
        price = int(buy_price)
    return SimulationQuery(int(complex_id), bucket, day, price)


@dataclass(frozen=True, slots=True)
class Gate:
    """202 본문, 또는 계산할 수 있으면 `None`(오늘 확인이 실패했으면 그 종류·사유)."""

    collecting: Json | None
    recheck_failed: tuple[str, str] | None = None


async def judge(session: AsyncSession, lawd_cd: str, *, settings: Settings,
                now: dt.datetime) -> Gate:
    """받을 달이 있으면 수집을 시작해 202. 받아 둔 시·군·구에서 오늘 확인이 실패했으면 200으로
    답한다."""
    if await apt_job.running_job_id(session, "trade", lawd_cd) is None:
        today = kst_date(now)
        state = await apt_region.get_state(session, apt_region.sgg_scope(lawd_cd))
        coverage = await apt_trade.coverage(session, lawd_cd)
        first = state.first_trade_ym if state is not None else None
        if not plan_months(coverage, first, today=today, settings=settings):
            return Gate(None)
        if await collected(session, lawd_cd, settings=settings, now=now):
            since = dt.datetime.combine(today, dt.time()) - _KST
            failed = await apt_job.last_failure_since(session, "trade", lawd_cd, since)
            if failed is not None:
                kind, reason = apt_job.split_error(failed.last_error)
                return Gate(None, (kind or "network", reason or "실거래를 확인하지 못했습니다."))
    started = await start_trade_job(session, lawd_cd, settings=settings, now=now)
    return Gate(started.collecting_body(lawd_cd))


async def _monthly(session: AsyncSession, row: AptComplex,
                   area: AreaBucket) -> dict[dt.date, MonthTotal]:
    trades = [] if row.apt_seq is None else await apt_trade.complex_trades(session, row.apt_seq)
    return aggregate(Trade(t.deal_date, t.amount) for t in trades if area.contains(t.excl_area))


def _money(value: int | None) -> str | None:
    return None if value is None else str(value)


def _rate(value: Decimal | None) -> str | None:
    return None if value is None else format(value, ".6f")


def _month(day: dt.date | None) -> str | None:
    return None if day is None else f"{day:%Y-%m}"


def _basis(price: MarketPrice) -> Json:
    return {"month": _month(price.month), "price": str(price.price), "window": price.window,
            "windowTrades": price.trades, "estimated": price.estimated,
            "provisional": price.provisional}


def _tax(payment: TaxPayment | None) -> Json | None:
    if payment is None:
        return None
    return {"amount": str(payment.amount), "rule": payment.rule_date.isoformat(),
            "installment": payment.installment, "basis": _basis(payment.basis)}


def _acquisition(cost: AcquisitionCost) -> Json:
    return {"acquisitionTax": str(cost.acquisition_tax), "educationTax": str(cost.education_tax),
            "ruralTax": str(cost.rural_tax), "brokerageFee": str(cost.brokerage_fee),
            "total": str(cost.total),
            "rules": {"acquisition": cost.acquisition_rule_from.isoformat(),
                      "brokerage": cost.brokerage_rule_from.isoformat()}}


def render(result: HoldingResult, *, row: AptComplex, umd_name: str, area: AreaBucket,
           ratio: Decimal, recheck_failed: tuple[str, str] | None,
           provisional_from: dt.date) -> Json:
    acquisition = _acquisition(result.acquisition)
    window = result.buy_price_window
    summary = result.summary
    body_summary: Json = {
        "buyPrice": str(result.buy_price), "invested": str(result.invested),
        "propertyTaxTotal": str(summary.property_tax_total),
        "comprehensiveTaxTotal": str(summary.comprehensive_tax_total),
        "holdingTaxTotal": str(summary.holding_tax_total),
        "value": _money(summary.value), "valueMonth": _month(summary.value_month),
        "valueWindow": None if summary.value_price is None else {
            "months": summary.value_price.window, "trades": summary.value_price.trades},
        "estimated": summary.estimated, "provisional": summary.provisional,
        "profit": _money(summary.profit), "returnRate": _rate(summary.return_rate),
        "asOf": summary.as_of.isoformat(), "taxGaps": list(summary.tax_gaps),
        "lastPricedMonth": None if summary.value is not None else _month(
            summary.last_priced_month),
        "provisionalFrom": provisional_from.isoformat(),
    }
    if recheck_failed is not None:
        body_summary["recheckFailed"] = {"kind": recheck_failed[0], "reason": recheck_failed[1]}
    rows: list[Json] = []
    for item in result.rows:
        price = item.price
        rows.append({
            "month": _month(item.month), "trades": item.trades,
            "monthAverage": _money(item.month_average),
            "price": None if price is None else str(price.price),
            "window": None if price is None else price.window,
            "windowTrades": None if price is None else price.trades,
            "estimated": False if price is None else price.estimated,
            "provisional": False if price is None else price.provisional,
            "acquisition": None if item.acquisition is None else acquisition,
            "propertyTax": _tax(item.property_tax),
            "comprehensiveTax": _tax(item.comprehensive_tax),
            "cumulativeCost": str(item.cumulative_cost), "value": _money(item.value),
            "profit": _money(item.profit), "returnRate": _rate(item.return_rate),
        })
    return {
        "complex": {"complexId": row.id, "name": row.name, "umdName": umd_name},
        "area": {"key": area.key, "label": area.label},
        "condition": {
            "buyDate": result.buy_date.isoformat(), "buyPrice": str(result.buy_price),
            "buyPriceSource": result.buy_price_source,
            "buyPriceWindow": None if window is None or result.buy_price_source == "input" else {
                "months": window.window, "trades": window.trades, "estimated": window.estimated},
            "holdingTaxBaseRatio": format(ratio, ".6f"), "assumptions": list(ASSUMPTIONS),
        },
        "acquisition": acquisition, "summary": body_summary, "rows": rows,
    }


async def simulation_response(session: AsyncSession, query: SimulationQuery, *,
                              settings: Settings, now: dt.datetime) -> tuple[int, Json]:
    row = await resolve_complex(session, query.complex_id)
    gate = await judge(session, row.lawd_cd, settings=settings, now=now)
    if gate.collecting is not None:
        return 202, gate.collecting
    ratio = (await apt_setting.get_settings(session)).holding_tax_base_ratio
    result = simulate_holding(
        await _monthly(session, row, query.area), buy_date=query.buy_date,
        buy_price=query.buy_price, area=query.area, today=kst_date(now),
        holding_tax_base_ratio=ratio, provisional_months=settings.apt_trade_provisional_months)
    umd = await apt_region.current(session, row.umd_code)
    return 200, render(result, row=row, umd_name=umd.name if umd is not None else "",
                       area=query.area, ratio=ratio, recheck_failed=gate.recheck_failed,
                       provisional_from=provisional_start(kst_date(now),
                                                          settings.apt_trade_provisional_months))
