"""기간 표 — 대표일·표시·사건 행·결측 구간 행·쪽 (012 T012) — FR-004, FR-004a, FR-004b, FR-005,
FR-009, SC-002, SC-003,
research R12-2·R12-3·R12-5~R12-7, data-model 3, quickstart 1.

손으로 만든 날짜 목록으로 고정한다(2026-10 달력 — 10-05 월요일 대체공휴일, 10-09 금요일 한글날,
10-31 토요일).

- 주는 월~일, 대표일은 **그 주 ∩ 계산 기간에서 금요일 이하의 마지막 시세일**이다. 없으면 그 주의
  마지막 시세일(토·일 — 가상자산)이다(명확화 2)
- 월은 그 달 ∩ 계산 기간의 마지막 시세일이다
- 대표일이 기준일(금요일·말일)과 다르면 `shifted_from` = 기준일이다. 같으면 없다 — 늘 붙으면 구별의
  뜻이 사라진다(004 FR-014)
- 구간의 끝이 계산 끝 뒤면 진행 중이다(FR-004a). 일 단위는 늘 아니다
- 사건이 있는 날은 단위와 관계없이 사건 묶음 하나다. 대표일에 사건이 있으면 기간 행이 없고 표시는
  사건 묶음이 진다(FR-005)
- 결측 구간은 일 단위에만 들어간다(FR-004b). 값을 만들지 않는다 — 날짜만 고른다(원칙 V)
"""

from __future__ import annotations

import datetime as dt

import pytest

from src.simulation.period_table import (
    PERIOD_UNITS,
    TableEntry,
    anchor_of,
    build_table,
    is_ongoing,
    page,
    period_bounds,
)

D = dt.date.fromisoformat


def days(
    start: str, end: str, *, skip: tuple[str, ...] = (), weekends: bool = False
) -> list[dt.date]:
    """`start`~`end`의 날(기본은 평일만). `skip`은 휴장·결측이다."""
    out: list[dt.date] = []
    day, last, skipped = D(start), D(end), {D(s) for s in skip}
    while day <= last:
        if (weekends or day.weekday() < 5) and day not in skipped:
            out.append(day)
        day += dt.timedelta(days=1)
    return out


def view(entries: list[TableEntry]) -> list[tuple[str, str, str | None, bool]]:
    return [
        (
            e.kind,
            e.date.isoformat(),
            e.shifted_from.isoformat() if e.shifted_from else None,
            e.is_ongoing,
        )
        for e in entries
    ]


class Test달력:
    def test_단위는_일_주_월이다(self) -> None:
        assert PERIOD_UNITS == ("daily", "weekly", "monthly")

    @pytest.mark.parametrize(
        ("day", "unit", "bounds"),
        [
            ("2026-10-07", "weekly", ("2026-10-05", "2026-10-11")),
            ("2026-10-11", "weekly", ("2026-10-05", "2026-10-11")),
            ("2026-10-12", "weekly", ("2026-10-12", "2026-10-18")),
            ("2026-10-07", "monthly", ("2026-10-01", "2026-10-31")),
            ("2026-02-10", "monthly", ("2026-02-01", "2026-02-28")),
            ("2026-10-07", "daily", ("2026-10-07", "2026-10-07")),
        ],
    )
    def test_구간(self, day: str, unit: str, bounds: tuple[str, str]) -> None:
        assert period_bounds(D(day), unit) == (D(bounds[0]), D(bounds[1]))  # type: ignore[arg-type]

    @pytest.mark.parametrize(
        ("day", "unit", "anchor"),
        [
            ("2026-10-05", "weekly", "2026-10-09"),
            ("2026-10-11", "weekly", "2026-10-09"),
            ("2026-10-07", "monthly", "2026-10-31"),
            ("2026-10-07", "daily", "2026-10-07"),
        ],
    )
    def test_기준일(self, day: str, unit: str, anchor: str) -> None:
        assert anchor_of(D(day), unit) == D(anchor)  # type: ignore[arg-type]

    def test_진행_중은_구간_끝이_계산_끝_뒤일_때뿐이다(self) -> None:
        assert is_ongoing(D("2026-10-11"), D("2026-10-05"), "weekly")
        assert not is_ongoing(
            D("2026-10-11"), D("2026-10-11"), "weekly"
        )  # 계산 끝이 일요일이면 그 주는 끝났다
        assert not is_ongoing(D("2026-10-04"), D("2026-10-05"), "weekly")
        assert is_ongoing(D("2026-10-31"), D("2026-10-05"), "monthly")
        assert not is_ongoing(D("2026-10-07"), D("2026-10-05"), "daily")  # 일 단위는 늘 아니다


