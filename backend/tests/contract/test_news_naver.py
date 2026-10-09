"""네이버 증권 주요뉴스 계약 (014 T064) — FR-020~FR-022, FR-024, SC-007, SC-008, research R14-13.

**공개되지 않은 내부 API**(헌법 원칙 II 이탈 — plan Complexity Tracking, 사용자 승인 2026-10-09).
**네트워크를 쓰지 않는다**(원칙 III). 실측 본문(`fixtures/news/`)을 쓴다.

- 15개를 받아 **같은 제목은 한 번**(MBN 두 건) 센 뒤 위에서 10개다
- 칸: 제목 원문·언론사, `datetime`(오프셋 없는 KST) → UTC, 링크는 응답에 없어 기사 번호로 만든다
- 요청: `category=MAINNEWS`·`page=1`·`pageSize=15`, 브라우저형 UA·`Accept-Language: ko-KR`
- 실패: `articles` 없음 → `parse_empty`, 403 → `blocked`, 429 → `rate_limited`, 연결 오류 →
  `connection`
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import json
from pathlib import Path
from typing import Self

import aiohttp
import pytest

from src.config.settings import Settings, load_settings
from src.ingestion.news import naver
from src.ingestion.news.client import NewsClient
from src.ingestion.news.errors import (
    NewsBlocked,
    NewsConnectionError,
    NewsInvalidBody,
    NewsParseEmpty,
    NewsRateLimited,
)

FIX = Path(__file__).parent / "fixtures" / "news"
UA = "Mozilla/5.0 (테스트) Chrome/154.0.0.0 Safari/537.36"
NOW = dt.datetime(2026, 10, 9, 13, 30, tzinfo=dt.UTC)


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
    def __init__(self, replies: list[Resp | Exception]) -> None:
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
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply

    async def close(self) -> None:
        return None


async def no_sleep(_: float) -> None:
    return None


def settings(**over: object) -> Settings:
    base: dict[str, object] = {"news_user_agent": UA, "news_retry_max_attempts": 2}
    base.update(over)
    return dataclasses.replace(load_settings(), **base)  # type: ignore[arg-type]


def client(session: Session, **over: object) -> NewsClient:
    return NewsClient(
        settings(**over),
        session=session,  # type: ignore[arg-type]
        sleep=no_sleep,
        clock=lambda: NOW,
    )


class Test파싱:
    def test_같은_제목은_한_번_세고_위에서_10개다(self) -> None:
        items = naver.parse(fixture("naver_mainnews.json"))
        articles = json.loads(fixture("naver_mainnews.json"))["articles"]
        # 4번째(0부터 셈) 기사가 2번째와 같은 제목이다 — 빼고 위에서 10개
        expected = [articles[i]["title"] for i in (0, 1, 2, 3, 5, 6, 7, 8, 9, 10)]
        assert [i.title for i in items] == expected
        assert [i.rank for i in items] == list(range(1, 11))
        titles = [i.title for i in items]
        assert titles.count("70억짜리 12억 하락, 분당은 5억 올라…경매도 서울보다 경기 남부") == 1

    def test_칸은_제목_원문_언론사_UTC_시각_기사_링크다(self) -> None:
        first = naver.parse(fixture("naver_mainnews.json"))[0]
        assert first.title == "\"하루에 1조 벌었는데…\" 한국 개미들 다시 '미장' 가는 이유 [분석+]"
        assert first.publisher == "한국경제"
        # "2026-10-09 22:12:14"(KST) → 13:12:14 UTC
        assert first.published_at == dt.datetime(2026, 10, 9, 13, 12, 14, tzinfo=dt.UTC)
        assert first.published_date is None and first.published_text is None
        assert first.url == "https://n.news.naver.com/article/015/0005340952"
        assert first.paid is False

    def test_허용_도메인_밖_링크가_없다(self) -> None:
        for item in naver.parse(fixture("naver_mainnews.json")):
            assert item.url.startswith("https://n.news.naver.com/article/")

    def test_기사_번호가_숫자가_아니면_그_줄을_버린다(self) -> None:
        body = json.loads(fixture("naver_mainnews.json"))
        body["articles"][0]["officeId"] = "../x"
        body["articles"][1]["articleId"] = ""
        items = naver.parse(json.dumps(body, ensure_ascii=False))
        assert items[0].url == "https://n.news.naver.com/article/057/0001972681"
        assert len(items) == 10

    def test_시각을_읽지_못하면_시각만_비운다(self) -> None:
        body = json.loads(fixture("naver_mainnews.json"))
        body["articles"][0]["datetime"] = "어제"
        first = naver.parse(json.dumps(body, ensure_ascii=False))[0]
        assert first.published_at is None and first.title.startswith('"하루에 1조')

    def test_10개보다_적으면_있는_만큼이다(self) -> None:
        body = json.loads(fixture("naver_mainnews.json"))
        body["articles"] = body["articles"][:3]
        assert len(naver.parse(json.dumps(body, ensure_ascii=False))) == 3

    def test_articles가_없으면_parse_empty다(self) -> None:
        with pytest.raises(NewsParseEmpty):
            naver.parse(fixture("naver_no_articles.json"))

    def test_articles가_비면_parse_empty다(self) -> None:
        with pytest.raises(NewsParseEmpty):
            naver.parse(json.dumps({"articles": []}))

    def test_JSON이_아니면_invalid_body다(self) -> None:
        with pytest.raises(NewsInvalidBody):
            naver.parse("<html>점검 중</html>")


class Test요청:
    async def test_질의와_머리(self) -> None:
        session = Session([Resp(fixture("naver_mainnews.json"))])
        async with client(session) as news:
            listed = await news.fetch("kr")
        url, params, headers = session.requests[0]
        assert url == "https://stock.naver.com/api/domestic/news/list"
        assert params == {"category": "MAINNEWS", "page": "1", "pageSize": "15"}
        assert headers["User-Agent"] == UA
        assert headers["Accept-Language"].startswith("ko-KR")
        assert listed.source == "kr" and listed.fetched_at == NOW and len(listed.items) == 10

    async def test_주소는_설정이다(self) -> None:
        session = Session([Resp(fixture("naver_mainnews.json"))])
        async with client(session, news_kr_url="https://example.test/news") as news:
            await news.fetch("kr")
        assert session.requests[0][0] == "https://example.test/news"

    async def test_403은_blocked이고_다시_시도하지_않는다(self) -> None:
        session = Session([Resp("forbidden", 403), Resp(fixture("naver_mainnews.json"))])
        async with client(session) as news:
            with pytest.raises(NewsBlocked):
                await news.fetch("kr")
        assert len(session.requests) == 1

    async def test_429는_rate_limited이고_다시_시도하지_않는다(self) -> None:
        session = Session([Resp("too many", 429), Resp(fixture("naver_mainnews.json"))])
        async with client(session) as news:
            with pytest.raises(NewsRateLimited):
                await news.fetch("kr")
        assert len(session.requests) == 1

    async def test_연결_오류는_다시_시도한_뒤_connection이다(self) -> None:
        session = Session([aiohttp.ClientConnectionError("x"), TimeoutError()])
        async with client(session) as news:
            with pytest.raises(NewsConnectionError):
                await news.fetch("kr")
        assert len(session.requests) == 2

    async def test_연결_오류_뒤_성공하면_목록이다(self) -> None:
        session = Session(
            [aiohttp.ClientConnectionError("x"), Resp(fixture("naver_mainnews.json"))]
        )
        async with client(session) as news:
            listed = await news.fetch("kr")
        assert len(listed.items) == 10

    async def test_5xx는_connection이다(self) -> None:
        session = Session([Resp("down", 503), Resp("down", 503)])
        async with client(session) as news:
            with pytest.raises(NewsConnectionError) as caught:
                await news.fetch("kr")
        assert "503" in str(caught.value)
