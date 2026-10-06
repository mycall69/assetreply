"""시뮬레이션 이력 경로 (012 T054) — contracts/rest-api.md 2~7.

`/api/history/settings`를 `/api/history/{asset}`보다 **먼저** 둔다 — 뒤에 두면 `settings`가 자산군
매개변수로 잡혀 404가 된다. 계산·검증은 서비스가
한다(`api/services/history`·`history_conditions`).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Body, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.services import history
from src.api.services.history_conditions import parse_asset
from src.db.session import get_session

router = APIRouter(prefix="/api/history", tags=["history"])

Json = dict[str, object]
Session = Annotated[AsyncSession, Depends(get_session)]


@router.get("/settings")
async def get_retention(session: Session) -> Json:
    """보관 기간. 무기한은 `null`이다."""
    return await history.retention_body(session)


@router.put("/settings")
async def put_retention(session: Session, payload: Annotated[Json, Body()]) -> Json:
    """보관 기간을 저장하고 곧바로 모든 자산군의 기한 지난 항목을 지운다."""
    return await history.put_retention(session, payload)


@router.get("/{asset}")
async def list_history(session: Session, asset: str) -> Json:
    """그 자산군의 목록 — 마지막 실행 내림차순. 기한 지난 항목을 먼저 지운다."""
    return await history.list_history(session, parse_asset(asset))


@router.put("/{asset}")
async def put_history(session: Session, asset: str, payload: Annotated[Json, Body()]) -> Json:
    """실행한 조건을 저장하고 목록을 돌려준다."""
    return await history.put_history(session, parse_asset(asset), payload)


@router.delete("/{asset}")
async def delete_history(
    session: Session, asset: str, id: Annotated[str | None, Query(description="조건 식별자")] = None
) -> Json:  # noqa: A002
    """항목을 지우고 목록을 돌려준다. 없는 식별자도 200이다(멱등)."""
    return await history.delete_history(session, parse_asset(asset), id)


@router.post("/{asset}/import")
async def import_history(session: Session, asset: str, payload: Annotated[Json, Body()]) -> Json:
    """브라우저 옛 이력을 옮긴다. 옮긴 수·합친 수·건너뛴 수와 목록을 돌려준다."""
    return await history.import_history(session, parse_asset(asset), payload)
