"""대시보드 기준금리 경로 (014 반복 2026-10-11d T208) — FR-040~FR-042, contracts A14~A17.

- `GET /api/dashboard/rates` — 칸(은행 다섯, 늘 차례대로). **DB만 읽는다** — 출처를 부르지 않는다
- `GET /api/dashboard/rates/{bank}` — 금리 모달(결정 전부). 없는 은행은 404
- `GET /api/dashboard/rates/{bank}/commentary` — 변화 까닭(출처가 실패해도 200). 서비스가 없으면(앱
  수명 밖) 503
- `POST /api/dashboard/rates/collect` — 다시 시도: 수집 워커를 곧바로 깨운다(202). 이 요청에서
  출처를 부르지 않는다
"""

from __future__ import annotations

import datetime as dt
from typing import Annotated, Final
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.services import policy_rate_commentary
from src.api.services.policy_rates import SOURCE, SOURCE_URL, detail_json, row_json
from src.config.settings import load_settings
from src.db.session import get_session
from src.repository import policy_rate_repository as repo
from src.simulation.policy_rate import BANKS, get_bank
from src.worker import policy_rate_worker

router = APIRouter(prefix="/api/dashboard/rates", tags=["dashboard"])

Json = dict[str, object]
_KST: Final = ZoneInfo("Asia/Seoul")


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def _today() -> dt.date:
    return utc_now().astimezone(_KST).date()


def _unknown(bank_id: str) -> JSONResponse:
    message = f"없는 은행입니다: {bank_id}"
    return JSONResponse(status_code=404, content={"status": "unknown_bank", "message": message})


@router.post("/collect", status_code=202)
async def collect() -> Json:
    policy_rate_worker.wake()
    return {"accepted": True}


@router.get("", response_model=None)
async def get_rates(session: Annotated[AsyncSession, Depends(get_session)]) -> Json:
    today = _today()
    banks: list[Json] = []
    for bank in BANKS:
        rows = await repo.decisions(session, bank.id)
        banks.append(row_json(bank, rows, await repo.get_state(session, bank.id), today=today))
    return {
        "source": SOURCE,
        "sourceUrl": SOURCE_URL,
        "refreshAfterSeconds": load_settings().dashboard_refresh_seconds,
        "banks": banks,
    }


@router.get("/{bank_id}", response_model=None)
async def get_rate(
    session: Annotated[AsyncSession, Depends(get_session)], bank_id: str
) -> Json | JSONResponse:
    bank = get_bank(bank_id)
    if bank is None:
        return _unknown(bank_id)
    rows = await repo.decisions(session, bank.id)
    return detail_json(bank, rows, await repo.get_state(session, bank.id), today=_today())


@router.get("/{bank_id}/commentary", response_model=None)
async def get_commentary(bank_id: str) -> Json | JSONResponse:
    bank = get_bank(bank_id)
    if bank is None:
        return _unknown(bank_id)
    service = policy_rate_commentary.get_shared_service()
    if service is None:
        return JSONResponse(
            status_code=503,
            content={"status": "unavailable", "message": "변화 까닭 서비스가 없습니다."},
        )
    return await service.body(bank)
