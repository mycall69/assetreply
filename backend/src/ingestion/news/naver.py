"""네이버 증권 주요뉴스 (014 T073) — FR-020~FR-022, research R14-13.

**공개되지 않은 내부 JSON API다** — 네이버 증권 뉴스 화면이 부르는 그 경로(HTML에는 목록이 없다).
헌법 원칙 II 이탈
(plan Complexity Tracking, 사용자 승인 2026-10-09).

- 목록은 "주요뉴스"(`MAINNEWS`) 첫 쪽이다. 같은 제목이 다른 기사 번호로 두 번 나온 실측이 있어
  15개를 받아 거른 뒤
  10개를 쓴다
- 칸: `title`(원문), 언론사 `officeHname`, 시각 `datetime`(오프셋 없는 한국 시간 — UTC로 바꾼다).
  응답에 링크가 없어
  기사 번호 둘(`officeId`·`articleId`)로 뉴스 화면 주소를 만든다 — 숫자가 아니면 그 줄을 버린다
"""

from __future__ import annotations

import datetime as dt
import json
import re
from typing import Final
from zoneinfo import ZoneInfo

from src.ingestion.news.errors import NewsInvalidBody, NewsParseEmpty
from src.ingestion.news.types import NewsItem, TextFetcher, pick_top

ACCEPT_LANGUAGE: Final = "ko-KR,ko;q=0.9"
PARAMS: Final = {"category": "MAINNEWS", "page": "1", "pageSize": "15"}
_KST: Final = ZoneInfo("Asia/Seoul")
_ARTICLE: Final = "https://n.news.naver.com/article/{office}/{article}"
_DIGITS: Final = re.compile(r"\d+")
_DATETIME: Final = "%Y-%m-%d %H:%M:%S"


def _text(value: object) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _published_at(value: object) -> dt.datetime | None:
    if not isinstance(value, str):
        return None
    try:
        local = dt.datetime.strptime(value.strip(), _DATETIME)
    except ValueError:
        return None
    return local.replace(tzinfo=_KST).astimezone(dt.UTC)


def parse(raw: str) -> list[NewsItem]:
    """본문 → 위 10개. `articles`가 없거나 읽은 기사가 0이면 `NewsParseEmpty`."""
    try:
        body = json.loads(raw)
    except ValueError as exc:
        raise NewsInvalidBody("네이버 증권 응답이 JSON이 아닙니다.") from exc
    articles = body.get("articles") if isinstance(body, dict) else None
    if not isinstance(articles, list):
        raise NewsParseEmpty("네이버 증권 응답에 기사 목록이 없습니다.")
    candidates: list[NewsItem] = []
    for article in articles:
        if not isinstance(article, dict):
            continue
        title = _text(article.get("title"))
        office, number = article.get("officeId"), article.get("articleId")
        if (
            title is None
            or not isinstance(office, str)
            or not isinstance(number, str)
            or not _DIGITS.fullmatch(office)
            or not _DIGITS.fullmatch(number)
        ):
            continue
        candidates.append(
            NewsItem(
                rank=0,
                title=title,
                url=_ARTICLE.format(office=office, article=number),
                publisher=_text(article.get("officeHname")),
                published_at=_published_at(article.get("datetime")),
                published_date=None,
                published_text=None,
                paid=False,
            )
        )
    items = pick_top(candidates)
    if not items:
        raise NewsParseEmpty("네이버 증권 응답에서 기사를 하나도 읽지 못했습니다.")
    return items


async def fetch(http: TextFetcher, url: str, *, now: dt.datetime) -> list[NewsItem]:
    """`now`는 쓰지 않는다 — 출처가 정확한 시각을 준다(칸마다 같은 꼴로 부르려고 받는다)."""
    del now
    return parse(await http.get_text(url, params=PARAMS, accept_language=ACCEPT_LANGUAGE))
