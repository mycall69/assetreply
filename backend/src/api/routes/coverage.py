"""수집 커버리지 조회 엔드포인트 — `GET /api/fx/coverage` (T054).

FR-004·FR-005: 통화별로 어느 구간까지 수집이 완료됐는지와 실제 최초 제공일을 제시한다.
최초 제공일은 수집 중 발견되어 기록된 값이다 (research R3).
"""

from __future__ import annotations

import datetime as dt
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Currency
from src.db.session import get_session
from src.repository.coverage import list_coverage
from src.repository.fx_rate import oldest_stale_provisional

router = APIRouter(prefix="/api/fx", tags=["fx"])

Json = dict[str, object]


@router.get("/coverage")
async def get_coverage_endpoint(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Json:
    rows = await list_coverage(session)
    # 오늘이 지났는데도 잠정으로 남은 레코드 (FR-043a). 확정 전환이 안 일어난 신호다.
    stale = await oldest_stale_provisional(session, today=dt.date.today())
    first_dates = {
        c.code: c.first_available_date
        for c in (await session.execute(select(Currency))).scalars()
    }
    def _first(code: str) -> str | None:
        d = first_dates.get(code)
        return d.isoformat() if d is not None else None

    return {"coverage": [{
        "currency": r.currency_code,
        "coveredFrom": r.covered_from.isoformat(),
        "coveredThrough": r.covered_through.isoformat(),
        "firstAvailableDate": _first(r.currency_code),
        "lastUpdatedAt": r.last_updated_at.isoformat(),
        # 값이 없을 때는 키를 넣지 않는다. 정상 상태에 빈 객체를 두면 화면이
        # 존재 여부가 아니라 내용을 검사해야 한다.
        **({"staleProvisional": {"date": stale[r.currency_code].isoformat()}}
           if r.currency_code in stale else {}),
    } for r in rows]}
