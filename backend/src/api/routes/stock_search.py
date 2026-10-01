"""종목 검색 (T037) — 005 FR-002, FR-002a~002c, contracts/rest-api.

**검색 실패와 "결과 없음"을 구별한다.** 출처가 죽었는데 빈 목록을 주면 사용자는 그
종목이 존재하지 않는다고 읽는다 — 할 일이 정반대인데 화면이 같은 말을 하게 된다.

목록을 미리 쌓지 않고 **검색 시점에 출처에 묻는다.** 신규 상장 종목이 빠지지 않는
근거다 (FR-002c, research R5-2). 전체 목록을 받아 두면 갱신 시점을 관리해야 하고,
그 관리가 틀리면 조용히 낡은 목록을 보여준다.
"""

from __future__ import annotations

from types import TracebackType
from typing import Annotated, Protocol

from fastapi import APIRouter, Depends, Query

from src.api.errors import InvalidQuery
from src.config.settings import load_settings
from src.ingestion.yahoo.client import YahooStockClient
from src.ingestion.yahoo.parse import StockQuote

router = APIRouter(prefix="/api/stocks", tags=["stocks"])

Json = dict[str, object]

#: 질의가 너무 짧으면 출처가 관련 없는 결과를 쏟아낸다.
MIN_QUERY_LENGTH = 1


class SearchSource(Protocol):
    """검색 출처. 어댑터를 교체할 수 있도록 Protocol에 의존한다 (헌법 원칙 II)."""

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


def get_source() -> SearchSource:
    """기본 출처. 테스트는 의존성 오버라이드로 스텁을 넣는다."""
    return YahooStockClient(load_settings())


@router.get("/search")
async def search_stocks(
    source: Annotated[SearchSource, Depends(get_source)],
    q: Annotated[str, Query(description="종목 이름 또는 코드의 일부")],
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> Json:
    """종목을 검색한다 (FR-002a).

    응답에 **시장과 통화를 함께 싣는다**(FR-002b). 같은 이름이 여러 시장에 있을 수
    있고, 통화가 다르면 환전 여부와 수익률 기준이 달라진다.
    """
    query = q.strip()
    if len(query) < MIN_QUERY_LENGTH:
        raise InvalidQuery("검색어를 입력하세요.")

    async with source as client:
        results, _, _ = await client.search(query, limit)

    return {
        "query": query,
        "results": [{
            "market": r.market,
            "symbol": r.symbol,
            "name": r.name,
            "currency": r.currency,
        } for r in results],
    }
