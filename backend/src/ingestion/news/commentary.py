"""변화 까닭의 시황 기사 (014 반복 2026-10-10b T113) — FR-027, FR-022, research R14-17.

**공개되지 않은 내부 API·화면 HTML을 읽는다**(헌법 원칙 II 이탈 — plan Complexity Tracking, 사용자
승인 2026-10-10). 저장하지 않는다. 지표마다 출처가 하나다:

- **네이버 증권 뉴스 포커스**(`/api/domestic/news/focus?sid=&date=YYYYMMDD`) — 한국어
  제목·요약(`subcontent`)·한국 시간. `date`가 없으면 빈 목록이라 한국 오늘과 어제 두 날짜를 부르고,
  지표 낱말이 든 제목만 고른다(다른 지표의 기사를 섞지 않는다 — spec FR-027 실패 양상)
- **Yahoo Finance 종목 뉴스**(`/quote/{심볼}/news/`) — 그 종목의 목록이라 거르지 않는다. 시각은 상대
  표기("18h ago")뿐이라 받은 시각에서 빼 어림한다(읽을 수 없으면 그 줄은 고르지 않는다 — 시각을 꾸며
  내지 않는다)

출처 응답의 꼴은 이 모듈 밖으로 나가지 않는다 — 밖은 `CommentaryItem`만 본다(원칙 II·IV).
"""

from __future__ import annotations

import datetime as dt
import json
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Final, Literal
from urllib.parse import quote
from zoneinfo import ZoneInfo

from src.config.settings import Settings
from src.ingestion.news.errors import NewsInvalidBody, NewsParseEmpty
from src.ingestion.news.types import TextFetcher, absolute_url, normalize_title

_KST: Final = ZoneInfo("Asia/Seoul")
NAVER_HOST: Final = "n.news.naver.com"
YAHOO_HOST: Final = "finance.yahoo.com"
_NAVER_LANGUAGE: Final = "ko-KR,ko;q=0.9"
_YAHOO_LANGUAGE: Final = "en-US,en;q=0.9"
#: 한 날짜에 받는 기사 수 — 쪽 하나로 그날의 시황을 거의 다 본다(실측 401 하루 약 100개 중 앞쪽).
_PAGE_SIZE: Final = "50"
_NAVER_TIME: Final = "%Y%m%d%H%M%S"

SourceKind = Literal["naver", "yahoo"]


@dataclass(frozen=True, slots=True)
class CommentarySource:
    kind: SourceKind
    #: 칸에 보이는 출처 이름
    name: str
    #: 네이버 뉴스 포커스 분류(`401` 시황·전망 · `403` 해외 증시 · `429` 환율)
    sid: str | None = None
    #: 제목에 이 가운데 하나가 들어야 그 지표의 기사다(네이버만)
    keywords: tuple[str, ...] = ()
    #: Yahoo 종목 심볼
    symbol: str | None = None


def _naver(sid: str, *keywords: str) -> CommentarySource:
    return CommentarySource("naver", "네이버 증권", sid=sid, keywords=keywords)


def _yahoo(symbol: str) -> CommentarySource:
    return CommentarySource("yahoo", "Yahoo Finance", symbol=symbol)


_US_MARKET: Final = ("뉴욕증시", "뉴욕 증시")

#: 지표 → 출처. **유일한 대응**이다(R14-17 실측 — 네이버에 거의 없는 다섯은 Yahoo).
SOURCES: Final[dict[str, CommentarySource]] = {
    "kospi": _naver("401", "코스피"),
    "kosdaq": _naver("401", "코스닥"),
    "dow": _naver("403", "다우", *_US_MARKET),
    "nasdaq": _naver("403", "나스닥", *_US_MARKET),
    "sp500": _naver("403", "S&P", *_US_MARKET),
    "sox": _naver("403", "필라델피아", "반도체지수", "반도체 지수"),
    "wti": _naver("403", "유가", "WTI", "원유"),
    "usd": _naver("429", "달러"),
    "jpy": _naver("429", "엔화", "엔저", "엔고", "원·엔", "원/엔", "달러·엔", "달러/엔"),
    "eur": _naver("429", "유로"),
    "nikkei225": _yahoo("^N225"),
    "hangseng": _yahoo("^HSI"),
    "shanghai": _yahoo("000001.SS"),
    "gold": _yahoo("GC=F"),
    "vix": _yahoo("^VIX"),
}


def source_of(indicator_id: str) -> CommentarySource:
    """지표의 출처. 모르는 지표는 `KeyError`다(목록은 고정 15개 — spec FR-003)."""
    return SOURCES[indicator_id]


