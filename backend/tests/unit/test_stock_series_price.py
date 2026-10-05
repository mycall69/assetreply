"""주식 시계열의 가격 (010 T004) — FR-001, FR-007, FR-008, research R10-1·R10-3·R10-4.

**계산하지 않는다** — 점의 `price`는 그 날 **마지막 행**의 원주가 시가(`Row.open_price`)다.
시뮬레이터는 같은 날의 배당락 행을 먼저, 달 첫 행을 뒤에 덧붙이므로 나중 행이 그 날의 최종
상태다(005와 같은 규칙 — 잔고와 같은 행에서 꺼내야 한 점의 값이 같은 날·같은 행의 것이다).

분할 기록은 결과의 `splits`에서 **구간 안의 것만 효력일 순으로** 시계열에 싣는다. 표식 자리(효력일
뒤 첫 점)는 화면이 그린 점에서 정한다 — 다운샘플이 그 점을 뺄 수 있다.
"""
from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest

from src.api.services.stock_series import build_series
from src.api.services.stock_simulation import ConvertedRow, SimulationResult
from src.simulation.reinvest import Row, SplitOn

D = dt.date.fromisoformat


def row(day: str, open_price: str, balance: str = "100", kind: str = "month_first") -> ConvertedRow:
    return ConvertedRow(Row(
        date=D(day), kind=kind, open_price=Decimal(open_price),
        bought_shares=0, held_shares=1, cash=Decimal("0"),
        principal=Decimal("100"), balance=Decimal(balance),
        profit=Decimal("0"), return_rate=Decimal("0.1")))


def result(rows: list[ConvertedRow], splits: tuple[SplitOn, ...] | None = None) -> SimulationResult:
    extra = {} if splits is None else {"splits": splits}
    return SimulationResult(
        rows=rows, latest=rows[-1], as_of=rows[-1].row.date, is_final=True,
        quote_dates=frozenset(r.row.date for r in rows), **extra)  # type: ignore[arg-type]


def build(res: SimulationResult, start: str = "2021-01-01", end: str = "2021-12-31",
          max_points: int = 1000):  # type: ignore[no-untyped-def]
    return build_series(res, start=D(start), end=D(end), covered=(D(start), D(end)),
                        max_points=max_points)


def test_점의_가격은_그_날_마지막_행의_시가다() -> None:
    """같은 날 배당락 행(먼저)과 달 첫 행(나중)이 있으면 나중 행이다 — 잔고도 그 행이다."""
    series = build(result([
        row("2021-08-02", "140.25"),
        row("2021-09-01", "152.10", balance="100", kind="dividend"),
        row("2021-09-01", "152.83", balance="200"),
        row("2021-10-01", "141.90"),
    ]))
    assert [(p.date, p.price, p.balance) for p in series.points] == [
        (D("2021-08-02"), Decimal("140.25"), Decimal("100")),
        (D("2021-09-01"), Decimal("152.83"), Decimal("200")),
        (D("2021-10-01"), Decimal("141.90"), Decimal("100")),
    ]


def test_가격은_비지_않는다() -> None:
    """주식의 점은 표의 행이라 그 날의 시가가 늘 있다 — 비면 조립이 틀린 것이다."""
    series = build(result([row(f"2021-{m:02d}-01", str(100 + m)) for m in range(1, 13)]))
    assert all(isinstance(p.price, Decimal) for p in series.points)


def test_줄인_점의_가격은_그_날짜의_원래_값이다() -> None:
    """FR-007 — 잔고 축으로 날짜를 고르고 점을 통째로 가져온다. 값마다 따로 줄이면 한 점에 다른 날의
    가격이 섞인다."""
    days = [D("2021-01-01") + dt.timedelta(days=i) for i in range(60)]
    rows = [row(d.isoformat(), f"{100 + (i * 7) % 13}.{i:02d}", balance=str(1000 + (i * 37) % 101))
            for i, d in enumerate(days)]
    full = {p.date: p for p in build(result(rows), end="2021-03-01").points}
    reduced = build(result(rows), end="2021-03-01", max_points=10)
    assert reduced.downsampled is True and len(reduced.points) == 10
    for point in reduced.points:
        assert (point.price, point.balance) == (full[point.date].price, full[point.date].balance)


def test_분할은_구간_안의_것만_효력일_순으로_싣는다() -> None:
    splits = (
        SplitOn(D("2021-08-31"), 4, 1),
        SplitOn(D("2020-06-01"), 2, 1),   # 구간 앞
        SplitOn(D("2021-03-10"), 3, 2),
        SplitOn(D("2022-02-01"), 5, 1),   # 구간 뒤
    )
    series = build(result([row("2021-01-04", "100"), row("2021-12-01", "30")], splits))
    assert [(s.date, s.numerator, s.denominator) for s in series.splits] == [
        (D("2021-03-10"), 3, 2), (D("2021-08-31"), 4, 1)]


def test_분할을_넘기지_않은_결과도_만들어진다() -> None:
    """`test_stock_series_build.py`처럼 결과를 직접 만드는 곳이 있다 — 새 필드는 기본값(빈
    묶음)이다."""
    res = result([row("2021-01-04", "100")])
    assert res.splits == ()
    assert build(res).splits == ()


@pytest.mark.parametrize("kind", ["month_first", "dividend", "reinvest"])
def test_행_종류와_관계없이_그_행의_시가다(kind: str) -> None:
    series = build(result([row("2021-05-03", "123.45", kind=kind)]))
    assert series.points[0].price == Decimal("123.45")
