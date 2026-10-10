"""변화 까닭 고르기 (014 반복 2026-10-10b T104) — FR-027, SC-013, research R14-17.

순수 함수다. 마지막 세션 날짜(그 시장 현지 0시) 이후 게시된 기사만, 출처 차례로 위에서부터 최대 3개,
같은 제목은 한 번.
게시 시각을 모르는 기사는 고르지 않는다 — 지난 변화의 기사일 수 있다.
"""

from __future__ import annotations

import datetime as dt

from src.api.services.indicator_commentary import select_items, since_of
from src.ingestion.news.commentary import CommentaryItem

UTC = dt.UTC


def item(title: str, at: dt.datetime | None) -> CommentaryItem:
    return CommentaryItem(
        title=title,
        summary=None,
        publisher="한국경제",
        published_at=at,
        published_text=None,
        url="https://n.news.naver.com/a",
    )


SINCE = dt.datetime(2026, 10, 7, 15, 0, tzinfo=UTC)  # 한국 10-08 0시


def test_세션_이후만_위에서부터_셋() -> None:
    items = [
        item("A", SINCE + dt.timedelta(hours=10)),
        item("B — 지난 세션", SINCE - dt.timedelta(minutes=1)),
        item("C", SINCE),
        item("D", SINCE + dt.timedelta(hours=2)),
        item("E", SINCE + dt.timedelta(hours=3)),
    ]
    assert [i.title for i in select_items(items, since=SINCE)] == ["A", "C", "D"]


def test_같은_제목은_한_번이고_시각_모르는_기사는_뺀다() -> None:
    items = [
        item("코스피  하락", SINCE + dt.timedelta(hours=1)),
        item("코스피 하락", SINCE + dt.timedelta(hours=2)),
        item("F", None),
    ]
    assert [i.title for i in select_items(items, since=SINCE)] == ["코스피  하락"]


def test_기준은_그_시장_현지_0시다() -> None:
    assert since_of(dt.date(2026, 10, 8), "krx") == dt.datetime(2026, 10, 7, 15, 0, tzinfo=UTC)
    # 뉴욕 10-08 0시 = 04:00 UTC(서머타임)
    assert since_of(dt.date(2026, 10, 8), "us_equity") == dt.datetime(2026, 10, 8, 4, 0, tzinfo=UTC)
