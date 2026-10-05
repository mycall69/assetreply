"""주식 시계열의 주가 — 분할만 반영한 수정 종가 (010 반복 1, T041) — FR-001, FR-002, FR-007, FR-008,
research R10-13.

반복 전(T004)에는 원주가 시가였다 — 분할 날 비율만큼 꺾여 폭락처럼 보였다(사용자 관찰). 이제 점의
`price`는

    수정 종가(d) = 원주가 종가(d) ÷ ∏(분자 / 분모)   — 곱은 효력일 e가 d < e ≤ 계산 끝인 분할

이다. 효력일 **당일 이후**의 종가는 이미 분할 뒤 값이라 그 분할로 나누지 않는다. 배당은 소급하지
않는다(출처의 배당 소급 수정가를 쓰지 않는다). 계산은 순수 함수
(`simulation/split_adjust.split_restated_close` — DB·HTTP 없음, 헌법 원칙 IV)이고 저장하지
않는다(원칙 V).

점은 지금처럼 표의 행 날짜뿐이고 잔고와 같은 날의 값이다(FR-007). 분할 기록은 응답에 싣지
않는다(분할 표식 없음 — FR-008).
"""
from __future__ import annotations

import datetime as dt
from decimal import Decimal

from src.api.services.stock_series import build_series
from src.api.services.stock_simulation import ConvertedRow, SimulationResult
from src.simulation.reinvest import Row, SplitOn
from src.simulation.split_adjust import split_restated_close

D = dt.date.fromisoformat
M = Decimal


def row(day: str, balance: str = "100", kind: str = "month_first") -> ConvertedRow:
    return ConvertedRow(Row(
        date=D(day), kind=kind, open_price=Decimal("1"),
        bought_shares=0, held_shares=1, cash=Decimal("0"),
        principal=Decimal("100"), balance=Decimal(balance),
        profit=Decimal("0"), return_rate=Decimal("0.1")))


def result(rows: list[ConvertedRow], closes: dict[str, str],
           splits: tuple[SplitOn, ...] = ()) -> SimulationResult:
    return SimulationResult(
        rows=rows, latest=rows[-1], as_of=rows[-1].row.date, is_final=True,
        quote_dates=frozenset(r.row.date for r in rows),
        closes={D(d): Decimal(v) for d, v in closes.items()}, splits=splits)


def build(res: SimulationResult, max_points: int = 1000):  # type: ignore[no-untyped-def]
    return build_series(res, start=D("2020-01-01"), end=D("2021-12-31"),
                        covered=(D("2020-01-01"), D("2021-12-31")), max_points=max_points)


class Test순수_함수:
    def test_분할이_없으면_원주가_종가_그대로다(self) -> None:
        assert split_restated_close(M("123.450000"), D("2021-01-04"), ()) == M("123.450000")

    def test_효력일_앞_날짜는_분할_비율로_나눈다(self) -> None:
        split = (SplitOn(D("2020-08-31"), 4, 1),)
        assert split_restated_close(M("500.000000"), D("2020-08-28"), split) == M("125.000000")

    def test_효력일_당일과_뒤는_나누지_않는다(self) -> None:
        split = (SplitOn(D("2020-08-31"), 4, 1),)
        assert split_restated_close(M("129.040000"), D("2020-08-31"), split) == M("129.040000")
        assert split_restated_close(M("130.000000"), D("2020-09-01"), split) == M("130.000000")

    def test_분할_둘은_곱한다(self) -> None:
        splits = (SplitOn(D("2014-06-09"), 7, 1), SplitOn(D("2020-08-31"), 4, 1))
        assert split_restated_close(M("560.000000"), D("2014-06-06"), splits) == M("20.000000")
        assert split_restated_close(M("400.000000"), D("2018-01-02"), splits) == M("100.000000")

    def test_병합은_곱해진다(self) -> None:
        """병합(1:10 — 분자 < 분모)이면 그 앞 날짜의 가격이 10배가 된다."""
        merge = (SplitOn(D("2021-03-01"), 1, 10),)
        assert split_restated_close(M("2.500000"), D("2021-02-26"), merge) == M("25.000000")

    def test_나누어떨어지지_않으면_소수_6자리로_반올림한다(self) -> None:
        split = (SplitOn(D("2021-06-01"), 3, 2),)
        assert split_restated_close(M("100.000000"), D("2021-05-31"), split) == M("66.666667")