class Test주_대표일:
    def test_금요일_휴장_주는_목요일이고_금요일에서_옮겨졌다(self) -> None:
        quotes = days("2026-10-05", "2026-10-16", skip=("2026-10-05", "2026-10-09"))
        table = build_table(quotes, set(), "weekly", D("2026-10-18"))
        assert view(table) == [
            ("period", "2026-10-16", None, False),
            ("period", "2026-10-08", "2026-10-09", False),
        ]

    def test_계산_끝이_대체공휴일_월요일이면_그_주의_행이_없고_맨_위는_앞_주_금요일이다(
        self,
    ) -> None:
        quotes = days("2026-09-28", "2026-10-02")
        table = build_table(quotes, set(), "weekly", D("2026-10-05"))
        assert view(table) == [("period", "2026-10-02", None, False)]

    def test_계산_끝_월요일에_시세가_있으면_그날이_대표일이고_옮겨졌고_진행_중이다(self) -> None:
        quotes = days("2026-09-28", "2026-10-05")
        table = build_table(quotes, set(), "weekly", D("2026-10-05"))
        assert view(table) == [
            ("period", "2026-10-05", "2026-10-09", True),
            ("period", "2026-10-02", None, False),
        ]

    def test_가상자산_금요일_결측이면_토일이_있어도_목요일이다(self) -> None:
        quotes = days("2021-03-01", "2021-03-07", skip=("2021-03-05",), weekends=True)
        table = build_table(quotes, set(), "weekly", D("2021-03-07"))
        assert view(table) == [("period", "2021-03-04", "2021-03-05", False)]

    def test_가상자산_월부터_금까지_결측이면_그_주의_마지막_일봉이다(self) -> None:
        quotes = days(
            "2021-03-08",
            "2021-03-14",
            skip=tuple(f"2021-03-{d:02d}" for d in range(8, 13)),
            weekends=True,
        )
        table = build_table(quotes, set(), "weekly", D("2021-03-14"))
        assert view(table) == [("period", "2021-03-14", "2021-03-12", False)]

    def test_가상자산_금요일이_있으면_토일이_있어도_금요일이다(self) -> None:
        quotes = days("2021-03-15", "2021-03-21", weekends=True)
        table = build_table(quotes, set(), "weekly", D("2021-03-21"))
        assert view(table) == [("period", "2021-03-19", None, False)]

    def test_첫_주_금요일이_첫_평가일_전이면_그_주의_계산_기간_안_마지막_일봉이고_표시가_있다(
        self,
    ) -> None:
        # 토요일에 샀다 — 그 주 ∩ 계산 기간에 금요일 이하의 일봉이 없다. 금요일(첫 평가일 전)로 행을
        # 만들지 않는다
        quotes = days("2021-03-06", "2021-03-12", weekends=True)
        table = build_table(quotes, {D("2021-03-06")}, "weekly", D("2021-03-12"))
        assert view(table) == [
            ("period", "2021-03-12", None, True),
            ("period", "2021-03-07", "2021-03-05", False),
            ("events", "2021-03-06", None, False),
        ]
        assert all(e.date >= D("2021-03-06") for e in table)

    def test_구간에_시세일이_없으면_그_구간의_행이_없다(self) -> None:
        quotes = days("2026-09-14", "2026-09-18") + days("2026-09-28", "2026-10-02")
        table = build_table(quotes, set(), "weekly", D("2026-10-04"))
        assert [e.date.isoformat() for e in table] == ["2026-10-02", "2026-09-18"]


