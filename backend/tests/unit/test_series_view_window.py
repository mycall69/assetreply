"""보기 구간 질의의 검증·자르기 (014 반복 2026-10-11c T192) — spec FR-038, contracts/rest-api.md
A13.

`view_window`는 둘 다 없으면 `None`(지금 응답 그대로)이고, 하나만이거나 차례가 거꾸로면
`InvalidQuery`(400)다. 있으면 계산 구간으로 자른다 — 계산 구간 밖이면 시작이 끝보다 늦은 빈
구간이다(점이 없다).
"""

from __future__ import annotations

import datetime as dt

import pytest

from src.api.errors import InvalidQuery
from src.api.services.series_query import ViewWindow, view_window

D = dt.date.fromisoformat
START, END = D("2021-08-01"), D("2021-10-31")


def test_둘_다_없으면_None이다() -> None:
    assert view_window(None, None, start=START, end=END) is None


@pytest.mark.parametrize("pair", [(D("2021-09-01"), None), (None, D("2021-09-01"))],
                         ids=["시작만", "끝만"])
def test_하나만이면_거절한다(pair: tuple[dt.date | None, dt.date | None]) -> None:
    with pytest.raises(InvalidQuery):
        view_window(*pair, start=START, end=END)


def test_차례가_거꾸로면_거절한다() -> None:
    with pytest.raises(InvalidQuery):
        view_window(D("2021-09-30"), D("2021-09-01"), start=START, end=END)


def test_계산_구간으로_자른다() -> None:
    wide = view_window(D("2021-07-01"), D("2021-12-31"), start=START, end=END)
    assert wide == ViewWindow(START, END)
    assert view_window(D("2021-09-01"), D("2021-09-30"), start=START, end=END) == ViewWindow(
        D("2021-09-01"), D("2021-09-30"))


def test_계산_구간_밖이면_빈_구간이다() -> None:
    window = view_window(D("2019-01-01"), D("2019-12-31"), start=START, end=END)
    assert window is not None and window.start > window.end
    assert window.empty
