"""투자 성과표 등락의 비교 날짜 — 직전 기간의 대표일 (014 반복 2026-10-13b T221) — spec FR-048,
data-model 19.2, research R14-38.

날짜가 속한 기간(일·주·월 — 012 `period_bounds`)의 바로 앞, **시세일이 있는 가장 가까운 기간의
대표일**(012 대표일 규칙)이다. 사건 날(대표일이 아닌 날)도 같은 규칙이라 적립식 월 표의 납입 행과 달
끝 행이 같은 직전 달 끝과 견준다 — "바로 아래 행"이면 며칠 차이만 견주게 된다(FR-048 실패 양상).
계산 기간의 첫 기간은 비교 대상이 없다. 결측 날(시세일이 아닌 날)은 건너뛴다(원칙 V — 메우지
않는다).
"""

from __future__ import annotations

import datetime as dt

import pytest

from src.simulation.period_table import PeriodUnit, build_table, previous_representative

D = dt.date.fromisoformat


def span(first: str, last: str, *, skip: set[str] | frozenset[str] = frozenset(),
         weekdays_only: bool = False) -> list[dt.date]:
    out, day = [], D(first)
    while day <= D(last):
        if day.isoformat() not in skip and not (weekdays_only and day.weekday() >= 5):
            out.append(day)
        day += dt.timedelta(days=1)
    return out


class Test일:
    def test_직전_시세일이고_결측_날은_건너뛴다(self) -> None:
        skip = {"2021-03-05", *(f"2021-03-{d}" for d in range(10, 13))}
        days = span("2021-03-01", "2021-03-21", skip=skip)
        previous = previous_representative(days, "daily")
        assert previous(D("2021-03-02")) == D("2021-03-01")
        assert previous(D("2021-03-06")) == D("2021-03-04")
        assert previous(D("2021-03-13")) == D("2021-03-09")
        assert previous(D("2021-03-01")) is None

    def test_휴장_뒤는_직전_거래일이다(self) -> None:
        days = span("2026-09-28", "2026-10-08", skip={"2026-09-30", "2026-10-05"},
                    weekdays_only=True)
        previous = previous_representative(days, "daily")
        assert previous(D("2026-10-01")) == D("2026-09-29")
        assert previous(D("2026-10-06")) == D("2026-10-02")


class Test주:
    def test_직전_주의_금요일_이하_마지막_시세일이다(self) -> None:
        days = span("2026-09-07", "2026-09-25", skip={"2026-09-18"}, weekdays_only=True)
        previous = previous_representative(days, "weekly")
        assert previous(D("2026-09-15")) == D("2026-09-11")   # 둘째 주의 사건 날
        assert previous(D("2026-09-17")) == D("2026-09-11")   # 둘째 주의 대표일(금요일 휴장 → 목)
        assert previous(D("2026-09-21")) == D("2026-09-17")
        assert previous(D("2026-09-11")) is None

    def test_주말만_있는_주는_그_주의_마지막_시세일이다(self) -> None:
        # 가상자산: 둘째 주는 월~금이 모두 결측이고 토·일만 있다
        days = [*span("2021-03-01", "2021-03-07"), D("2021-03-13"), D("2021-03-14"),
                *span("2021-03-15", "2021-03-21")]
        previous = previous_representative(days, "weekly")
        assert previous(D("2021-03-13")) == D("2021-03-05")
        assert previous(D("2021-03-14")) == D("2021-03-05")
        assert previous(D("2021-03-16")) == D("2021-03-14")
        assert previous(D("2021-03-07")) is None   # 첫 주의 일요일(대표일 금요일 뒤의 사건 날)


class Test월:
    def test_직전_달의_마지막_시세일이다(self) -> None:
        days = span("2026-08-03", "2026-10-16", skip={"2026-09-30", "2026-10-05", "2026-10-09"},
                    weekdays_only=True)
        previous = previous_representative(days, "monthly")
        assert previous(D("2026-09-16")) == D("2026-08-31")   # 사건 날(배당락)
        assert previous(D("2026-09-29")) == D("2026-08-31")   # 9월 대표일(말일 휴장)
        assert previous(D("2026-10-16")) == D("2026-09-29")   # 진행 중인 달
        assert previous(D("2026-08-03")) is None              # 첫 달(첫 매수)
        assert previous(D("2026-08-31")) is None

    def test_시세일이_없는_달은_건너뛴다(self) -> None:
        days = [D("2026-01-30"), D("2026-03-02"), D("2026-03-31")]
        previous = previous_representative(days, "monthly")
        assert previous(D("2026-03-31")) == D("2026-01-30")


@pytest.mark.parametrize("unit", ["daily", "weekly", "monthly"])
def test_비교_날짜는_늘_표에_보이는_행의_날짜다(unit: PeriodUnit) -> None:
    days = span("2026-08-03", "2026-10-16", skip={"2026-09-30", "2026-10-05", "2026-10-09"},
                weekdays_only=True)
    events = {D("2026-08-03"), D("2026-09-16"), D("2026-09-18"), D("2026-10-12")}
    entries = build_table(days, events, unit, D("2026-10-16"))
    shown = {e.date for e in entries}
    previous = previous_representative(days, unit)
    compared = [previous(e.date) for e in entries]
    assert all(c is None or c in shown for c in compared)
    assert all(c is None or c < e.date for c, e in zip(compared, entries, strict=True))
    assert compared[-1] is None   # 맨 아래(첫 매수)