class Test월_대표일:
    def test_말일이_토요일이면_금요일이고_말일에서_옮겨졌다(self) -> None:
        quotes = days("2026-10-26", "2026-10-30")
        table = build_table(quotes, set(), "monthly", D("2026-11-02"))
        assert view(table) == [("period", "2026-10-30", "2026-10-31", False)]

    def test_말일에_시세가_있으면_표시가_없다(self) -> None:
        quotes = days("2026-09-28", "2026-09-30")
        table = build_table(quotes, set(), "monthly", D("2026-10-02"))
        assert view(table) == [("period", "2026-09-30", None, False)]

    def test_이번_달은_계산_끝까지의_마지막_시세일이고_진행_중이다(self) -> None:
        quotes = days("2026-09-28", "2026-10-02")
        table = build_table(quotes, set(), "monthly", D("2026-10-05"))
        assert view(table) == [
            ("period", "2026-10-02", "2026-10-31", True),
            ("period", "2026-09-30", None, False),
        ]

    def test_시세가_끊긴_종목의_마지막_구간은_계산_끝_앞에서_끝났으면_진행_중이_아니다(
        self,
    ) -> None:
        quotes = days("2026-07-01", "2026-07-15")  # 7-15에 끊겼다 — 계산 끝은 10-05
        table = build_table(quotes, set(), "monthly", D("2026-10-05"))
        assert view(table) == [("period", "2026-07-15", "2026-07-31", False)]


class Test사건:
    def test_대표일에_사건이_있으면_기간_행이_없고_사건_묶음이_표시를_진다(self) -> None:
        quotes = days("2026-09-21", "2026-10-02", skip=("2026-09-30",))
        table = build_table(quotes, {D("2026-09-25"), D("2026-09-29")}, "monthly", D("2026-10-05"))
        assert view(table) == [
            ("period", "2026-10-02", "2026-10-31", True),
            (
                "events",
                "2026-09-29",
                "2026-09-30",
                False,
            ),  # 9월 대표일(말일 휴장) — 재투자일이라 사건 묶음이 진다
            (
                "events",
                "2026-09-25",
                None,
                False,
            ),  # 배당락일 — 대표일이 아니어도 늘 있다. 날짜는 그대로다
        ]

    def test_사건은_모든_단위에_한_번씩이다(self) -> None:
        quotes = days("2026-09-01", "2026-10-12", skip=("2026-10-05", "2026-10-09", "2026-09-30"))
        events = {D("2026-09-01"), D("2026-09-25"), D("2026-09-29"), D("2026-10-07")}
        for unit in PERIOD_UNITS:
            table = build_table(quotes, events, unit, D("2026-10-12"))
            assert sorted(e.date for e in table if e.kind == "events") == sorted(events), unit

    def test_기간마다_대표_행은_하나다(self) -> None:
        # 대조용 계산 — 금요일 이하의 마지막 시세일, 없으면 그 구간의 마지막(월은 마지막). 구현과
        # 따로 센다
        quotes = days(
            "2026-09-01",
            "2026-10-12",
            weekends=True,
            skip=("2026-10-05", "2026-10-09", "2026-10-02"),
        )
        events = {D("2026-09-01"), D("2026-09-25"), D("2026-10-08")}
        for unit in ("weekly", "monthly"):
            groups: dict[tuple[dt.date, dt.date], list[dt.date]] = {}
            for q in quotes:
                groups.setdefault(period_bounds(q, unit), []).append(q)
            expected = set()
            for group in groups.values():
                anchor = anchor_of(group[0], unit)
                upto = [q for q in group if q <= anchor] if unit == "weekly" else group
                expected.add(max(upto or group))
            table = build_table(quotes, events, unit, D("2026-10-12"))
            periods = {e.date for e in table if e.kind == "period"}
            assert periods == expected - events, unit
            assert periods | (expected & events) == expected, unit

    def test_옮겨짐_표시는_대표일이_기준일과_다를_때뿐이다(self) -> None:
        quotes = days("2026-09-01", "2026-10-12", skip=("2026-10-05", "2026-10-09", "2026-09-30"))
        for unit in ("weekly", "monthly"):
            for e in build_table(quotes, {D("2026-09-25")}, unit, D("2026-10-12")):
                if e.shifted_from is not None:
                    assert e.shifted_from == anchor_of(e.date, unit) and e.shifted_from != e.date
                elif e.kind == "period":
                    assert e.date == anchor_of(e.date, unit)


