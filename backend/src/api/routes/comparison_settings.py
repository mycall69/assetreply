"""투자 비교 설정 경로 (014 반복 2026-10-13 T216) — contracts A18.

`create_app()`이 이 라우터를 비교 라우터(`/api/comparison/<자산군>/...`)보다 **먼저** 더한다 —
저장한 비교 라우터와 같은 까닭(나중의 경로가 앞 경로를 잡지 않게). 검증·본문은 서비스가
한다(`api/services/comparison_settings`).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Body, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.services import comparison_settings as service
from src.db.session import get_session

router = APIRouter(prefix="/api/comparison/settings", tags=["comparison"])

Json = dict[str, object]
Session = Annotated[AsyncSession, Depends(get_session)]


@router.get("")
async def read_settings(session: Session) -> Json:
    """최대 대상 수 — 저장된 값이 없으면 기본(20). 범위·기본은 상수다."""
    return await service.read(session)


@router.put("")
async def update_settings(session: Session, payload: Annotated[Json, Body()]) -> Json:
    """최대 대상 수를 저장한다. 다음에 투자 비교 화면을 열 때부터 그 한도다(화면이 열 때마다
    읽는다)."""
    return await service.update(session, payload)
