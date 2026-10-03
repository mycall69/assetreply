"""차트 시계열 조립 (T083 보조) — 005 FR-033, FR-034, SC-032.

라우트는 미수집 구간을 202로 막으므로(FR-049), **`not_collected`는 이 함수 밖으로
나가지 않는다.** 그래도 여기서 분류하는 이유는 두 가지다.

- 분류 규칙이 FX와 **한 곳**(`compute_gaps`)에 있어야 한다. 자산군마다 다시 쓰면
  같은 화면 규칙이 자산군마다 다른 뜻이 된다.
- 게이트가 느슨해지는 날, 선이 **끊겨서** 드러나야 한다. 그때 이어 그리면 구멍 위에
  온전한 선이 생기고 사용자는 데이터를 다 가졌다고 믿는다 (헌법 원칙 V).
"""
from __future__ import annotations

import datetime as dt
from decimal import Decimal

from src.api.services.stock_series import build_series
from src.api.services.stock_simulation import ConvertedRow, SimulationResult
from src.simulation.reinvest import Row

D = dt.date.fromisoformat


def row(day: str, balance: str, rate: str) -> ConvertedRow:
    return ConvertedRow(Row(
        date=D(day), kind="month_first", open_price=Decimal("100"),
        bought_shares=0, held_shares=1, cash=Decimal("0"),
        principal=Decimal("100"), balance=Decimal(balance),
        profit=Decimal("0"), return_rate=Decimal(rate)))


def result(days: list[str]) -> SimulationResult:
    return SimulationResult(
        rows=[row(d, "100", "0.1") for d in days],
        latest=row(days[-1], "100", "0.1"),
        as_of=D(days[-1]), is_final=True,
        quote_dates=frozenset(D(d) for d in days))


def test_커버리지_밖은_미수집이다() -> None:
    series = build_series(
        result(["2021-08-02", "2021-08-03"]),
        start=D("2021-08-01"), end=D("2021-08-31"),
        covered=(D("2021-08-01"), D("2021-08-10")))
    not_collected = [g for g in series.gaps if g.reason == "not_collected"]
    assert any(g.start == D("2021-08-11") and g.end == D("2021-08-31")
               for g in not_collected), series.gaps


def test_커버리지_안의_빈_날은_휴장일이다() -> None:
    """이어 그린다 — 그날은 시장이 열리지 않아 값이 **존재하지 않는다**."""
    series = build_series(
        result(["2021-08-02", "2021-08-03"]),
        start=D("2021-08-01"), end=D("2021-08-10"),
        covered=(D("2021-08-01"), D("2021-08-10")))
    assert {g.reason for g in series.gaps} == {"no_quote"}


def test_커버리지가_없으면_전부_미수집이다() -> None:
    series = build_series(
        result(["2021-08-02"]),
        start=D("2021-08-01"), end=D("2021-08-03"), covered=None)
    assert {g.reason for g in series.gaps} == {"not_collected"}


def test_같은_날짜의_행이_하나로_합쳐진다() -> None:
    """배당락일이 그 달 첫 거래일이면 행이 둘 생긴다.

    점을 둘 넣으면 한 x좌표에 값이 둘이라 선이 되돌아 그려진다 — **표는 멀쩡한데
    차트만 깨진다.** 그 날의 마지막 상태가 남아야 한다.
    """
    both = SimulationResult(
        rows=[row("2021-09-01", "100", "0.1"), row("2021-09-01", "200", "0.2")],
        latest=row("2021-09-01", "200", "0.2"),
        as_of=D("2021-09-01"), is_final=True,
        quote_dates=frozenset({D("2021-09-01")}))
    series = build_series(
        both, start=D("2021-09-01"), end=D("2021-09-01"),
        covered=(D("2021-09-01"), D("2021-09-01")))
    assert len(series.points) == 1
    assert series.points[0].balance == Decimal("200")


def test_KRW_평가가_있으면_그_값을_그린다() -> None:
    """006 FR-068(반복 2026-10-03 #4, T139) — 해외 종목의 표 잔고는 종목 통화로 남는다. 차트가
    그것을 그리면 원화 원금 실행의 선이 달러 규모로 떨어진다. KRW 평가(`balance_krw`)가 있으면 그
    값이다."""
    krw = ConvertedRow(
        row("2021-09-01", "100", "0.1").row, fx_rate=Decimal("1150"),
        fx_rate_date=D("2021-09-01"), balance_krw=Decimal("115000"))
    series = build_series(
        SimulationResult(rows=[krw], latest=krw, as_of=D("2021-09-01"), is_final=True,
                         quote_dates=frozenset({D("2021-09-01")})),
        start=D("2021-09-01"), end=D("2021-09-01"),
        covered=(D("2021-09-01"), D("2021-09-01")))
    assert series.points[0].balance == Decimal("115000")
