"""종목 검색 (T038) — 006 FR-017, FR-021, FR-026~029, contracts/rest-api, research R6-12.

검색이 **두 엔드포인트로 나뉜다.** 한 응답으로 합치면 서버가 외부 응답을
기다려야 하고, 외부가 막히면 로컬 결과까지 늦는다(FR-027). 나누면 서로를
기다릴 방법 자체가 없다.

- `GET /api/stocks/search` — 국내 검색용 목록(로컬). **외부 출처를 부르지
  않는다.** 그날 처음 들어온 검색이면 갱신을 요청하되 기다리지 않는다
  (FR-017). 목록이 없거나 갱신이 실패해도 오류가 아니다 — 200에 `lists`로
  알린다. 오류로 내면 화면이 "검색 실패"로만 보이고 무엇을 해야 하는지
  말할 자리가 없다(FR-028a)
- `GET /api/stocks/search/external` — 005의 외부 출처 검색. 결과에서
  **TSE만 남긴다**(FR-026). 국내·미국 종목은 로컬 목록이 맡는다

005 research R5-2("목록을 미리 쌓지 않는다")를 국내·미국에 한해 뒤집는다.
초성 검색에는 목록이 필요하고, 로컬 목록이 외부 왕복보다 빠르다. R5-2가
걱정한 "조용히 낡은 목록"은 매일 갱신하고 **기준 시각을 드러내는 것**으로
답한다(FR-029).
"""

from __future__ import annotations

import datetime as dt
from types import TracebackType
from typing import Annotated, Final, Protocol

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.errors import InvalidQuery
from src.api.services.listing_index import ListingView, get_listing_index
from src.api.services.listing_refresh import (
    ListState,
    get_auth_blocker,
    request_refreshes,
    utc_now,
)
from src.config.settings import Settings, load_settings
from src.db.session import get_session
from src.ingestion.yahoo.client import YahooStockClient
from src.ingestion.yahoo.gate import get_yahoo_gate
from src.ingestion.yahoo.parse import StockQuote
from src.search.match import MatchKind
from src.worker import listing_queue
from src.worker.listing_queue import ListingQueue

router = APIRouter(prefix="/api/stocks", tags=["stocks"])

Json = dict[str, object]

#: 외부 검색이 맡는 시장 (FR-026).
EXTERNAL_MARKETS: Final = frozenset({"TSE"})


class SearchSource(Protocol):
    """외부 검색 출처. 어댑터를 교체할 수 있도록 Protocol에 의존한다 (헌법 원칙 II)."""

    async def search(
        self, query: str, limit: int
    ) -> tuple[list[StockQuote], str, int]: ...

    async def __aenter__(self) -> SearchSource: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None: ...


async def get_source() -> SearchSource:
    """외부 검색 출처. 테스트는 의존성 오버라이드로 스텁을 넣는다.

    014 — 요청마다 새 클라이언트라도 Yahoo 관문은 하나다(대시보드·주식 수집과 함께 — R14-10). 관문이
    이벤트 루프에 묶이므로
    비동기 의존성으로 루프 안에서 얻는다.
    """
    settings = load_settings()
    return YahooStockClient(settings, gate=get_yahoo_gate(settings))


def get_now() -> dt.datetime:
    """지금 시각(UTC). "오늘(한국 시간) 받았나"의 판정 근거라 테스트가 바꿔 끼운다."""
    return utc_now()


def get_listing_settings() -> Settings:
    return load_settings()


def get_listing_queue() -> ListingQueue:
    return listing_queue.get_listing_queue()


def _query(q: str) -> str:
    query = q.strip()
    if not query:
        raise InvalidQuery("검색어를 입력하세요.")
    return query


def _iso_utc(value: dt.datetime | None) -> str | None:
    return None if value is None else f"{value.isoformat()}Z"


def result_json(view: ListingView, match: MatchKind) -> Json:
    """검색 결과 한 줄. `market`·`symbol`은 **005의 시세 식별자**다(FR-030)."""
    return {
        "listingId": view.listing_id,
        "country": view.country,
        "market": view.market,
        "symbol": view.symbol,
        "code": view.code,
        "name": view.name_ko or view.name_en or view.code,
        "nameEn": view.name_en,
        "currency": view.currency,
        "kind": view.kind,
        # 시작 가능 날짜가 아니라 하한이다 (FR-005a).
        "listedOn": view.listed_on.isoformat() if view.listed_on else None,
        "listingStatus": view.status,
        "match": match,
    }


def state_json(state: ListState) -> Json:
    body: Json = {"unit": state.unit, "state": state.state, "asOf": _iso_utc(state.as_of)}
    if state.reason is not None:
        body["reason"] = state.reason
    if state.action is not None:
        body["action"] = state.action
    return body


@router.get("/search")
async def search_stocks(
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_listing_settings)],
    now: Annotated[dt.datetime, Depends(get_now)],
    queue: Annotated[ListingQueue, Depends(get_listing_queue)],
    q: Annotated[str, Query(description="한글명·초성·혼용·영문명·코드·티커")],
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> Json:
    """로컬 목록에서 찾는다. 결과가 없어도 `lists`는 항상 온다(FR-028)."""
    query = _query(q)
    states = await request_refreshes(
        session, now=now, settings=settings, queue=queue, blocker=get_auth_blocker())
    index = await get_listing_index(session)
    outcome = index.search.search(query, limit)
    return {
        "query": query,
        "results": [result_json(index.views[h.entry.key], h.match) for h in outcome.hits],
        "truncated": outcome.truncated,
        "lists": [state_json(s) for s in states],
    }


@router.get("/search/external")
async def search_external(
    source: Annotated[SearchSource, Depends(get_source)],
    q: Annotated[str, Query(description="종목 이름 또는 코드의 일부")],
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> Json:
    """일본 종목을 외부 출처에서 찾는다. 출처 장애는 005와 같은 오류로 낸다.

    **검색 실패와 "결과 없음"을 구별한다.** 출처가 죽었는데 빈 목록을 주면
    사용자는 그 종목이 존재하지 않는다고 읽는다.
    """
    query = _query(q)
    async with source as client:
        results, _, _ = await client.search(query, limit)
    return {
        "query": query,
        "results": [{
            "market": r.market, "symbol": r.symbol, "name": r.name,
            "currency": r.currency, "kind": r.kind,
        } for r in results if r.market in EXTERNAL_MARKETS],
    }
