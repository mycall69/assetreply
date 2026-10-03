"""코인 검색 (T019) — 007 FR-003~FR-006, contracts/rest-api `GET /api/crypto/search`.

로컬 코인 목록에서 찾는다. **출처를 부르지 않는다.** 목록 갱신 주기가 되었으면 갱신을 요청하되
**기다리지 않는다**(006 FR-017과 같다). 목록이 없거나 갱신이 실패해도 오류가 아니다 — 200에 `list`로
알린다. 화면은 `results`가 비었을 때 `list`를 보고 "결과 없음"과 "목록 없음"을 가른다.
"""

from __future__ import annotations

import datetime as dt
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.errors import InvalidQuery
from src.api.services.crypto_index import CoinView, get_coin_index
from src.api.services.crypto_list_refresh import EditionState, request_refresh
from src.api.services.listing_refresh import utc_now
from src.config.settings import Settings, load_settings
from src.db.session import get_session
from src.repository import crypto_coin as repo
from src.search.match import MatchKind
from src.worker import crypto_list_queue
from src.worker.crypto_list_queue import CryptoListQueue

router = APIRouter(prefix="/api/crypto", tags=["crypto"])

Json = dict[str, object]


def get_now() -> dt.datetime:
    """지금 시각(UTC). 갱신 주기(한국 시간 날짜)의 판정 근거라 테스트가 바꿔 끼운다."""
    return utc_now()


def get_crypto_list_settings() -> Settings:
    return load_settings()


def get_crypto_list_queue() -> CryptoListQueue:
    return crypto_list_queue.get_crypto_list_queue()


def iso_utc(value: dt.datetime | None) -> str | None:
    return None if value is None else f"{value.isoformat()}Z"


def edition_json(state: EditionState) -> Json:
    body: Json = {"state": state.state, "asOf": iso_utc(state.as_of)}
    if state.reason is not None:
        body["reason"] = state.reason
    return body


def coin_json(view: CoinView, match: MatchKind, first_available: dt.date | None) -> Json:
    return {
        "coinId": view.coin_id,
        "symbol": view.symbol,
        "name": view.name_en,
        "nameKo": view.name_ko,
        "slug": view.slug,
        "currency": view.currency,
        "rank": view.rank,
        "listStatus": view.status,
        # 수집으로 발견한 첫 일봉. 없으면 아직 모른다(research R7-10).
        "firstAvailableDate": first_available.isoformat() if first_available else None,
        "match": match,
    }


@router.get("/search")
async def search_coins(
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_crypto_list_settings)],
    now: Annotated[dt.datetime, Depends(get_now)],
    queue: Annotated[CryptoListQueue, Depends(get_crypto_list_queue)],
    q: Annotated[str, Query(description="영문 이름·심볼·한글 이름·초성")],
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> Json:
    """로컬 목록에서 찾는다. 결과가 없어도 `list`는 항상 온다."""
    query = q.strip()
    if not query:
        raise InvalidQuery("검색어를 입력하세요.")
    status = await request_refresh(session, now=now, settings=settings, queue=queue)
    index = await get_coin_index(session)
    outcome = index.search.search(query, limit)
    firsts = await repo.first_available_dates(session, [h.entry.key for h in outcome.hits])
    return {
        "query": query,
        "results": [coin_json(index.views[h.entry.key], h.match, firsts.get(h.entry.key))
                    for h in outcome.hits],
        "truncated": outcome.truncated,
        "list": {**edition_json(status.list), "koreanNames": edition_json(status.korean)},
    }
