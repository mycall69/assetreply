"""검색 색인 (T037) — 006 SC-001, research R6-5.

검색은 **프로세스 메모리의 색인**에서 한다. DB가 원본이고 색인은 사본이다. 검색마다 목록의 버전을 한
번 읽어(작은 질의 하나) 바뀌었으면 다시 만든다 — 프로세스가 여럿이어도 각자 DB 버전을 보고 따라온다.

**버전은 단위마다의 기준 시각 묶음이다.** research R6-5는 "기준 시각의 최댓값"이라 했으나, 두 단위가
같은 초에 교체되면 최댓값이 같아 먼저 만든 색인이 뒤 단위를 빠뜨린 채 남는다(저장 시각은 초 단위다).
단위별 기준 시각을 모두 보면 어느 단위가 바뀌어도 버전이 바뀐다.
"""

from __future__ import annotations

import datetime as dt
import logging
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from src.repository import stock_listing as repo
from src.search.match import SearchEntry, SearchIndex
from src.search.price_symbol import to_price_symbol

_log = logging.getLogger(__name__)

Version = tuple[tuple[str, dt.datetime | None], ...]


@dataclass(frozen=True, slots=True)
class ListingView:
    """검색 결과 한 줄에 필요한 것. 시세 식별자(`market`·`symbol`)는 005의 것이다(FR-030)."""

    listing_id: int
    country: str
    unit: str
    code: str
    name_ko: str | None
    name_en: str | None
    kind: str
    listed_on: dt.date | None
    status: str
    market: str
    symbol: str
    currency: str


@dataclass(frozen=True, slots=True)
class ListingIndex:
    version: Version
    search: SearchIndex
    views: dict[int, ListingView]


_current: ListingIndex | None = None


async def _version(session: AsyncSession) -> Version:
    records = await repo.all_refresh(session)
    return tuple(sorted((unit, row.as_of) for unit, row in records.items()))


async def _build(session: AsyncSession, version: Version) -> ListingIndex:
    views: dict[int, ListingView] = {}
    entries: list[SearchEntry] = []
    for row in await repo.load_listings(session):
        try:
            ps = to_price_symbol(row.unit, row.code)
        except ValueError:
            # 규칙이 없는 단위의 종목을 결과에 내면 고른 뒤에야 시세를 받을 수 없음을 안다.
            _log.warning("시세 식별자 규칙이 없는 목록 종목 unit=%s code=%s", row.unit, row.code)
            continue
        view = ListingView(
            listing_id=int(row.id), country=row.country, unit=row.unit, code=row.code,
            name_ko=row.name_ko, name_en=row.name_en, kind=row.kind, listed_on=row.listed_on,
            status=row.status, market=ps.market, symbol=ps.symbol, currency=ps.currency)
        views[view.listing_id] = view
        names = tuple(n for n in (row.name_ko, row.name_en) if n)
        entries.append(SearchEntry(key=view.listing_id, names=names, codes=(row.code,),
                                   market=ps.market, code=row.code))
    return ListingIndex(version, SearchIndex(entries), views)


async def get_listing_index(session: AsyncSession) -> ListingIndex:
    """지금 목록의 색인. 버전이 같으면 다시 만들지 않는다.

    잠금을 두지 않는다 — 동시에 들어온 검색이 함께 다시 만들어도 같은 색인이 나오고, 낭비는 하루
    한두 번이다. 모듈 수준의 `asyncio.Lock`은 처음 기다린 이벤트 루프에 묶여 다른 루프에서 깨진다.
    """
    global _current
    version = await _version(session)
    current = _current
    if current is None or current.version != version:
        current = await _build(session, version)
        _current = current
    return current


def reset_listing_index() -> None:
    """테스트용. 같은 고정 시각을 쓰는 앞 테스트의 색인이 뒤 테스트에 남지 않게 한다."""
    global _current
    _current = None
