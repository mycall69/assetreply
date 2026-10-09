"""Yahoo!ファイナンス ヘッドライン 계약 (014 T066) — FR-020~FR-022, FR-024, SC-007, SC-008, research
R14-13.

**화면 HTML의 상태 JSON을 읽는다**(헌법 원칙 II 이탈 — plan Complexity Tracking, 사용자 승인
2026-10-09).
**네트워크를 쓰지 않는다**(원칙 III). 실측 본문(`fixtures/news/`)을 쓴다.

- `window.__PRELOADED_STATE__`의 `mainNewsCategory`(`title.name == "ヘッドライン"`) 목록의 위 10개
- **시각**: 오늘 기사 `"22:20"` + `pageInfo.currentDateTime`의 JST 날짜 → `publishedAt`(정확), 지난
  날 `"10/8"` →
  `publishedDate`(날짜만). 연도는 기준 날짜에서 추정한다 — 기준이 1월인데 `"12/30"`이면 지난해다
- `isPaidArticle` → `paid`
- `finance.yahoo.co.jp` 밖 링크 줄은 버린다
- 실패: 상태 키 없음 → `parse_empty`, 상태 JSON이 깨짐 → `invalid_body`
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import json
from collections.abc import Callable
from pathlib import Path
from typing import Self

import pytest

from src.config.settings import load_settings
from src.ingestion.news import yahoo_jp
from src.ingestion.news.client import NewsClient
from src.ingestion.news.errors import NewsInvalidBody, NewsParseEmpty

FIX = Path(__file__).parent / "fixtures" / "news"
UA = "Mozilla/5.0 (테스트) Chrome/154.0.0.0 Safari/537.36"
# 기준(`currentDateTime`)은 본문에 있다 — 이 시각은 본문에 기준이 없을 때만 쓴다
NOW = dt.datetime(2026, 10, 9, 13, 30, tzinfo=dt.UTC)
MARK = "window.__PRELOADED_STATE__ = "
JST = dt.timezone(dt.timedelta(hours=9))

Json = dict[str, object]


def fixture(name: str) -> str:
    return (FIX / name).read_text(encoding="utf-8")


def edited(name: str, change: Callable[[dict], None]) -> str:  # type: ignore[type-arg]
    """픽스처 본문의 상태 JSON을 고친 사본 — 실측에 없는 상황(유료·1월 기준·다른 도메인)."""
    html = fixture(name)
    start = html.index(MARK) + len(MARK)
    state, end = json.JSONDecoder().raw_decode(html[start:])
    change(state)
    return html[:start] + json.dumps(state, ensure_ascii=False) + html[start + end :]


def articles(state: dict) -> list[dict]:  # type: ignore[type-arg]
    return state["mainNewsCategory"]["news"]["articles"]  # type: ignore[no-any-return]


def epoch_ms(moment: dt.datetime) -> str:
    return str(int(moment.timestamp() * 1000))


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


class Test파싱:
    def test_ヘッドライン_목록의_위_10개다(self) -> None:
        items = yahoo_jp.parse(fixture("yahoo_jp_headline.html"), now=NOW)
        assert len(items) == 10
        assert [i.rank for i in items] == list(range(1, 11))
        assert items[0].title == "60歳からの残り35～40年、安心して暮らすために備えておきたいこと3つ"
        assert items[0].publisher == "あるじゃん（All About マネー）"
        assert items[0].url == (
            "https://finance.yahoo.co.jp/news/detail/426c191460b8585ab73a1383cf1faeead31b13a3"
        )
        assert items[9].title == "NY株見通しー底堅い展開か　ミシガン大期待インフレ率に注目"

    def test_오늘_시각은_기준_날짜와_합친_UTC다(self) -> None:
        items = yahoo_jp.parse(fixture("yahoo_jp_headline.html"), now=NOW)
        # 기준 2026-10-09 22:29 JST, "22:20" → 2026-10-09 13:20 UTC
        assert items[0].published_at == dt.datetime(2026, 10, 9, 13, 20, tzinfo=dt.UTC)
        assert items[0].published_date is None and items[0].published_text is None

    def test_앞_0_없는_시각과_지난_날을_함께_읽는다(self) -> None:
        def tail(state: dict) -> None:  # type: ignore[type-arg]
            state["mainNewsCategory"]["news"]["articles"] = articles(state)[10:]

        items = yahoo_jp.parse(edited("yahoo_jp_headline_p12.html", tail), now=NOW)
        # "1:49" — 기준 날짜(10-09 JST)의 01:49 → 10-08 16:49 UTC
        assert items[0].published_at == dt.datetime(2026, 10, 8, 16, 49, tzinfo=dt.UTC)
        # "10/8" — 날짜만
        assert items[5].published_at is None
        assert items[5].published_date == dt.date(2026, 10, 8)

    def test_기준이_1월인데_12월_날짜면_지난해다(self) -> None:
        def january(state: dict) -> None:  # type: ignore[type-arg]
            state["pageInfo"]["currentDateTime"] = epoch_ms(
                dt.datetime(2027, 1, 2, 9, 0, tzinfo=JST)
            )
            articles(state)[0]["createTime"] = "12/30"
            articles(state)[1]["createTime"] = "1/1"

        items = yahoo_jp.parse(edited("yahoo_jp_headline.html", january), now=NOW)
        assert items[0].published_date == dt.date(2026, 12, 30)
        assert items[1].published_date == dt.date(2027, 1, 1)

    def test_기준_시각보다_늦은_오늘_시각은_전날이다(self) -> None:
        """자정 직후의 쪽에 어제 늦은 시각이 시각 꼴로 남아도 앞으로의 시각을 만들지 않는다."""

        def after_midnight(state: dict) -> None:  # type: ignore[type-arg]
            state["pageInfo"]["currentDateTime"] = epoch_ms(
                dt.datetime(2026, 10, 10, 0, 10, tzinfo=JST)
            )
            articles(state)[0]["createTime"] = "23:55"

        items = yahoo_jp.parse(edited("yahoo_jp_headline.html", after_midnight), now=NOW)
        assert items[0].published_at == dt.datetime(2026, 10, 9, 14, 55, tzinfo=dt.UTC)

    def test_isPaidArticle은_유료다(self) -> None:
        def paid(state: dict) -> None:  # type: ignore[type-arg]
            articles(state)[2]["isPaidArticle"] = True

        items = yahoo_jp.parse(edited("yahoo_jp_headline.html", paid), now=NOW)
        assert [i.paid for i in items[:4]] == [False, False, True, False]

    def test_허용_도메인_밖_링크_줄은_버린다(self) -> None:
        def outside(state: dict) -> None:  # type: ignore[type-arg]
            articles(state)[0]["link"] = "https://news.example.jp/a/1"
            articles(state)[1]["link"] = "http://finance.yahoo.co.jp/news/detail/plain"

        items = yahoo_jp.parse(edited("yahoo_jp_headline.html", outside), now=NOW)
        assert (
            items[0].title
            == "アングル：日韓で不正アクセスの「じゅうたん爆撃」、ＡＩ使いサイバー攻撃が手軽に"
        )
        assert len(items) == 10
        assert all(i.url.startswith("https://finance.yahoo.co.jp/") for i in items)

    def test_다른_목록이면_parse_empty다(self) -> None:
        def other(state: dict) -> None:  # type: ignore[type-arg]
            state["mainNewsCategory"]["title"]["name"] = "マーケット"

        with pytest.raises(NewsParseEmpty):
            yahoo_jp.parse(edited("yahoo_jp_headline.html", other), now=NOW)

    def test_기준이_없으면_받은_시각의_JST_날짜다(self) -> None:
        def no_reference(state: dict) -> None:  # type: ignore[type-arg]
            del state["pageInfo"]["currentDateTime"]

        items = yahoo_jp.parse(edited("yahoo_jp_headline.html", no_reference), now=NOW)
        assert items[0].published_at == dt.datetime(2026, 10, 9, 13, 20, tzinfo=dt.UTC)

    def test_상태_키가_없으면_parse_empty다(self) -> None:
        with pytest.raises(NewsParseEmpty):
            yahoo_jp.parse(fixture("yahoo_jp_no_state.html"), now=NOW)

    def test_상태_JSON이_깨지면_invalid_body다(self) -> None:
        broken = fixture("yahoo_jp_headline.html").replace(MARK + "{", MARK + "{,", 1)
        with pytest.raises(NewsInvalidBody):
            yahoo_jp.parse(broken, now=NOW)


class Test요청:
    async def test_주소와_머리(self) -> None:
        session = Session([Resp(fixture("yahoo_jp_headline.html"))])
        settings = dataclasses.replace(load_settings(), news_user_agent=UA)
        async with NewsClient(
            settings,
            session=session,  # type: ignore[arg-type]
            sleep=no_sleep,
            clock=lambda: NOW,
        ) as news:
            listed = await news.fetch("jp")
        url, params, headers = session.requests[0]
        assert url == "https://finance.yahoo.co.jp/news/headline"
        assert params == {}
        assert headers["User-Agent"] == UA
        assert headers["Accept-Language"].startswith("ja-JP")
        assert listed.source == "jp" and len(listed.items) == 10
