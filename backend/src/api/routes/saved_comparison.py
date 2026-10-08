"""저장한 비교 경로 (013 T073) — contracts/rest-api.md 2~6.

`create_app()`이 이 라우터를 비교 라우터(`/api/comparison/<자산군>/...`)보다 **먼저** 더한다 — 012
`settings`처럼 나중의 경로가 앞 경로를 잡지 않게 한다. 검증·본문은 서비스가 한다
(`api/services/saved_comparison`) — 경로는 저장소 모듈을 넘길 뿐이다.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Body, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.services import saved_comparison as service
from src.db.session import get_session
from src.repository import saved_comparison as repo

router = APIRouter(prefix="/api/comparison/saved", tags=["comparison"])

Json = dict[str, object]
Session = Annotated[AsyncSession, Depends(get_session)]


@router.get("")
async def list_saved(session: Session) -> Json:
    """저장한 비교 목록 — 최근 저장 먼저. 보관 기간이 없다."""
    return await service.list_body(session, repo)


@router.post("", status_code=201)
async def save_comparison(session: Session, payload: Annotated[Json, Body()]) -> Json:
    """조건과 이름을 저장한다 — 늘 새 항목이다. 새 항목과 목록 전체를 돌려준다."""
    return await service.save(session, repo, payload)


@router.delete("/{comparison_id}")
async def delete_comparison(session: Session, comparison_id: int) -> Json:
    """항목을 지우고 남은 목록을 돌려준다. 없는 `id`도 200이다(멱등)."""
    return await service.delete(session, repo, comparison_id)
