"""뉴스 목록 (014 T072) — data-model 6, FR-020~FR-022.

저장하지 않는다(FR-023). 출처의 키 이름은 어댑터 밖으로 나가지 않는다 — 칸은 여기의 이름이다.

- **10개**: 출처 목록의 위에서부터, 같은 기사는 한 번만 센다 — 정규화한 제목(공백 접기)으로
  거른다(명확화 3, R14-13).
  출처가 같은 제목을 다른 기사 번호로 두 번 내는 일이 실측으로 있었다
- **링크**: 절대 https이고 칸마다 허용한 도메인 안이어야 한다. 아니면 그 줄을 버린다(FR-022) — 상대
  주소는 대시보드
  주소 아래의 없는 경로가 되고, `javascript:`는 스크립트가 실행된다
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, replace
from typing import Final, Literal, Protocol
from urllib.parse import urljoin, urlsplit

SourceKey = Literal["kr", "us", "jp"]
SOURCES: Final[tuple[SourceKey, ...]] = ("kr", "us", "jp")

#: 칸마다 보이는 기사 수(FR-020).
LIMIT: Final = 10


@dataclass(frozen=True, slots=True)
class NewsItem:
    rank: int
    title: str
    url: str
    publisher: str | None
    #: 정확한 시각이 있을 때만(UTC). 한국 출처와 일본 출처의 오늘 기사
    published_at: dt.datetime | None
    #: 날짜만 있을 때(일본 출처의 지난 날 기사)
    published_date: dt.date | None
    #: 상대 표기 글자 그대로(미국 출처 — "4m ago"). 시각을 꾸며 내지 않는다(FR-021)
    published_text: str | None
    paid: bool


@dataclass(frozen=True, slots=True)
class NewsList:
    source: SourceKey
    fetched_at: dt.datetime
    items: tuple[NewsItem, ...]


class TextFetcher(Protocol):
    """본문 하나를 받는다. 실패는 `errors.NewsError`로 올린다."""

    async def get_text(
        self, url: str, *, params: Mapping[str, str] | None = None, accept_language: str
    ) -> str: ...


def normalize_title(title: str) -> str:
    """같은 기사를 가리는 열쇠 — 공백을 접는다(글자는 바꾸지 않는다)."""
    return " ".join(title.split())


def absolute_url(href: str, *, base: str, host: str) -> str | None:
    """절대 https 주소. 허용 도메인 밖이거나 https가 아니면 `None`(그 줄을 버린다)."""
    url = urljoin(base, href.strip())
    parts = urlsplit(url)
    if parts.scheme != "https" or parts.hostname != host:
        return None
    return url


def pick_top(candidates: Iterable[NewsItem], limit: int = LIMIT) -> list[NewsItem]:
    """위에서부터 같은 제목을 한 번만 세어 `limit`개. 차례 번호는 1부터 다시 매긴다."""
    seen: set[str] = set()
    out: list[NewsItem] = []
    for item in candidates:
        key = normalize_title(item.title)
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(replace(item, rank=len(out) + 1, title=item.title.strip()))
        if len(out) == limit:
            break
    return out
