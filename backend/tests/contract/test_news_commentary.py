"""변화 까닭의 시황 출처 계약 (014 반복 2026-10-10b T103) — FR-027, FR-022, SC-013, research R14-17.

**공개되지 않은 내부 API·화면 HTML**(헌법 원칙 II 이탈 — plan Complexity Tracking, 사용자 승인
2026-10-10).
**네트워크를 쓰지 않는다**(원칙 III). 실측 본문(`fixtures/news/commentary/`)을 쓴다.

- 네이버 뉴스 포커스: 제목·요약(`subcontent`) 원문, 언론사, 한국 시간 → UTC, 허용 호스트
  `n.news.naver.com`. 한국 오늘과
  어제 두 날짜를 부르고 지표 낱말로 거른다
- Yahoo 종목 뉴스: `news-stream`의 카드 — 제목(`h3`를 감싼 링크), `div.publishing`의 언론사·상대
  시각(받은 시각에서 뺀
  어림), 허용 호스트 `finance.yahoo.com`
- 실패: 목록 칸·`articles`가 없으면 `parse_empty`, JSON이 아니면 `invalid_body`. 빈 `articles`는
  실패가 아니다(그 날
  기사가 없다)
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import json
from pathlib import Path
from typing import Self

import pytest

from src.config.settings import load_settings
from src.ingestion.news import commentary
from src.ingestion.news.client import NewsClient
from src.ingestion.news.errors import NewsInvalidBody, NewsParseEmpty
from src.simulation.market_indicators import INDICATORS

FIX = Path(__file__).parent / "fixtures" / "news" / "commentary"
UA = "Mozilla/5.0 (테스트) Chrome/154.0.0.0 Safari/537.36"
# 2026-10-09 22:30 KST(금요일)
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
    """질의의 `date`(네이버)마다 다른 본문을 준다."""

    def __init__(self, bodies: dict[str, str]) -> None:
        self.bodies = bodies
        self.requests: list[tuple[str, dict[str, str], dict[str, str]]] = []

    def get(
        self,
        url: str,
        *,
        params: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
        **_: object,
    ) -> Resp:
        query = dict(params or {})
        self.requests.append((url, query, dict(headers or {})))
        return Resp(self.bodies.get(query.get("date", url), json.dumps({"articles": []})))

    async def close(self) -> None:
        return None


async def no_sleep(_: float) -> None:
    return None


def fetcher(session: Session) -> commentary.CommentaryClient:
    settings = dataclasses.replace(load_settings(), news_user_agent=UA)
    http = NewsClient(settings, session=session, sleep=no_sleep, clock=lambda: NOW)  # type: ignore[arg-type]
    return commentary.CommentaryClient(http, settings, clock=lambda: NOW)


class Test네이버_파싱:
    def test_제목_요약_언론사_시각_링크(self) -> None:
        items = commentary.parse_naver_focus(fixture("naver_focus_401.json"))
        assert len(items) == 20
        third = items[2]
        assert third.title == "삼성전자 100조 벌어도…코스피 2.62% '뚝'"
        assert third.publisher == "연합뉴스TV"
        # "20261008210809"(KST) → 12:08:09 UTC
        assert third.published_at == dt.datetime(2026, 10, 8, 12, 8, 9, tzinfo=dt.UTC)
        assert third.published_text is None
        assert third.summary is not None and third.summary.startswith(
            json.loads(fixture("naver_focus_401.json"))["articles"][2]["subcontent"][:20]
        )
        assert third.url.startswith("https://n.news.naver.com/mnews/article/422/0000913926")

    def test_허용_호스트_밖_줄은_버린다(self) -> None:
        body = json.loads(fixture("naver_focus_401.json"))
        body["articles"][0]["url"] = "https://example.com/a"
        body["articles"][1]["url"] = "http://n.news.naver.com/mnews/article/1/2"
        items = commentary.parse_naver_focus(json.dumps(body, ensure_ascii=False))
        assert len(items) == 18
        assert all(i.url.startswith("https://n.news.naver.com/") for i in items)

    def test_빈_articles는_실패가_아니다(self) -> None:
        assert commentary.parse_naver_focus(json.dumps({"articles": []})) == []

    def test_articles가_없으면_parse_empty다(self) -> None:
        with pytest.raises(NewsParseEmpty):
            commentary.parse_naver_focus(json.dumps({"page": "1"}))

    def test_JSON이_아니면_invalid_body다(self) -> None:
        with pytest.raises(NewsInvalidBody):
            commentary.parse_naver_focus("<html>점검</html>")


class TestYahoo_파싱:
    def test_종목_뉴스_카드(self) -> None:
        items = commentary.parse_yahoo_quote_news(fixture("yahoo_quote_news_HSI.html"), now=NOW)
        assert len(items) == 12
        first = items[0]
        assert first.title == "Xiaomi shares surge as SkyNomad EV lineup clocks strong orders"
        assert (first.publisher, first.published_text) == ("Investing.com", "18h ago")
        assert first.published_at == NOW - dt.timedelta(hours=18)
        assert first.url.startswith("https://finance.yahoo.com/")
        assert first.summary is None
        assert items[1].published_at == NOW - dt.timedelta(days=1)

    def test_종목_링크의_title을_제목으로_읽지_않는다(self) -> None:
        for item in commentary.parse_yahoo_quote_news(
            fixture("yahoo_quote_news_HSI.html"), now=NOW
        ):
            assert "/quote/" not in item.url
            assert not item.title.endswith(".HK")

    def test_목록_칸이_없으면_parse_empty다(self) -> None:
        with pytest.raises(NewsParseEmpty):
            commentary.parse_yahoo_quote_news(fixture("yahoo_quote_news_no_stream.html"), now=NOW)


class Test상대_시각:
    @pytest.mark.parametrize(
        ("text", "delta"),
        [
            ("4m ago", dt.timedelta(minutes=4)),
            ("18h ago", dt.timedelta(hours=18)),
            ("1d ago", dt.timedelta(days=1)),
            ("10d ago", dt.timedelta(days=10)),
            ("yesterday", dt.timedelta(days=1)),
            ("2 days ago", dt.timedelta(days=2)),
            ("2mo ago", dt.timedelta(days=60)),
        ],
    )
    def test_받은_시각에서_뺀다(self, text: str, delta: dt.timedelta) -> None:
        assert commentary.relative_instant(text, NOW) == NOW - delta

    @pytest.mark.parametrize("text", ["Oct 8", "", "어제"])
    def test_읽을_수_없으면_없다(self, text: str) -> None:
        assert commentary.relative_instant(text, NOW) is None


class Test지표마다_출처:
    def test_15개_모두_출처가_있다(self) -> None:
        for indicator in INDICATORS:
            assert commentary.source_of(indicator.id) is not None

    def test_한국_미국_환율_원유는_네이버이고_나머지는_Yahoo다(self) -> None:
        naver = {i.id for i in INDICATORS if commentary.source_of(i.id).kind == "naver"}
        assert naver == {
            "kospi",
            "kosdaq",
            "dow",
            "nasdaq",
            "sp500",
            "sox",
            "wti",
            "usd",
            "jpy",
            "eur",
        }
        assert commentary.source_of("kospi").sid == "401"
        assert commentary.source_of("sp500").sid == "403"
        assert commentary.source_of("usd").sid == "429"
        assert commentary.source_of("nikkei225").symbol == "^N225"
        assert commentary.source_of("gold").symbol == "GC=F"

    def test_낱말로_거른다(self) -> None:
        kospi = commentary.source_of("kospi")
        assert commentary.matches("삼성전자 100조 벌어도…코스피 2.62% '뚝'", kospi.keywords)
        assert not commentary.matches("레버리지 ETF에 고개 숙인 이억원", kospi.keywords)


class Test요청:
    async def test_네이버는_한국_오늘과_어제_두_날짜이고_낱말로_거른다(self) -> None:
        session = Session({"20261008": fixture("naver_focus_401.json")})
        items = await fetcher(session).fetch("kospi")
        dates = [q.get("date") for _, q, _ in session.requests]
        assert dates == ["20261009", "20261008"]
        url, query, headers = session.requests[0]
        assert url == "https://stock.naver.com/api/domestic/news/focus"
        assert (query["sid"], query["page"], query["pageSize"]) == ("401", "1", "50")
        assert headers["User-Agent"] == UA and headers["Accept-Language"].startswith("ko-KR")
        assert len(items) == 5
        assert all("코스피" in i.title for i in items)

    async def test_Yahoo는_종목_뉴스_주소다(self) -> None:
        url = "https://finance.yahoo.com/quote/%5EHSI/news/"
        session = Session({url: fixture("yahoo_quote_news_HSI.html")})
        items = await fetcher(session).fetch("hangseng")
        assert session.requests[0][0] == url
        assert session.requests[0][2]["Accept-Language"].startswith("en-US")
        assert len(items) == 12