class Test시계열:
    def test_점의_가격은_그_날_수정_종가다(self) -> None:
        series = build(result(
            [row("2020-08-03"), row("2020-09-01"), row("2020-10-01")],
            {"2020-08-03": "435.75", "2020-09-01": "134.18", "2020-10-01": "116.79"},
            (SplitOn(D("2020-08-31"), 4, 1),)))
        assert [(p.date, p.price) for p in series.points] == [
            (D("2020-08-03"), Decimal("108.937500")),
            (D("2020-09-01"), Decimal("134.18")),
            (D("2020-10-01"), Decimal("116.79")),
        ]

    def test_분할_앞뒤가_이어진다(self) -> None:
        """원주가 종가가 그대로면(분할 말고는 움직임 없음) 수정 종가도 같다 — 4배 꺾임이 없다."""
        series = build(result([row("2020-08-28"), row("2020-09-01")],
                              {"2020-08-28": "400.00", "2020-09-01": "100.00"},
                              (SplitOn(D("2020-08-31"), 4, 1),)))
        before, after = (p.price for p in series.points)
        assert before == after == Decimal("100.00")

    def test_배당_행이_있어도_값은_같다(self) -> None:
        """배당은 소급하지 않는다 — 같은 날의 배당락 행과 달 첫 행이 같은 수정 종가다."""
        series = build(result([row("2021-09-01", kind="dividend"), row("2021-09-01")],
                              {"2021-09-01": "152.83"}))
        assert [p.price for p in series.points] == [Decimal("152.83")]

    def test_가격은_비지_않는다(self) -> None:
        days = [f"2021-{m:02d}-01" for m in range(1, 13)]
        closes = {d: str(100 + i) for i, d in enumerate(days)}
        series = build(result([row(d) for d in days], closes))
        assert all(isinstance(p.price, Decimal) for p in series.points)

    def test_줄인_점의_가격은_그_날짜의_원래_값이다(self) -> None:
        days = [D("2021-01-01") + dt.timedelta(days=i) for i in range(60)]
        rows = [row(d.isoformat(), balance=str(1000 + (i * 37) % 101)) for i, d in enumerate(days)]
        closes = {d.isoformat(): f"{100 + (i * 7) % 13}.{i:02d}" for i, d in enumerate(days)}
        split = (SplitOn(D("2021-02-01"), 2, 1),)
        full = {p.date: p for p in build(result(rows, closes, split)).points}
        reduced = build(result(rows, closes, split), max_points=10)
        assert reduced.downsampled is True and len(reduced.points) == 10
        for point in reduced.points:
            same = full[point.date]
            assert (point.price, point.balance) == (same.price, same.balance)

    def test_그_날_종가가_없으면_지어내지_않는다(self) -> None:
        """점은 거래일(표의 행)이라 실제 경로에서는 원주가 종가가 늘 있다(통합 테스트가 본다).
        없으면 시가 등으로 메우지 않고 `None` + `missing`이다(원칙 V) — 결과를 직접 만드는 005
        테스트(`test_stock_series_build`)가 그대로 돈다."""
        point = build(result([row("2021-01-04")], {})).points[0]
        assert (point.price, point.price_missing) == (None, "missing")

    def test_분할을_넘기지_않은_결과도_만들어진다(self) -> None:
        """결과를 직접 만드는 곳(`test_stock_series_build.py`)이 있다 — 새 필드는 기본값이다."""
        bare = SimulationResult(rows=[row("2021-01-04")], latest=row("2021-01-04"),
                                as_of=D("2021-01-04"), is_final=True)
        assert (bare.splits, dict(bare.closes)) == ((), {})
