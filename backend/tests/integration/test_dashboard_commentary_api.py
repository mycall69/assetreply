"""지표 모달의 변화 까닭 (014 반복 2026-10-10b T105) — FR-027, SC-013, contracts A8.

- 마지막 세션 이후의 시황 기사 최대 3개(출처 글자 그대로), 없으면 `status: "none"`(문장을 만들지
  않는다)
- 출처가 실패해도 200 + `failure`다. 없는 지표는 404, 서비스가 없으면 503이다
- 저장하지 않는다 — 캐시 안의 재요청은 출처를 부르지 않는다
"""

from __future__ import annotations

import dataclasses
import datetime as dt
from decimal import Decimal

import pytest
from httpx2 import ASGITransport, AsyncClient
from src.api.services.indicator_commentary import CommentaryService
from src.ingestion.news.commentary import CommentaryItem

from src.api.main import create_app
from src.api.services import indicator_commentary
from src.config.settings import load_settings
from src.ingestion.news.errors import NewsError, NewsRateLimited
from src.simulation.market_quote import MarketQuote, Previous

NOW = dt.datetime(2026, 10, 9, 13, 30, tzinfo=dt.UTC)  # 한국 22:30


def item(title: str, at: dt.datetime) -> CommentaryItem:
    return CommentaryItem(
        title=title,
        summary=f"{title} 요약",
        publisher="한국경제",
        published_at=at,
        published_text=None,
        url="https://n.news.naver.com/mnews/article/015/1",
    )


class Quotes:
    async def quote(self, indicator_id: str) -> MarketQuote | None:
        return MarketQuote(
            value=Decimal("6625.930000"),
            value_time=NOW,
            session_date=dt.date(2026, 10, 8),
            state="holiday",
            provisional=False,
            delay_minutes=None,
            previous=Previous(Decimal("6803.900000"), dt.date(2026, 10, 7), "history"),
            change=Decimal("-177.970000"),
            change_rate=Decimal("-0.026157"),
            change_rate_blank=None,
            direction="down",
        )


class Fetcher:
    def __init__(self) -> None:
        self.calls = 0
        self.items: list[CommentaryItem] = []
        self.fail: NewsError | None = None

    async def fetch(self, indicator_id: str) -> list[CommentaryItem]:
        self.calls += 1
        if self.fail is not None:
            raise self.fail
        return self.items


@pytest.fixture
def fetcher() -> Fetcher:
    return Fetcher()


@pytest.fixture
async def client(fetcher):  # type: ignore[no-untyped-def]
    settings = dataclasses.replace(load_settings(), dashboard_commentary_cache_seconds=600)
    indicator_commentary.set_shared_service(
        CommentaryService(fetcher, Quotes(), settings, clock=lambda: NOW)
    )
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    indicator_commentary.set_shared_service(None)


SESSION = dt.datetime(2026, 10, 7, 15, 0, tzinfo=dt.UTC)  # 한국 10-08 0시


async def test_세션_이후_기사_셋(client: AsyncClient, fetcher: Fetcher) -> None:
    fetcher.items = [
        item("코스피 2.62% 하락", SESSION + dt.timedelta(hours=10)),
        item("지난 세션 기사", SESSION - dt.timedelta(hours=1)),
        item("코스피 6,600선 후퇴", SESSION + dt.timedelta(hours=9)),
        item("코스피 사흘째 하락", SESSION + dt.timedelta(hours=8)),
        item("넷째", SESSION + dt.timedelta(hours=7)),
    ]
    body = (await client.get("/api/dashboard/indicators/kospi/commentary")).json()
    assert body["status"] == "ok" and body["indicator"] == "kospi"
    assert body["source"] == "네이버 증권" and body["sessionDate"] == "2026-10-08"
    assert [i["title"] for i in body["items"]] == [
        "코스피 2.62% 하락",
        "코스피 6,600선 후퇴",
        "코스피 사흘째 하락",
    ]
    first = body["items"][0]
    assert set(first) == {"title", "summary", "publisher", "publishedAt", "publishedText", "url"}
    assert (
        first["publishedAt"] == "2026-10-08T01:00:00Z"
        and first["summary"] == "코스피 2.62% 하락 요약"
    )
    assert body["failure"] is None and body["fetchedAt"] == "2026-10-09T13:30:00Z"


async def test_세션_이후_기사가_없으면_none이다(client: AsyncClient, fetcher: Fetcher) -> None:
    fetcher.items = [item("지난 세션 기사", SESSION - dt.timedelta(hours=1))]
    body = (await client.get("/api/dashboard/indicators/kospi/commentary")).json()
    assert (body["status"], body["items"], body["failure"]) == ("none", [], None)


async def test_출처가_실패해도_200이다(client: AsyncClient, fetcher: Fetcher) -> None:
    fetcher.fail = NewsRateLimited("뉴스 출처가 요청을 제한했습니다(429).")
    res = await client.get("/api/dashboard/indicators/nikkei225/commentary")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "failed" and body["failure"]["reason"] == "rate_limited"
    assert body["source"] == "Yahoo Finance"


async def test_캐시_안의_재요청은_출처를_부르지_않는다(
    client: AsyncClient, fetcher: Fetcher
) -> None:
    await client.get("/api/dashboard/indicators/kospi/commentary")
    await client.get("/api/dashboard/indicators/kospi/commentary")
    assert fetcher.calls == 1


async def test_없는_지표는_404다(client: AsyncClient) -> None:
    assert (await client.get("/api/dashboard/indicators/nope/commentary")).status_code == 404


async def test_서비스가_없으면_503이다() -> None:
    indicator_commentary.set_shared_service(None)
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get("/api/dashboard/indicators/kospi/commentary")
    assert res.status_code == 503
