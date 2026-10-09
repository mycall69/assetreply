"""뉴스 캐시 (014 T067) — FR-023, FR-024, research R14-13, contracts A5.

가짜 출처·가짜 시계를 쓴다(DB·HTTP 없음).

- **성공 캐시**: 600초 안의 재요청은 출처를 부르지 않는다. 601초 뒤는 다시 부른다
- **실패 기억**: 60초부터 연달아 실패하면 두 배씩 600초까지 늘린다. 성공하면 처음으로 돌아간다. 남은
  시간이 `retryAfterSeconds`다
- **단일 비행**: 같은 칸의 동시 요청은 출처를 한 번 부른다
- **칸 사이**: 한 칸의 실패가 다른 칸에 영향이 없다
- **사건**(반복 2026-10-10 T089 — FR-023, SC-008): 출처를 부를 때마다 `news_fetch` 한 줄이다
  - 캐시·실패 기억 안의 재요청은 출처를 부르지 않으므로 줄도 없다
  - 운영자가 캐시가 출처 호출을 막는지 이 줄로 본다
"""

from __future__ import annotations

import asyncio
import dataclasses
import datetime as dt

from _pytest.monkeypatch import MonkeyPatch

from src.api.services import news_cache
from src.api.services.news_cache import NewsCache
from src.config.settings import load_settings
from src.ingestion.news.errors import NewsConnectionError, NewsError, NewsParseEmpty
from src.ingestion.news.types import NewsItem, NewsList, SourceKey

START = dt.datetime(2026, 10, 9, 13, 0, tzinfo=dt.UTC)


class Clock:
    def __init__(self) -> None:
        self.now = START

    def __call__(self) -> dt.datetime:
        return self.now

    def advance(self, seconds: int) -> None:
        self.now += dt.timedelta(seconds=seconds)


def item(rank: int, title: str) -> NewsItem:
    return NewsItem(
        rank=rank,
        title=title,
        url=f"https://n.news.naver.com/article/015/{rank:010d}",
        publisher="한국경제",
        published_at=dt.datetime(2026, 10, 9, 12, rank, tzinfo=dt.UTC),
        published_date=None,
        published_text=None,
        paid=False,
    )


class FakeSource:
    def __init__(self, clock: Clock) -> None:
        self.clock = clock
        self.calls: dict[str, int] = {"kr": 0, "us": 0, "jp": 0}
        self.failures: dict[str, NewsError | None] = {"kr": None, "us": None, "jp": None}
        self.hold: asyncio.Event | None = None

    async def fetch(self, source: SourceKey) -> NewsList:
        self.calls[source] += 1
        if self.hold is not None:
            await self.hold.wait()
        failure = self.failures[source]
        if failure is not None:
            raise failure
        return NewsList(
            source=source, fetched_at=self.clock(), items=(item(1, f"{source} 첫 기사"),)
        )


def cache(clock: Clock, source: FakeSource) -> NewsCache:
    settings = dataclasses.replace(
        load_settings(),
        news_cache_seconds=600,
        news_failure_cache_seconds=60,
        news_failure_cache_max_seconds=600,
    )
    return NewsCache(source, settings, clock=clock)


class Test성공_캐시:
    async def test_600초_안은_출처를_부르지_않는다(self) -> None:
        clock = Clock()
        source = FakeSource(clock)
        news = cache(clock, source)
        first = await news.body("kr")
        clock.advance(599)
        again = await news.body("kr")
        assert source.calls["kr"] == 1
        assert again == first
        assert first["fetchedAt"] == "2026-10-09T13:00:00Z"

    async def test_601초_뒤는_다시_부른다(self) -> None:
        clock = Clock()
        source = FakeSource(clock)
        news = cache(clock, source)
        await news.body("kr")
        clock.advance(601)
        later = await news.body("kr")
        assert source.calls["kr"] == 2
        assert later["fetchedAt"] == "2026-10-09T13:10:01Z"