def source_url(indicator_id: str, settings: Settings) -> str:
    """칸에 거는 출처 목록 화면."""
    source = source_of(indicator_id)
    if source.kind == "naver":
        return "https://stock.naver.com/news"
    return f"{settings.news_commentary_yahoo_base}/quote/{quote(source.symbol or '')}/news/"


@dataclass(frozen=True, slots=True)
class CommentaryItem:
    title: str
    #: 출처의 요약 원문(네이버 `subcontent`). 없으면 `None`
    summary: str | None
    publisher: str | None
    #: 게시 시각(UTC). Yahoo는 상대 표기에서 어림한 값이다. 모르면 `None`(고르지 않는다)
    published_at: dt.datetime | None
    #: 상대 표기 글자 그대로(Yahoo)
    published_text: str | None
    url: str


def matches(title: str, keywords: Sequence[str]) -> bool:
    return any(word in title for word in keywords)


def _text(value: object) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def parse_naver_focus(raw: str) -> list[CommentaryItem]:
    """뉴스 포커스 본문 → 기사(출처 차례). `articles`가 비면 그날 기사가 없을 뿐이다(실패 아님)."""
    try:
        body = json.loads(raw)
    except ValueError as exc:
        raise NewsInvalidBody("네이버 증권 응답이 JSON이 아닙니다.") from exc
    articles = body.get("articles") if isinstance(body, dict) else None
    if not isinstance(articles, list):
        raise NewsParseEmpty("네이버 증권 응답에 기사 목록이 없습니다.")
    items: list[CommentaryItem] = []
    for article in articles:
        if not isinstance(article, dict):
            continue
        title = _text(article.get("title"))
        url = _text(article.get("url"))
        absolute = (
            None
            if url is None
            else absolute_url(url, base=f"https://{NAVER_HOST}/", host=NAVER_HOST)
        )
        if title is None or absolute is None:
            continue
        items.append(
            CommentaryItem(
                title=title,
                summary=_text(article.get("subcontent")),
                publisher=_text(article.get("officeHName")),
                published_at=_naver_time(article.get("date")),
                published_text=None,
                url=absolute,
            )
        )
    return items


def _naver_time(value: object) -> dt.datetime | None:
    if not isinstance(value, str):
        return None
    try:
        local = dt.datetime.strptime(value.strip(), _NAVER_TIME)
    except ValueError:
        return None
    return local.replace(tzinfo=_KST).astimezone(dt.UTC)


_RELATIVE: Final = re.compile(
    r"(\d+)\s*(mo|m|h|d|w|y)\b|(\d+)\s+(minute|hour|day|week|month|year)s?\b"
)
_UNIT: Final[dict[str, dt.timedelta]] = {
    "m": dt.timedelta(minutes=1),
    "minute": dt.timedelta(minutes=1),
    "h": dt.timedelta(hours=1),
    "hour": dt.timedelta(hours=1),
    "d": dt.timedelta(days=1),
    "day": dt.timedelta(days=1),
    "w": dt.timedelta(days=7),
    "week": dt.timedelta(days=7),
    "mo": dt.timedelta(days=30),
    "month": dt.timedelta(days=30),
    "y": dt.timedelta(days=365),
    "year": dt.timedelta(days=365),
}


def relative_instant(text: str, now: dt.datetime) -> dt.datetime | None:
    """상대 표기("4m ago"·"18h ago"·"yesterday"·"2 days ago"·"2mo ago")를 받은 시각에서 뺀 어림.
    읽을 수 없으면
    `None`. 달은 30일·해는 365일로 센다(어림 — 지난 세션 거르기에만 쓴다)."""
    value = text.strip().lower()
    if not value:
        return None
    if value == "yesterday":
        return now - dt.timedelta(days=1)
    if value in ("just now", "now"):
        return now
    match = _RELATIVE.search(value)
    if match is None or "ago" not in value:
        return None
    count, unit = (
        (match.group(1), match.group(2)) if match.group(1) else (match.group(3), match.group(4))
    )
    return now - int(count) * _UNIT[unit]


@dataclass
class _Card:
    #: 카드의 태그(실측 `li`)와 그 태그가 안에서 겹친 수 — 0이 되면 카드가 끝난다
    tag: str
    nest: int = 1
    href: str | None = None
    title: str | None = None
    publishing: list[str] | None = None


