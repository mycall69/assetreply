"""`GET /api/dashboard/news/{source}` (014 T068) — FR-020, FR-023, FR-024, SC-007, SC-008, contracts
A5.

출처는 실측 본문(`contract/fixtures/news/`)을 주소마다 돌려주는 가짜 HTTP 세션이다(네트워크 없음).
뉴스는
저장하지 않는다 — DB를 쓰지 않는다.

- 세 칸의 성공 본문이 contracts A5의 칸 이름이다
- 한 칸이 실패해도 200이고 `status: "failed"` + `failure`다. 다른 칸은 그대로 성공이다
- 틀린 `source`는 404다
- 캐시 안의 재요청은 출처를 부르지 않는다
"""

from __future__ import annotations

import dataclasses
import datetime as dt
from pathlib import Path
from typing import Self

import pytest
from httpx2 import ASGITransport, AsyncClient

from src.api.main import create_app
from src.api.services import news_cache
from src.api.services.news_cache import NewsCache
from src.config.settings import load_settings
from src.ingestion.news.client import NewsClient

FIX = Path(__file__).parents[1] / "contract" / "fixtures" / "news"
NOW = dt.datetime(2026, 10, 9, 13, 30, tzinfo=dt.UTC)
BODIES = {
    "https://stock.naver.com/api/domestic/news/list": "naver_mainnews.json",
    "https://finance.yahoo.com/topic/latest-news/": "yahoo_us_latest.html",
    "https://finance.yahoo.co.jp/news/headline": "yahoo_jp_headline.html",
}
ITEM_KEYS = {
    "rank",
    "title",
    "url",
    "publisher",
    "publishedAt",
    "publishedDate",
    "publishedText",
    "paid",
}


class Resp:
    def __init__(self, body: str, status: int) -> None:
        self._body = body
        self.status = status

    async def text(self) -> str:
        return self._body

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *exc: object) -> None:
        return None


class Portal:
    """주소마다 픽스처 본문. `status`를 바꾸면 그 주소가 실패한다."""

    def __init__(self) -> None:
        self.calls: list[str] = []
        self.status: dict[str, int] = {}

    def get(self, url: str, **_: object) -> Resp:
        self.calls.append(url)
        status = self.status.get(url, 200)
        body = (FIX / BODIES[url]).read_text(encoding="utf-8") if status == 200 else "blocked"
        return Resp(body, status)

    async def close(self) -> None:
        return None


async def no_sleep(_: float) -> None:
    return None


@pytest.fixture
def portal() -> Portal:
    return Portal()


@pytest.fixture
async def client(portal):  # type: ignore[no-untyped-def]
    settings = dataclasses.replace(load_settings(), news_retry_max_attempts=1)
    news = NewsClient(settings, session=portal, sleep=no_sleep, clock=lambda: NOW)
    news_cache.set_shared_service(NewsCache(news, settings, clock=lambda: NOW))
    app = create_app()
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            yield ac
    finally:
        news_cache.set_shared_service(None)


async def test_세_칸의_성공_본문은_contracts_A5다(client) -> None:  # type: ignore[no-untyped-def]
    for source, name, items in (
        ("kr", "네이버 증권", 10),
        ("us", "Yahoo Finance", 10),
        ("jp", "Yahoo!ファイナンス", 10),
    ):
        response = await client.get(f"/api/dashboard/news/{source}")
        assert response.status_code == 200
        body = response.json()
        assert set(body) == {
            "source",
            "sourceName",
            "sourceUrl",
            "list",
            "status",
            "fetchedAt",
            "items",
            "failure",
        }
        assert (body["source"], body["sourceName"], body["status"]) == (source, name, "ok")
        assert body["fetchedAt"] == "2026-10-09T13:30:00Z"
        assert body["failure"] is None
        assert len(body["items"]) == items
        for row in body["items"]:
            assert set(row) == ITEM_KEYS


async def test_칸마다_시각의_꼴이_다르다(client) -> None:  # type: ignore[no-untyped-def]
    kr = (await client.get("/api/dashboard/news/kr")).json()["items"][0]
    us = (await client.get("/api/dashboard/news/us")).json()["items"][0]
    jp = (await client.get("/api/dashboard/news/jp")).json()["items"][0]
    assert (kr["publishedAt"], kr["publishedText"]) == ("2026-10-09T13:12:14Z", None)
    assert kr["url"] == "https://n.news.naver.com/article/015/0005340952"
    assert (us["publishedAt"], us["publishedText"]) == (None, "4m ago")
    assert (jp["publishedAt"], jp["publishedDate"]) == ("2026-10-09T13:20:00Z", None)


async def test_한_칸이_실패해도_200이고_다른_칸은_성공이다(client, portal) -> None:  # type: ignore[no-untyped-def]
    portal.status["https://finance.yahoo.com/topic/latest-news/"] = 429
    us = await client.get("/api/dashboard/news/us")
    assert us.status_code == 200
    body = us.json()
    assert (body["status"], body["items"], body["fetchedAt"]) == ("failed", [], None)
    assert body["failure"]["reason"] == "rate_limited"
    assert body["failure"]["retryAfterSeconds"] == 60
    assert (await client.get("/api/dashboard/news/kr")).json()["status"] == "ok"
    assert (await client.get("/api/dashboard/news/jp")).json()["status"] == "ok"


async def test_틀린_칸은_404다(client) -> None:  # type: ignore[no-untyped-def]
    response = await client.get("/api/dashboard/news/cn")
    assert response.status_code == 404
    assert response.json()["status"] == "unknown_source"


async def test_캐시_안의_재요청은_출처를_부르지_않는다(client, portal) -> None:  # type: ignore[no-untyped-def]
    first = (await client.get("/api/dashboard/news/kr")).json()
    calls = len(portal.calls)
    again = (await client.get("/api/dashboard/news/kr")).json()
    assert len(portal.calls) == calls
    assert again == first


async def test_실패_기억_안의_재요청도_출처를_부르지_않는다(client, portal) -> None:  # type: ignore[no-untyped-def]
    portal.status["https://finance.yahoo.co.jp/news/headline"] = 503
    await client.get("/api/dashboard/news/jp")
    calls = len(portal.calls)
    again = (await client.get("/api/dashboard/news/jp")).json()
    assert len(portal.calls) == calls
    assert again["failure"]["reason"] == "connection"


async def test_서비스가_없으면_503이다() -> None:
    news_cache.set_shared_service(None)
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/dashboard/news/kr")
    assert response.status_code == 503
