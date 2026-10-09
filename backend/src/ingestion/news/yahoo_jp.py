"""Yahoo!ファイナンス ヘッドライン (014 T075) — FR-020~FR-022, research R14-13.

**화면 HTML의 상태 JSON을 읽는다**(헌법 원칙 II 이탈 — plan Complexity Tracking, 사용자 승인
2026-10-09). 서버가 그린
화면에 `window.__PRELOADED_STATE__ = {…}`가 있다 — 그 뒤를 `json.JSONDecoder().raw_decode`로
읽는다(정규식으로 끝을
찾지 않는다 — 문자열 안의 `}`·`;`에 걸린다).

- 목록은 `mainNewsCategory`이고 이름이 "ヘッドライン"이어야 한다 — 다른 목록이면 읽지 않는다(FR-020
  — 다른 목록과 섞지
  않는다)
- **시각**: 오늘 기사는 `"22:20"`(앞 0 없을 수 있음), 지난 기사는 `"10/8"`이다. 기준은
  `pageInfo.currentDateTime`(밀리초)의
  일본 날짜다. 오늘 기사는 날짜 + 시각(정확 — `published_at`), 지난 기사는 날짜만(`published_date`)
  - 연도는 기준 날짜에서 정한다 — 달·날이 기준보다 뒤면 지난해다(1월에 본 `"12/30"`)
  - 오늘 꼴의 시각이 기준보다 한 시간 넘게 뒤면 전날이다(자정 직후의 쪽) — 앞으로의 시각을 만들지
    않는다
- `isPaidArticle`이 참이면 유료다(FR-021)
"""

from __future__ import annotations

import datetime as dt
import json
import re
from typing import Final
from zoneinfo import ZoneInfo

from src.ingestion.news.errors import NewsInvalidBody, NewsParseEmpty
from src.ingestion.news.types import NewsItem, TextFetcher, absolute_url, pick_top

ACCEPT_LANGUAGE: Final = "ja-JP,ja;q=0.9"
HOST: Final = "finance.yahoo.co.jp"
LIST_NAME: Final = "ヘッドライン"
_BASE: Final = f"https://{HOST}/"
_MARK: Final = "window.__PRELOADED_STATE__"
_JST: Final = ZoneInfo("Asia/Tokyo")
_TIME: Final = re.compile(r"(\d{1,2}):(\d{2})")
_DATE: Final = re.compile(r"(\d{1,2})/(\d{1,2})")
#: 기준보다 이만큼 넘게 뒤인 오늘 꼴 시각은 전날이다 — 출처 시계의 작은 어긋남은 오늘로 둔다.
_SKEW: Final = dt.timedelta(hours=1)


def _state(raw: str) -> dict[str, object]:
    start = raw.find(_MARK)
    if start < 0:
        raise NewsParseEmpty("Yahoo!ファイナンス 화면에 상태 JSON이 없습니다.")
    equals = raw.find("=", start + len(_MARK))
    if equals < 0:
        raise NewsParseEmpty("Yahoo!ファイナンス 화면에 상태 JSON이 없습니다.")
    text = raw[equals + 1 :].lstrip()
    try:
        state, _ = json.JSONDecoder().raw_decode(text)
    except ValueError as exc:
        raise NewsInvalidBody("Yahoo!ファイナンス 상태 JSON을 읽지 못했습니다.") from exc
    if not isinstance(state, dict):
        raise NewsInvalidBody("Yahoo!ファイナンス 상태 JSON이 객체가 아닙니다.")
    return state


def _text(value: object) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _dict(value: object) -> dict[str, object]:
    return value if isinstance(value, dict) else {}


def _reference(state: dict[str, object], now: dt.datetime) -> dt.datetime:
    """기준 시각(일본 시간). 본문에 없으면 받은 시각이다."""
    raw = _dict(state.get("pageInfo")).get("currentDateTime")
    try:
        millis = int(str(raw))
    except ValueError:
        return now.astimezone(_JST)
    return dt.datetime.fromtimestamp(millis // 1000, _JST)


def _when(text: object, reference: dt.datetime) -> tuple[dt.datetime | None, dt.date | None]:
    if not isinstance(text, str):
        return None, None
    value = text.strip()
    if match := _TIME.fullmatch(value):
        hour, minute = int(match.group(1)), int(match.group(2))
        if hour > 23 or minute > 59:
            return None, None
        moment = reference.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if moment > reference + _SKEW:
            moment -= dt.timedelta(days=1)
        return moment.astimezone(dt.UTC), None
    if match := _DATE.fullmatch(value):
        month, day = int(match.group(1)), int(match.group(2))
        today = reference.date()
        year = today.year if (month, day) <= (today.month, today.day) else today.year - 1
        try:
            return None, dt.date(year, month, day)
        except ValueError:
            return None, None
    return None, None


def parse(raw: str, *, now: dt.datetime) -> list[NewsItem]:
    """화면 → 위 10개. 상태 키·목록이 없거나 읽은 기사가 0이면 `NewsParseEmpty`."""
    state = _state(raw)
    category = _dict(state.get("mainNewsCategory"))
    if _dict(category.get("title")).get("name") != LIST_NAME:
        raise NewsParseEmpty("Yahoo!ファイナンス 화면에 ヘッドライン 목록이 없습니다.")
    articles = _dict(category.get("news")).get("articles")
    if not isinstance(articles, list):
        raise NewsParseEmpty("Yahoo!ファイナンス 화면에 기사 목록이 없습니다.")
    reference = _reference(state, now)
    candidates: list[NewsItem] = []
    for article in articles:
        if not isinstance(article, dict):
            continue
        title, link = _text(article.get("headline")), article.get("link")
        if title is None or not isinstance(link, str):
            continue
        url = absolute_url(link, base=_BASE, host=HOST)
        if url is None:
            continue
        published_at, published_date = _when(article.get("createTime"), reference)
        candidates.append(
            NewsItem(
                rank=0,
                title=title,
                url=url,
                publisher=_text(article.get("mediaName")),
                published_at=published_at,
                published_date=published_date,
                published_text=None,
                paid=article.get("isPaidArticle") is True,
            )
        )
    items = pick_top(candidates)
    if not items:
        raise NewsParseEmpty("Yahoo!ファイナンス 화면에서 기사를 하나도 읽지 못했습니다.")
    return items


async def fetch(http: TextFetcher, url: str, *, now: dt.datetime) -> list[NewsItem]:
    return parse(await http.get_text(url, accept_language=ACCEPT_LANGUAGE), now=now)
