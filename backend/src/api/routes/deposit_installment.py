"""정기 적금 표·보드·시계열 (011 T048) — contracts/rest-api §3. FR-022~FR-032.

정기예금 경로(`/api/deposit/simulation`)와 **따로 둔다**(research R11-10) — 정기예금의 조회
문자열과 응답 모양은 008의 테스트가 정확히 고정한다.

금액·금리·세율·수익률은 모두 **문자열**이다(헌법 원칙 VI). 금액은 원 단위 정수, 금리는 출처 문자열
그대로(`"3.2"`), 수익률은 소수 6자리다. 해당이 없으면 키를 두지 않는다 — 0과 "없음"을 구별한다. 행은
한 번에 모두 보낸다(20년 약 500행 — 008과 같다). **받지 않은 달이 있으면 계산하지 않는다**(202).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.services import deposit_installment as service
from src.api.services.deposit_collect import month_text
from src.api.services.recurring_series import InstallmentPoint, build_installment_series
from src.api.services.series_query import DEFAULT_MAX_POINTS
from src.db.session import get_session
from src.repository.deposit_rate import rate_text
from src.simulation.installment_ladder import (
    InstallmentContract,
    LadderDeposit,
    LadderOutcome,
    LadderRow,
)

router = APIRouter(prefix="/api/deposit", tags=["deposit"])

Json = dict[str, object]


def won(value: Decimal) -> str:
    """원 단위 정수 문자열 — 지수 표기 없이."""
    return format(value, "f")


def contract_json(c: InstallmentContract) -> Json:
    return {
        "no": c.no, "joinedOn": c.joined_on.isoformat(), "maturesOn": c.matures_on.isoformat(),
        "rate": rate_text(c.rate), "rateMonth": month_text(c.rate_month),
        "provisional": c.provisional, "monthly": won(c.monthly), "paid": c.paid,
        "interest": won(c.interest), "tax": won(c.tax), "afterTax": won(c.after_tax),
        "amount": won(c.amount),
    }


def deposit_json(d: LadderDeposit) -> Json:
    return {
        "no": d.no, "joinedOn": d.joined_on.isoformat(), "maturesOn": d.matures_on.isoformat(),
        "rate": rate_text(d.rate), "rateMonth": month_text(d.rate_month),
        "provisional": d.provisional, "principal": won(d.principal),
        "fromDeposit": won(d.from_deposit), "fromInstallment": won(d.from_installment),
        "interest": won(d.interest), "tax": won(d.tax), "afterTax": won(d.after_tax),
    }


def row_json(row: LadderRow) -> Json:
    body: Json = {
        "date": row.date.isoformat(), "kind": row.kind, "contractNo": row.contract_no,
        "provisional": row.provisional, "contributed": won(row.contributed),
        "installmentValue": won(row.installment_value), "depositValue": won(row.deposit_value),
        "balance": won(row.balance), "profit": won(row.profit),
        "returnRate": format(row.return_rate, "f"),
    }
    if row.installment_no is not None:
        body["installmentNo"] = row.installment_no
    if row.rate is not None:
        body["rate"] = rate_text(row.rate)
    if row.rate_month is not None:
        body["rateMonth"] = month_text(row.rate_month)
    amounts = {"amount": row.amount, "interest": row.interest, "tax": row.tax,
               "afterTax": row.after_tax, "fromDeposit": row.from_deposit,
               "fromInstallment": row.from_installment}
    body.update({k: won(v) for k, v in amounts.items() if v is not None})
    return body


def summary_json(outcome: LadderOutcome, recheck_failed: tuple[str, str] | None) -> Json:
    s = outcome.summary
    current = s.current_installment
    held = s.current_deposit
    return {
        "contributed": won(s.contributed), "installments": s.installments,
        "interestTotal": won(s.interest_total), "taxTotal": won(s.tax_total),
        "afterTaxTotal": won(s.after_tax_total),
        "installmentAfterTax": won(s.installment_after_tax),
        "depositAfterTax": won(s.deposit_after_tax),
        "installmentValue": won(s.installment_value), "depositValue": won(s.deposit_value),
        "balance": won(s.balance), "profit": won(s.profit),
        "returnRate": format(s.return_rate, "f"), "asOf": s.as_of.isoformat(),
        "isFinal": s.is_final,
        "currentInstallment": None if current is None else {
            "no": current.no, "joinedOn": current.joined_on.isoformat(),
            "maturesOn": current.matures_on.isoformat(), "rate": rate_text(current.rate),
            "rateMonth": month_text(current.rate_month), "provisional": current.provisional,
            "paid": current.paid},
        "currentDeposit": None if held is None else {
            "no": held.no, "joinedOn": held.joined_on.isoformat(),
            "maturesOn": held.matures_on.isoformat(), "rate": rate_text(held.rate),
            "rateMonth": month_text(held.rate_month), "provisional": held.provisional,
            "principal": won(held.principal)},
        "provisionalFrom": None if s.provisional_from is None else s.provisional_from.isoformat(),
        "stopped": None if s.stopped is None else {
            "date": s.stopped.date.isoformat(), "reason": s.stopped.reason,
            "month": month_text(s.stopped.month)},
        "recheckFailed": None if recheck_failed is None else {
            "kind": recheck_failed[0], "reason": recheck_failed[1]},
    }


@router.get("/installment-simulation", response_model=None)
async def get_installment_simulation(
    session: Annotated[AsyncSession, Depends(get_session)],
    institution: Annotated[str, Query()],
    start: Annotated[str, Query(description="YYYY-MM-DD — 첫 적금 가입일")],
    amount: Annotated[str, Query(description="월 납입액. 원 단위 정수 문자열")],
    end: Annotated[str | None, Query(description="기본 오늘(한국 시간)")] = None,
) -> Json | JSONResponse:
    """적금 사다리를 실행하고 표 전체와 보드를 돌려준다."""
    request = service.read_request(institution, start, amount, end)
    result = await service.simulate_or_collect(session, request)
    if not isinstance(result, service.PreparedInstallment):
        return JSONResponse(status_code=202, content=result)
    outcome = result.outcome
    return {
        "institution": {"key": request.institution.key, "name": request.institution.name},
        # 설정·출처 항목은 바뀐다. 결과만 남으면 어느 조건의 수치인지 알 수 없다(008 FR-031).
        "condition": {
            "product": "installment", "start": request.start.isoformat(),
            "amount": won(request.monthly),
            "interestTaxRate": format(result.settings.interest_tax_rate, "f"),
            "installmentItem": request.option.description,
            "depositItem": request.institution.description,
        },
        "summary": summary_json(outcome, result.recheck_failed),
        "contracts": [contract_json(c) for c in outcome.contracts],
        "deposits": [deposit_json(d) for d in outcome.deposits],
        "rows": [row_json(r) for r in outcome.rows],
    }


def point_json(p: InstallmentPoint) -> Json:
    """금리가 없는 점은 `null`과 사유(010 FR-011). 정기예금 금리가 없으면 키를 두지 않는다."""
    body: Json = {"date": p.date.isoformat(), "balance": won(p.balance),
                  "returnRate": format(p.return_rate, "f"), "principal": won(p.principal),
                  "price": None if p.price is None else rate_text(p.price)}
    if p.price_missing is not None:
        body["priceMissing"] = p.price_missing
    if p.deposit_rate is not None:
        body["depositRate"] = rate_text(p.deposit_rate)
    return body


@router.get("/installment-simulation/series", response_model=None)
async def get_installment_series(
    session: Annotated[AsyncSession, Depends(get_session)],
    institution: Annotated[str, Query()],
    start: Annotated[str, Query(description="YYYY-MM-DD")],
    amount: Annotated[str, Query(description="월 납입액. 원 단위 정수 문자열")],
    end: Annotated[str | None, Query(description="기본 오늘(한국 시간)")] = None,
    max_points: Annotated[int, Query(alias="maxPoints", ge=2)] = DEFAULT_MAX_POINTS,
) -> Json | JSONResponse:
    """표와 같은 조건으로 행 날짜와 계산 끝의 시계열을 돌려준다(008 시계열과 같은 모양)."""
    request = service.read_request(institution, start, amount, end)
    result = await service.simulate_or_collect(session, request)
    if not isinstance(result, service.PreparedInstallment):
        return JSONResponse(status_code=202, content=result)
    series = build_installment_series(
        result.outcome, start=request.start, installment_rates=result.installment_rates,
        installment_latest=result.installment_latest, deposit_rates=result.deposit_rates,
        deposit_latest=result.deposit_latest, max_points=max_points)
    return {
        "from": series.start.isoformat(),
        "to": series.end.isoformat(),
        "principalCurrency": "KRW",
        "basisCurrency": "KRW",
        # 가격은 그 달 발표 **적금** 금리(연 %). 통화가 아니라 단위라 `priceCurrency`는 비운다.
        "priceKind": "installment_rate",
        "priceCurrency": None,
        "downsampled": series.downsampled,
        "algorithm": "lttb",
        "sourcePointCount": series.source_point_count,
        "points": [point_json(p) for p in series.points],
        "gaps": [],
        "provisionalFrom": (None if series.provisional_from is None
                            else series.provisional_from.isoformat()),
    }