class Test응답:
    async def test_성공_본문은_contracts_A5다(self) -> None:
        clock = Clock()
        news = cache(clock, FakeSource(clock))
        body = await news.body("kr")
        assert body == {
            "source": "kr",
            "sourceName": "네이버 증권",
            "sourceUrl": "https://stock.naver.com/news",
            "list": "주요뉴스",
            "status": "ok",
            "fetchedAt": "2026-10-09T13:00:00Z",
            "items": [
                {
                    "rank": 1,
                    "title": "kr 첫 기사",
                    "url": "https://n.news.naver.com/article/015/0000000001",
                    "publisher": "한국경제",
                    "publishedAt": "2026-10-09T12:01:00Z",
                    "publishedDate": None,
                    "publishedText": None,
                    "paid": False,
                }
            ],
            "failure": None,
        }

    async def test_받은_시각은_초까지다(self) -> None:
        """contracts A5의 꼴(`2026-10-09T13:12:30Z`) — 실측에서 마이크로초가 붙었다(T081)."""
        clock = Clock()
        clock.now = START.replace(microsecond=499_903)
        body = await cache(clock, FakeSource(clock)).body("kr")
        assert body["fetchedAt"] == "2026-10-09T13:00:00Z"

    async def test_칸의_이름과_목록(self) -> None:
        clock = Clock()
        news = cache(clock, FakeSource(clock))
        us, jp = await news.body("us"), await news.body("jp")
        assert (us["sourceName"], us["sourceUrl"], us["list"]) == (
            "Yahoo Finance",
            "https://finance.yahoo.com/topic/latest-news/",
            "Latest News",
        )
        assert (jp["sourceName"], jp["sourceUrl"], jp["list"]) == (
            "Yahoo!ファイナンス",
            "https://finance.yahoo.co.jp/news",
            "ヘッドライン",
        )

    async def test_날짜만_있는_기사는_publishedDate다(self) -> None:
        clock = Clock()
        source = FakeSource(clock)

        async def dated(key: SourceKey) -> NewsList:
            only = dataclasses.replace(
                item(1, "見出し"), published_at=None, published_date=dt.date(2026, 10, 8), paid=True
            )
            return NewsList(source=key, fetched_at=clock(), items=(only,))

        source.fetch = dated  # type: ignore[method-assign]
        body = await cache(clock, source).body("jp")
        row = body["items"][0]  # type: ignore[index]
        assert (row["publishedAt"], row["publishedDate"], row["paid"]) == (None, "2026-10-08", True)

    async def test_실패_본문(self) -> None:
        clock = Clock()
        source = FakeSource(clock)
        source.failures["us"] = NewsParseEmpty("기사를 하나도 읽지 못했습니다.")
        body = await cache(clock, source).body("us")
        assert body["status"] == "failed"
        assert body["items"] == []
        assert body["fetchedAt"] is None
        assert body["failure"] == {
            "reason": "parse_empty",
            "message": "기사를 하나도 읽지 못했습니다.",
            "retryAfterSeconds": 60,
        }


