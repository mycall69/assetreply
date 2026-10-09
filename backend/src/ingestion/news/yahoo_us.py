"""Yahoo Finance Latest News (014 T074) — FR-020~FR-022, research R14-13.

**화면 HTML을 읽는다**(헌법 원칙 II 이탈 — plan Complexity Tracking, 사용자 승인 2026-10-09). 주요
목록이 없어 그 화면의
최신 목록(`div[data-testid=topic-stream]`의 스트림 카드)을 쓴다.

- 선택은 `data-testid`와 뜻 있는 클래스(`publisher`·`published-date`)뿐이다 — 해시 클래스(`yf-…`)는
  배포마다 바뀐다
- 카드 하나 = `div[data-testid=stream-card]`. 광고 칸(`ad-container`)에는 카드가 없어 저절로 빠진다
- 제목은 **`h3`를 감싼 링크**의 `title`이다 — 카드 안 종목 링크(`/quote/NVDA/`)에도 `title`이 있다
- 시각은 상대 표기("4m ago")뿐이라 글자 그대로 둔다(FR-021 — 꾸며 내지 않는다). 칸의 받은 시각이
  기준이다
- 표준 라이브러리 `html.parser`만 쓴다(새 의존성 없음)
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import Final

from src.ingestion.news.errors import NewsParseEmpty
from src.ingestion.news.types import NewsItem, TextFetcher, absolute_url, pick_top

ACCEPT_LANGUAGE: Final = "en-US,en;q=0.9"
HOST: Final = "finance.yahoo.com"
_BASE: Final = f"https://{HOST}/"
_STREAM: Final = "topic-stream"
_CARD: Final = "stream-card"


@dataclass
class _Card:
    depth: int
    href: str | None = None
    title: str | None = None
    heading: list[str] = field(default_factory=list)
    publisher: list[str] = field(default_factory=list)
    published: list[str] = field(default_factory=list)


class _StreamParser(HTMLParser):
    """`topic-stream` 안의 카드만 모은다. `div` 깊이로 칸의 범위를 잰다."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.depth = 0
        #: 목록 칸의 `div` 깊이. 칸이 끝나면 `done` — 다른 칸의 카드를 섞지 않는다(FR-020)
        self.stream_depth: int | None = None
        self.done = False
        self.card: _Card | None = None
        self.cards: list[_Card] = []
        self.anchor: dict[str, str] | None = None
        self.in_heading = False
        self.span: str | None = None
        self.span_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {k: v or "" for k, v in attrs}
        if tag == "div":
            self.depth += 1
            testid = values.get("data-testid")
            if self.stream_depth is None and not self.done and testid == _STREAM:
                self.stream_depth = self.depth
            elif self.stream_depth is not None and self.card is None and testid == _CARD:
                self.card = _Card(depth=self.depth)
            return
        if self.card is None:
            return
        if tag == "a":
            self.anchor = values
        elif tag == "h3" and self.anchor is not None and self.card.href is None:
            self.card.href = self.anchor.get("href") or None
            self.card.title = (self.anchor.get("title") or "").strip() or None
            self.in_heading = True
        elif tag == "span":
            classes = values.get("class", "").split()
            if self.span is not None:
                self.span_depth += 1
            elif "publisher" in classes:
                self.span, self.span_depth = "publisher", 0
            elif "published-date" in classes:
                self.span, self.span_depth = "published", 0

    def handle_endtag(self, tag: str) -> None:
        if tag == "div":
            if self.card is not None and self.depth == self.card.depth:
                self.cards.append(self.card)
                self.card = None
            if self.stream_depth is not None and self.depth == self.stream_depth:
                self.stream_depth, self.done = None, True
            self.depth -= 1
        elif tag == "a":
            self.anchor = None
        elif tag == "h3":
            self.in_heading = False
        elif tag == "span" and self.span is not None:
            if self.span_depth == 0:
                self.span = None
            else:
                self.span_depth -= 1

    def handle_data(self, data: str) -> None:
        if self.card is None:
            return
        if self.in_heading:
            self.card.heading.append(data)
        elif self.span == "publisher":
            self.card.publisher.append(data)
        elif self.span == "published":
            self.card.published.append(data)


def _joined(parts: list[str]) -> str | None:
    text = " ".join("".join(parts).split())
    return text or None


def parse(raw: str) -> list[NewsItem]:
    """화면 → 위 10개. 목록 칸이 없거나 읽은 기사가 0이면 `NewsParseEmpty`."""
    parser = _StreamParser()
    parser.feed(raw)
    parser.close()
    candidates: list[NewsItem] = []
    for card in parser.cards:
        title = card.title or _joined(card.heading)
        url = absolute_url(card.href, base=_BASE, host=HOST) if card.href else None
        if title is None or url is None:
            continue
        candidates.append(
            NewsItem(
                rank=0,
                title=title,
                url=url,
                publisher=_joined(card.publisher),
                published_at=None,
                published_date=None,
                published_text=_joined(card.published),
                paid=False,
            )
        )
    items = pick_top(candidates)
    if not items:
        raise NewsParseEmpty("Yahoo Finance 화면에서 기사를 하나도 읽지 못했습니다.")
    return items


async def fetch(http: TextFetcher, url: str, *, now: dt.datetime) -> list[NewsItem]:
    """`now`는 쓰지 않는다 — 시각은 상대 표기 글자 그대로다."""
    del now
    return parse(await http.get_text(url, accept_language=ACCEPT_LANGUAGE))