class _NewsStreamParser(HTMLParser):
    """`div[data-testid=news-stream]` 안의 스트림 카드(`[data-testid=stream-card]` — 실측 `li`).

    제목은 `h3`를 감싼 링크의 `title`이다(카드 안 종목 링크에도 `title`이 있다). 언론사·시각은
    `div.publishing`의 글자다.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.depth = 0
        self.stream_depth: int | None = None
        self.done = False
        self.card: _Card | None = None
        self.cards: list[_Card] = []
        self.anchor: dict[str, str] | None = None
        self.publishing_depth: int | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {k: v or "" for k, v in attrs}
        testid = values.get("data-testid")
        if self.card is not None and tag == self.card.tag:
            self.card.nest += 1
        if tag == "div":
            self.depth += 1
            if self.stream_depth is None and not self.done and testid == "news-stream":
                self.stream_depth = self.depth
                return
            if self.card is not None and "publishing" in values.get("class", "").split():
                self.publishing_depth = self.depth
                self.card.publishing = []
        if self.stream_depth is not None and self.card is None and testid == "stream-card":
            self.card = _Card(tag=tag)
            return
        if self.card is None:
            return
        if tag == "a":
            self.anchor = values
        elif tag == "h3" and self.anchor is not None and self.card.href is None:
            self.card.href = self.anchor.get("href") or None
            self.card.title = (self.anchor.get("title") or "").strip() or None

    def handle_endtag(self, tag: str) -> None:
        if self.card is not None and tag == self.card.tag:
            self.card.nest -= 1
            if self.card.nest == 0:
                self.cards.append(self.card)
                self.card = None
        if tag == "div":
            if self.publishing_depth is not None and self.depth == self.publishing_depth:
                self.publishing_depth = None
            if self.stream_depth is not None and self.depth == self.stream_depth:
                self.stream_depth, self.done = None, True
            self.depth -= 1
        elif tag == "a":
            self.anchor = None

    def handle_data(self, data: str) -> None:
        if (
            self.card is not None
            and self.publishing_depth is not None
            and self.card.publishing is not None
        ):
            self.card.publishing.append(data)


def parse_yahoo_quote_news(raw: str, *, now: dt.datetime) -> list[CommentaryItem]:
    """종목 뉴스 화면 → 기사(화면 차례). 목록 칸이 없거나 카드가 0이면 `NewsParseEmpty`(화면이 바뀐
    신호)."""
    parser = _NewsStreamParser()
    parser.feed(raw)
    parser.close()
    items: list[CommentaryItem] = []
    for card in parser.cards:
        url = (
            absolute_url(card.href, base=f"https://{YAHOO_HOST}/", host=YAHOO_HOST)
            if card.href
            else None
        )
        if card.title is None or url is None:
            continue
        publisher, published = _publishing(card.publishing)
        items.append(
            CommentaryItem(
                title=card.title,
                summary=None,
                publisher=publisher,
                published_at=None if published is None else relative_instant(published, now),
                published_text=published,
                url=url,
            )
        )
    if not items:
        raise NewsParseEmpty("Yahoo Finance 종목 뉴스에서 기사를 하나도 읽지 못했습니다.")
    return items


def _publishing(parts: list[str] | None) -> tuple[str | None, str | None]:
    """ "Investing.com • 18h ago" → ("Investing.com", "18h ago")."""
    text = " ".join("".join(parts or []).split())
    if not text:
        return None, None
    if "•" in text:
        publisher, _, published = text.partition("•")
        return publisher.strip() or None, published.strip() or None
    return text, None


class CommentaryClient:
    """지표의 시황 기사를 출처에서 받는다. HTTP는 뉴스와 같은 클라이언트(`NewsClient` — 사용자
    에이전트·재시도)다."""

    def __init__(
        self,
        http: TextFetcher,
        settings: Settings,
        *,
        clock: Callable[[], dt.datetime],
    ) -> None:
        self._http = http
        self._settings = settings
        self._clock = clock

    async def fetch(self, indicator_id: str) -> list[CommentaryItem]:
        """그 지표의 기사(출처 차례 — 고르기 전). 실패는 `NewsError`다."""
        source = source_of(indicator_id)
        now = self._clock()
        if source.kind == "yahoo":
            raw = await self._http.get_text(
                source_url(indicator_id, self._settings), accept_language=_YAHOO_LANGUAGE
            )
            return parse_yahoo_quote_news(raw, now=now)
        today = now.astimezone(_KST).date()
        items: list[CommentaryItem] = []
        seen: set[str] = set()
        for day in (today, today - dt.timedelta(days=1)):
            raw = await self._http.get_text(
                self._settings.news_commentary_naver_url,
                params={
                    "sid": source.sid or "",
                    "page": "1",
                    "pageSize": _PAGE_SIZE,
                    "date": day.strftime("%Y%m%d"),
                },
                accept_language=_NAVER_LANGUAGE,
            )
            for item in parse_naver_focus(raw):
                key = normalize_title(item.title)
                if key in seen or not matches(item.title, source.keywords):
                    continue
                seen.add(key)
                items.append(item)
        return items
