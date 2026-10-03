"""코인 검색 색인 (T019) — 007 FR-003, FR-004, FR-006, research R7-6.

검색은 **프로세스 메모리의 색인**에서 한다. DB가 원본이고 색인은 사본이다. 검색마다 두 판의 기준
시각을 한 번 읽어(작은 질의 하나) 바뀌었으면 다시 만든다(006 `listing_index`와 같다).

- 찾을 이름은 **한글 이름·영문 이름**, 코드는 **심볼**이다 — 영문·심볼·한글·초성이 모두
  찾힌다(FR-006)
- 같은 일치 종류 안에서는 **시가총액 순위**가 먼저다 — 심볼이 겹치는 코인(MAX 5개)을 이름 길이로
  정렬하면 작은 코인이
  위에 온다(R7-6). 순위가 없는 코인은 뒤다
- 첫 일봉(`first_available_date`)은 담지 않는다 — 수집 중 발견해 목록 갱신 없이 바뀐다. 결과마다
  읽는다
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Final

from sqlalchemy.ext.asyncio import AsyncSession

from src.repository import crypto_coin as repo
from src.search.match import SearchEntry, SearchIndex

Version = tuple[tuple[str, dt.datetime | None], ...]

#: 순위가 없는 코인의 우선순위 — 순위가 있는 모든 코인 뒤.
_UNRANKED: Final = 10**9


@dataclass(frozen=True, slots=True)
class CoinView:
    """검색 결과 한 줄에 필요한 것. 식별자는 `coin_id`다 — 심볼은 유일하지 않다(FR-004)."""

    coin_id: int
    source_id: str
    symbol: str
    name_en: str
    name_ko: str | None
    slug: str | None
    currency: str
    rank: int | None
    status: str


@dataclass(frozen=True, slots=True)
class CoinIndex:
    version: Version
    search: SearchIndex
    views: dict[int, CoinView]


_current: CoinIndex | None = None


async def _version(session: AsyncSession) -> Version:
    records = await repo.all_refresh(session)
    return tuple(sorted((edition, row.as_of) for edition, row in records.items()))


async def _build(session: AsyncSession, version: Version) -> CoinIndex:
    views: dict[int, CoinView] = {}
    entries: list[SearchEntry] = []
    for row in await repo.load_coins(session):
        view = CoinView(
            coin_id=int(row.id), source_id=row.source_id, symbol=row.symbol, name_en=row.name_en,
            name_ko=row.name_ko, slug=row.slug, currency=row.quote_currency,
            rank=row.market_rank, status=row.status)
        views[view.coin_id] = view
        names = tuple(n for n in (row.name_ko, row.name_en) if n)
        entries.append(SearchEntry(
            key=view.coin_id, names=names, codes=(row.symbol,), market="CRYPTO", code=row.symbol,
            priority=row.market_rank if row.market_rank is not None else _UNRANKED))
    return CoinIndex(version, SearchIndex(entries), views)


async def get_coin_index(session: AsyncSession) -> CoinIndex:
    """지금 목록의 색인. 버전이 같으면 다시 만들지 않는다. 잠금을 두지 않는다(006과 같은 이유)."""
    global _current
    version = await _version(session)
    current = _current
    if current is None or current.version != version:
        current = await _build(session, version)
        _current = current
    return current


def reset_coin_index() -> None:
    """테스트용. 같은 고정 시각을 쓰는 앞 테스트의 색인이 뒤 테스트에 남지 않게 한다."""
    global _current
    _current = None
