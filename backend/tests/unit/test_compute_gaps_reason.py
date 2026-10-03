"""커버리지 안 빈 날의 사유 (T006) — 007 FR-023, research R7-9.

외환·주식은 커버리지 안인데 값이 없으면 **휴장**(`no_quote` — 이어 그린다)이다. 가상자산은 휴장이
없어 그날은 **출처 결측** (`source_missing` — 끊는다)이다. 같은 계산을 쓰되 사유만 매개변수로
받는다. 기본값은 그대로라 외환·주식이 바뀌지 않는다.
"""
from __future__ import annotations

import datetime as dt

from src.api.services.series_query import compute_gaps

D = dt.date.fromisoformat
PRESENT = {D("2021-03-01"), D("2021-03-03")}


def test_기본은_휴장이다() -> None:
    gaps = compute_gaps(D("2021-03-01"), D("2021-03-03"), PRESENT, D("2021-03-01"), D("2021-03-03"))
    assert [(g.start, g.end, g.reason) for g in gaps] == [
        (D("2021-03-02"), D("2021-03-02"), "no_quote")]


def test_가상자산은_출처_결측이다() -> None:
    gaps = compute_gaps(D("2021-03-01"), D("2021-03-03"), PRESENT, D("2021-03-01"), D("2021-03-03"),
                        inside_reason="source_missing")
    assert [(g.start, g.end, g.reason) for g in gaps] == [
        (D("2021-03-02"), D("2021-03-02"), "source_missing")]


def test_커버리지_밖은_사유와_관계없이_미수집이다() -> None:
    gaps = compute_gaps(D("2021-03-01"), D("2021-03-05"), PRESENT, D("2021-03-01"), D("2021-03-03"),
                        inside_reason="source_missing")
    assert {(g.reason, g.start) for g in gaps} == {
        ("source_missing", D("2021-03-02")), ("not_collected", D("2021-03-04"))}
