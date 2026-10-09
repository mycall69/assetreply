"""Yahoo Finance Latest News 계약 (014 T065) — FR-020~FR-022, FR-024, SC-007, SC-008, research
R14-13.

**화면 HTML을 읽는다**(헌법 원칙 II 이탈 — plan Complexity Tracking, 사용자 승인 2026-10-09).
**네트워크를 쓰지 않는다**(원칙 III). 실측 본문(`fixtures/news/`)을 쓴다.

- 주요 목록이 없다 — 그 화면의 최신 목록(`topic-stream`의 스트림 카드)에서 위 10개, 광고 칸은 뺀다
- 칸: 제목(`a[title]` — 종목 링크의 `title`이 아니다)·절대
  주소·`span.publisher`·`span.published-date` 글자 그대로
- `finance.yahoo.com` 밖·`javascript:`·`http:` 링크 줄은 버리고, 상대 주소는 절대 주소로 바꾼다
- 실패: 목록 칸 없음 → `parse_empty`, 429 본문 → `rate_limited`
"""

from __future__ import annotations

import dataclasses
import datetime as dt
from pathlib import Path
from typing import Self

import pytest
from src.ingestion.news import yahoo_us
from src.ingestion.news.client import NewsClient
from src.ingestion.news.errors import NewsParseEmpty, NewsRateLimited

from src.config.settings import load_settings

FIX = Path(__file__).parent / "fixtures" / "news"
UA = "Mozilla/5.0 (테스트) Chrome/154.0.0.0 Safari/537.36"
NOW = dt.datetime(2026, 10, 9, 13, 30, tzinfo=dt.UTC)

FIRST_TEN = [
    "Author Kyla Scanlon: It's getting harder to climb the economic ladder",
    "Chipotle shares jump after report that Starbucks has explored a takeover",
    "Tesla rebrands Full Self-Driving as Tesla Assisted Driving in Europe",
    "How AI corporate travel is quietly lifting Delta",
    "Oil Prices Retreat After Trump Appears to Rule out Iran Strikes Before Midterms",
    "Oracle trucks natural gas to AI data centers amid pipeline delays",
    "Cash App $15 million data breach settlement payments October 2026",
    "Blue Origin plans $555 million satellite factory in Hutto, Texas",
    "Wall St set to open higher as oil slips; telecoms hit by SpaceX spectrum deal",
    "ExxonMobil blocked $5B Kashagan environmental fine settlement",
]


def fixture(name: str) -> str:
    return (FIX / name).read_text(encoding="utf-8")


class Resp:
    def __init__(self, body: str, status: int = 200) -> None:
        self._body = body
        self.status = status

    async def text(self) -> str:
        return self._body

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *exc: object) -> None:
        return None


class Session:
    def __init__(self, replies: list[Resp]) -> None:
        self.replies = list(replies)
        self.requests: list[tuple[str, dict[str, str], dict[str, str]]] = []

    def get(
        self,
        url: str,
        *,
        params: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
        **_: object,
    ) -> Resp:
        self.requests.append((url, dict(params or {}), dict(headers or {})))
        return self.replies.pop(0)

    async def close(self) -> None:
        return None


async def no_sleep(_: float) -> None:
    return None


def client(session: Session) -> NewsClient:
    settings = dataclasses.replace(load_settings(), news_user_agent=UA)
    return NewsClient(settings, session=session, sleep=no_sleep, clock=lambda: NOW)  # type: ignore[arg-type]


class Test파싱:
    def test_스트림_카드_위_10개이고_광고_칸은_뺀다(self) -> None:
        items = yahoo_us.parse(fixture("yahoo_us_latest.html"))
        assert [i.title for i in items] == FIRST_TEN
        assert [i.rank for i in items] == list(range(1, 11))

    def test_칸은_제목_절대_주소_언론사_상대_시각_글자다(self) -> None:
        items = yahoo_us.parse(fixture("yahoo_us_latest.html"))
        first, second = items[0], items[1]
        assert first.url == (
            "https://finance.yahoo.com/economy/article/"
            "author-kyla-scanlon-its-getting-harder-to-climb-the-economic-ladder-132017624.html"
        )
        assert (first.publisher, first.published_text) == ("Yahoo Finance", "4m ago")
        assert (second.publisher, second.published_text) == ("CBS News", "6m ago")
        assert first.published_at is None and first.published_date is None
        assert first.paid is False

    def test_종목_링크의_title을_제목으로_읽지_않는다(self) -> None:
        """카드마다 종목 링크(`/quote/NVDA/`)에도 `title`이 있다 — 제목 줄의 링크만 읽는다."""
        for item in yahoo_us.parse(fixture("yahoo_us_latest.html")):
            assert "/quote/" not in item.url and item.title not in {"NVDA", "TSLA", "ORCL"}

    def test_허용_도메인_밖_링크가_없다(self) -> None:
        for item in yahoo_us.parse(fixture("yahoo_us_latest.html")):
            assert item.url.startswith("https://finance.yahoo.com/")

    def test_상대_주소는_절대로_바꾸고_다른_도메인_javascript_http_줄은_버린다(self) -> None:
        items = yahoo_us.parse(fixture("yahoo_us_link_variants.html"))
        assert items[0].url == "https://finance.yahoo.com/news/relative-link-fixture-123.html"
        assert items[0].title == FIRST_TEN[0]
        # 둘째~넷째 카드(javascript:·다른 도메인·http)는 버리고 다섯째부터 채운다
        assert [i.title for i in items[1:4]] == FIRST_TEN[4:7]
        assert len(items) == 10
        assert all(i.url.startswith("https://finance.yahoo.com/") for i in items)

    def test_목록_칸이_없으면_parse_empty다(self) -> None:
        with pytest.raises(NewsParseEmpty):
            yahoo_us.parse(fixture("yahoo_us_no_stream.html"))

    def test_빈_화면은_parse_empty다(self) -> None:
        with pytest.raises(NewsParseEmpty):
            yahoo_us.parse("")


class Test요청:
    async def test_주소와_머리(self) -> None:
        session = Session([Resp(fixture("yahoo_us_latest.html"))])
        async with client(session) as news:
            listed = await news.fetch("us")
        url, params, headers = session.requests[0]
        assert url == "https://finance.yahoo.com/topic/latest-news/"
        assert params == {}
        assert headers["User-Agent"] == UA
        assert headers["Accept-Language"].startswith("en-US")
        assert listed.source == "us" and len(listed.items) == 10

    async def test_429_본문은_rate_limited다(self) -> None:
        session = Session([Resp(fixture("yahoo_us_latest_noua.html"), 429)])
        async with client(session) as news:
            with pytest.raises(NewsRateLimited):
                await news.fetch("us")
