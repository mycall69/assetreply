"""청크 분할 테스트 (T036).

FR-005: 전체 수집 구간을 날짜 기준 청크로 분할해 순차 요청한다.
research R2: 기본 365일. 전 구간을 한 번에 요청하지 않는다.
"""
from __future__ import annotations

import datetime as dt

import pytest

from src.ingestion.collector import split_into_chunks


def test_구간이_청크보다_짧으면_한_덩어리다() -> None:
    chunks = split_into_chunks(dt.date(2026, 8, 1), dt.date(2026, 8, 20), chunk_days=365)
    assert chunks == [(dt.date(2026, 8, 1), dt.date(2026, 8, 20))]


def test_365일_단위로_나눈다() -> None:
    """2020-01-01~2022-12-31은 1096일(2020 윤년) — 365일 청크로 4개가 된다."""
    chunks = split_into_chunks(dt.date(2020, 1, 1), dt.date(2022, 12, 31), chunk_days=365)
    assert len(chunks) == 4
    assert all((b - a).days + 1 <= 365 for a, b in chunks)
    assert chunks[0][0] == dt.date(2020, 1, 1)
    assert chunks[-1][1] == dt.date(2022, 12, 31)


def test_청크가_겹치지_않고_빈틈도_없다() -> None:
    chunks = split_into_chunks(dt.date(1995, 1, 1), dt.date(2026, 8, 29), chunk_days=365)
    for prev, nxt in zip(chunks, chunks[1:], strict=False):
        assert nxt[0] == prev[1] + dt.timedelta(days=1)
    assert chunks[0][0] == dt.date(1995, 1, 1)
    assert chunks[-1][1] == dt.date(2026, 8, 29)


def test_30년_전구간은_약_32청크다() -> None:
    """research R2: 통화당 약 32회 호출로 전 구간을 받는다."""
    chunks = split_into_chunks(dt.date(1995, 1, 1), dt.date(2026, 8, 29), chunk_days=365)
    assert 30 <= len(chunks) <= 34


def test_시작일과_종료일이_같으면_한_덩어리다() -> None:
    d = dt.date(2005, 3, 15)
    assert split_into_chunks(d, d, chunk_days=365) == [(d, d)]


def test_종료일이_시작일보다_빠르면_빈_목록이다() -> None:
    assert split_into_chunks(dt.date(2026, 1, 2), dt.date(2026, 1, 1), chunk_days=365) == []


def test_청크_크기가_0_이하면_거부한다() -> None:
    with pytest.raises(ValueError):
        split_into_chunks(dt.date(2020, 1, 1), dt.date(2020, 12, 31), chunk_days=0)


def test_작은_청크_크기도_동작한다() -> None:
    chunks = split_into_chunks(dt.date(2026, 1, 1), dt.date(2026, 1, 10), chunk_days=3)
    assert chunks == [
        (dt.date(2026, 1, 1), dt.date(2026, 1, 3)),
        (dt.date(2026, 1, 4), dt.date(2026, 1, 6)),
        (dt.date(2026, 1, 7), dt.date(2026, 1, 9)),
        (dt.date(2026, 1, 10), dt.date(2026, 1, 10)),
    ]