class Test일_단위:
    def test_사건_없는_시세일마다_기간_행이고_표시가_없다(self) -> None:
        quotes = days("2026-10-01", "2026-10-07", skip=("2026-10-05",))
        table = build_table(quotes, {D("2026-10-02")}, "daily", D("2026-10-07"))
        assert view(table) == [
            ("period", "2026-10-07", None, False),
            ("period", "2026-10-06", None, False),
            ("events", "2026-10-02", None, False),
            ("period", "2026-10-01", None, False),
        ]

    def test_결측_구간마다_행_하나이고_자리가_맞다(self) -> None:
        quotes = days(
            "2021-03-01",
            "2021-03-14",
            weekends=True,
            skip=("2021-03-05", "2021-03-08", "2021-03-09", "2021-03-10"),
        )
        missing = [(D("2021-03-05"), D("2021-03-05")), (D("2021-03-08"), D("2021-03-10"))]
        table = build_table(quotes, set(), "daily", D("2021-03-14"), missing)
        gaps = [
            (e.date.isoformat(), e.date_to.isoformat() if e.date_to else None)
            for e in table
            if e.kind == "missing"
        ]
        assert gaps == [("2021-03-08", "2021-03-10"), ("2021-03-05", "2021-03-05")]
        order = [e.date.isoformat() for e in table]
        assert order.index("2021-03-11") < order.index("2021-03-08") < order.index("2021-03-07")
        assert order.index("2021-03-06") < order.index("2021-03-05") < order.index("2021-03-04")
        assert all(
            e.shifted_from is None and not e.is_ongoing for e in table if e.kind == "missing"
        )

    def test_주_월에는_결측_구간_행이_없다(self) -> None:
        quotes = days("2021-03-01", "2021-03-14", weekends=True, skip=("2021-03-05",))
        missing = [(D("2021-03-05"), D("2021-03-05"))]
        for unit in ("weekly", "monthly"):
            assert [
                e
                for e in build_table(quotes, set(), unit, D("2021-03-14"), missing)
                if e.kind == "missing"
            ] == []


class Test쪽:
    TABLE = build_table(
        days("2021-03-01", "2021-03-10", weekends=True, skip=("2021-03-05",)),
        {D("2021-03-03")},
        "daily",
        D("2021-03-10"),
        [(D("2021-03-05"), D("2021-03-05"))],
    )

    def test_before_미만만_최신순으로_limit개다(self) -> None:
        chunk, more = page(self.TABLE, D("2021-03-08"), 2)
        assert [e.date.isoformat() for e in chunk] == ["2021-03-07", "2021-03-06"]
        assert more

    def test_결측_구간_행의_커서는_구간의_처음이다(self) -> None:
        chunk, _ = page(self.TABLE, D("2021-03-06"), 1)
        assert chunk[0].kind == "missing" and chunk[0].date == D("2021-03-05")
        rest, more = page(self.TABLE, chunk[0].date, 10)
        assert [e.date.isoformat() for e in rest] == [
            "2021-03-04",
            "2021-03-03",
            "2021-03-02",
            "2021-03-01",
        ]
        assert not more

    def test_끝까지_이어_받으면_한_번에_받은_것과_같다(self) -> None:
        seen: list[TableEntry] = []
        before: dt.date | None = None
        while True:
            chunk, more = page(self.TABLE, before, 3)
            seen += chunk
            if not more:
                break
            before = chunk[-1].date
        assert seen == self.TABLE

    def test_같은_날의_사건_묶음은_항목_하나라_쪽에서_갈리지_않는다(self) -> None:
        assert sum(1 for e in self.TABLE if e.date == D("2021-03-03")) == 1
