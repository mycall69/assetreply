"""예금 시뮬레이션 표·보드 (T020) — 008 contracts/rest-api `GET /api/deposit/simulation`.

금액·금리·세율·수익률은 모두 **문자열**이다 — JSON `number`는 IEEE 754다(헌법 원칙 VI). 금액은 원
단위 정수, 금리는 출처 문자열 그대로(`"3.2"`), 수익률은 소수 6자리다. 행은 많아야 한 해에 15줄
남짓이라 **한 번에 모두** 보낸다. **받지 않은 달이 있으면 계산하지 않는다**(202, FR-011).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.services import deposit_simulation as service
from src.api.services.deposit_collect import month_text
from src.db.session import get_session
from src.repository.deposit_rate import rate_text
from src.simulation.deposit_rollover import DepositOutcome, OpenTerm, Row, Term

router = APIRouter(prefix="/api/deposit", tags=["deposit"])

Json = dict[str, object]


def won(value: Decimal) -> str:
    """원 단위 정수 문자열 — 지수 표기 없이."""
    return format(value, "f")


def term_json(term: Term) -> Json:
    return {
        "no": term.no, "joinedOn": term.joined_on.isoformat(),
        "maturesOn": term.matures_on.isoformat(), "rate": rate_text(term.rate),
        "rateMonth": month_text(term.rate_month), "provisional": term.provisional,
        "principal": won(term.principal), "interest": won(term.interest), "tax": won(term.tax),
        "afterTax": won(term.after_tax),
    }


def open_term_json(term: OpenTerm) -> Json:
    return {
        "joinedOn": term.joined_on.isoformat(), "maturesOn": term.matures_on.isoformat(),
        "rate": rate_text(term.rate), "rateMonth": month_text(term.rate_month),
        "principal": won(term.principal), "provisional": term.provisional,
    }


def row_json(row: Row) -> Json:
    return {
        "date": row.date.isoformat(), "kind": row.kind, "rate": rate_text(row.rate),
        "rateMonth": month_text(row.rate_month), "provisional": row.provisional,
        "principal": won(row.principal), "interest": won(row.interest), "tax": won(row.tax),
        "afterTax": won(row.after_tax), "balance": won(row.balance), "profit": won(row.profit),
        "returnRate": format(row.return_rate, "f"),
    }


def summary_json(outcome: DepositOutcome, recheck_failed: tuple[str, str] | None) -> Json:
    s = outcome.summary
    return {
        "principal": won(s.principal), "profit": won(s.profit),
        "returnRate": format(s.return_rate, "f"), "asOf": s.as_of.isoformat(),
        "isFinal": s.is_final,
        "currentTerm": None if s.current_term is None else open_term_json(s.current_term),
        "provisionalFrom": None if s.provisional_from is None else s.provisional_from.isoformat(),
        "stopped": None if s.stopped is None else {
            "date": s.stopped.date.isoformat(), "reason": s.stopped.reason,
            "month": month_text(s.stopped.month)},
        "recheckFailed": None if recheck_failed is None else {
            "kind": recheck_failed[0], "reason": recheck_failed[1]},
    }


@router.get("/simulation", response_model=None)
async def get_simulation(
    session: Annotated[AsyncSession, Depends(get_session)],
    institution: Annotated[str, Query()],
    start: Annotated[str, Query(description="YYYY-MM-DD")],
    principal: Annotated[str, Query(description="원 단위 정수 문자열")],
    principal_currency: Annotated[str | None, Query(alias="principalCurrency")] = None,
    end: Annotated[str | None, Query(description="기본 오늘(한국 시간)")] = None,
) -> Json | JSONResponse:
    """시뮬레이션을 실행하고 표 전체와 보드를 돌려준다."""
    request = service.read_request(institution, start, principal, principal_currency, end)
    result = await service.simulate_or_collect(session, request)
    if not isinstance(result, service.Prepared):
        return JSONResponse(status_code=202, content=result)
    outcome = result.outcome
    return {
        "institution": {"key": request.institution.key, "name": request.institution.name},
        # 설정은 언제든 바뀐다. 결과만 남으면 어느 조건의 수치인지 알 수 없다(FR-031).
        "condition": {"start": request.start.isoformat(), "principal": won(request.principal),
                      "interestTaxRate": format(result.settings.interest_tax_rate, "f")},
        "summary": summary_json(outcome, result.recheck_failed),
        "terms": [term_json(t) for t in outcome.terms],
        "rows": [row_json(r) for r in outcome.rows],
    }