class Test실패_기억:
    async def test_기억이_남은_동안은_출처를_부르지_않고_남은_시간을_준다(self) -> None:
        clock = Clock()
        source = FakeSource(clock)
        source.failures["kr"] = NewsConnectionError("연결하지 못했습니다.")
        news = cache(clock, source)
        await news.body("kr")
        clock.advance(25)
        body = await news.body("kr")
        assert source.calls["kr"] == 1
        assert body["failure"]["retryAfterSeconds"] == 35  # type: ignore[index]

    async def test_연달아_실패하면_두_배씩_600초까지(self) -> None:
        clock = Clock()
        source = FakeSource(clock)
        source.failures["kr"] = NewsConnectionError("연결하지 못했습니다.")
        news = cache(clock, source)
        seen: list[object] = []
        for _ in range(6):
            body = await news.body("kr")
            retry = body["failure"]["retryAfterSeconds"]  # type: ignore[index]
            seen.append(retry)
            clock.advance(int(retry))  # type: ignore[call-overload]
        assert seen == [60, 120, 240, 480, 600, 600]
        assert source.calls["kr"] == 6

    async def test_성공하면_처음으로_돌아간다(self) -> None:
        clock = Clock()
        source = FakeSource(clock)
        source.failures["kr"] = NewsConnectionError("연결하지 못했습니다.")
        news = cache(clock, source)
        await news.body("kr")
        clock.advance(60)
        await news.body("kr")  # 120
        clock.advance(120)
        source.failures["kr"] = None
        assert (await news.body("kr"))["status"] == "ok"
        clock.advance(601)
        source.failures["kr"] = NewsConnectionError("연결하지 못했습니다.")
        body = await news.body("kr")
        assert body["failure"]["retryAfterSeconds"] == 60  # type: ignore[index]


class Test단일_비행:
    async def test_동시_두_요청은_출처를_한_번_부른다(self) -> None:
        clock = Clock()
        source = FakeSource(clock)
        source.hold = asyncio.Event()
        news = cache(clock, source)
        first = asyncio.create_task(news.body("kr"))
        second = asyncio.create_task(news.body("kr"))
        await asyncio.sleep(0)
        source.hold.set()
        a, b = await asyncio.gather(first, second)
        assert source.calls["kr"] == 1
        assert a == b


class Test칸_사이:
    async def test_한_칸의_실패가_다른_칸에_영향이_없다(self) -> None:
        clock = Clock()
        source = FakeSource(clock)
        source.failures["us"] = NewsConnectionError("연결하지 못했습니다.")
        news = cache(clock, source)
        assert (await news.body("us"))["status"] == "failed"
        assert (await news.body("kr"))["status"] == "ok"
        assert (await news.body("jp"))["status"] == "ok"
        assert source.calls == {"kr": 1, "us": 1, "jp": 1}

    async def test_느린_칸이_다른_칸을_막지_않는다(self) -> None:
        clock = Clock()
        source = FakeSource(clock)
        news = cache(clock, source)
        hold = asyncio.Event()
        original = source.fetch

        async def slow(key: SourceKey) -> NewsList:
            if key == "us":
                await hold.wait()
            return await original(key)

        source.fetch = slow  # type: ignore[method-assign]
        pending = asyncio.create_task(news.body("us"))
        kr = await asyncio.wait_for(news.body("kr"), timeout=1)
        assert kr["status"] == "ok" and not pending.done()
        hold.set()
        assert (await pending)["status"] == "ok"


Events = list[tuple[str, dict[str, object]]]


def capture(monkeypatch: MonkeyPatch) -> Events:
    seen: Events = []
    monkeypatch.setattr(news_cache, "_event", lambda name, **fields: seen.append((name, fields)))
    return seen


class Test사건:
    async def test_부를_때마다_한_줄이고_캐시_안은_없다(self, monkeypatch: MonkeyPatch) -> None:
        events = capture(monkeypatch)
        clock = Clock()
        news = cache(clock, FakeSource(clock))
        await news.body("kr")
        clock.advance(599)
        await news.body("kr")
        assert events == [("news_fetch", {"source": "kr", "status": "ok", "items": 1})]

    async def test_실패는_까닭과_함께이고_기억_안은_없다(self, monkeypatch: MonkeyPatch) -> None:
        events = capture(monkeypatch)
        clock = Clock()
        source = FakeSource(clock)
        source.failures["us"] = NewsConnectionError("연결하지 못했습니다.")
        news = cache(clock, source)
        await news.body("us")
        clock.advance(30)
        await news.body("us")
        assert events == [
            (
                "news_fetch",
                {
                    "source": "us",
                    "status": "failed",
                    "reason": "connection",
                    "message": "연결하지 못했습니다.",
                },
            )
        ]
