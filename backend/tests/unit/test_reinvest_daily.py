"""일시금 하루하루 상태 (012 T013) — FR-004, FR-017, research R12-4, data-model 4.

일 단위 표는 거래일마다 상태가 필요하다. `rows`(월 행·사건 행 — 주식 차트의 재료)와 `latest`(보드)는
**그대로** 두고 `daily`를 더한다.
`rows`에 일 행을 넣으면 주식 차트가 그 행으로 그려져 차트가 바뀐다(FR-007).

- 첫 매수일부터 일봉마다 하나, 오름차순이다. 그날 사건(분할·매수·배당·재투자)을 모두 처리한 뒤의
  상태다 — 지금의 월 행 스냅숏과 같은 시점이다
- 월 행이 있는 날은 그 월 행과 값이 같다. 마지막은 `latest`와 같다
- 매수일에만 `bought_shares`·`trade_fee`가 있다
"""

from __future__ import annotations

import dataclasses
import datetime as dt
from decimal import Decimal

from src.simulation.reinvest import Condition, DayBar, DividendOn, Row, SplitOn, simulate_detailed

D = dt.date.fromisoformat
M = Decimal

#: 2021-08 ~ 2021-10의 거래일. 8-02가 매수일, 9-01 배당락, 재투자는 둘째 거래일(9-03), 10-04 분할
#: 2:1.
DAYS = [
    "2021-08-02",
    "2021-08-03",
    "2021-08-31",
    "2021-09-01",
    "2021-09-02",
    "2021-09-03",
    "2021-09-30",
    "2021-10-01",
    "2021-10-04",
    "2021-10-05",
]


def bars() -> list[DayBar]:
    out = []
    for i, day in enumerate(DAYS):
        open_ = M(40000 + 500 * i)
        out.append(DayBar(D(day), open_, open_ + M(300)))
    return out


def condition(**over: object) -> Condition:
    base = dict(
        start=D("2021-08-02"),
        principal=M("1000000"),
        currency="KRW",
        reinvest=True,
        fee_rate=M("0.00015"),
        tax_rate=M("0.154"),
        reinvest_lag_days=2,
    )
    base.update(over)
    return Condition(**base)  # type: ignore[arg-type]


def run(**over: object):  # type: ignore[no-untyped-def]
    return simulate_detailed(
        bars(),
        [DividendOn(D("2021-09-01"), M("1200"))],
        [SplitOn(D("2021-10-04"), 2, 1)],
        condition(**over),
    )


def values(row: Row) -> tuple[object, ...]:
    """값 칸 — 행의 종류와 매수 칸(그 행의 사건)을 뺀 상태."""
    return (
        row.date,
        row.open_price,
        row.close_price,
        row.held_shares,
        row.cash,
        row.principal,
        row.balance,
        row.profit,
        row.return_rate,
    )


class Test하루하루_상태:
    def test_첫_매수일부터_일봉마다_하나이고_오름차순이다(self) -> None:
        out = run()
        assert [r.date.isoformat() for r in out.daily] == DAYS
        assert all(r.kind == "day" for r in out.daily)

    def test_시작일이_달_중간이면_그_앞_일봉은_없다(self) -> None:
        out = simulate_detailed(
            [b for b in bars() if b.date >= D("2021-08-31")],
            [],
            [],
            condition(start=D("2021-08-31")),
        )
        assert out.daily[0].date == D("2021-08-31")

    def test_월_행이_있는_날은_그_월_행과_값이_같다(self) -> None:
        out = run()
        daily = {r.date: r for r in out.daily}
        months = [r for r in out.rows if r.kind == "month_first"]
        assert len(months) == 3
        for row in months:
            assert values(daily[row.date]) == values(row)

    def test_마지막은_latest와_값이_같다(self) -> None:
        out = run()
        assert out.latest is not None
        assert values(out.daily[-1]) == values(out.latest)

    def test_매수일에만_매수_수량과_수수료가_있다(self) -> None:
        out = run()
        first, *rest = out.daily
        assert first.bought_shares > 0 and first.trade_fee is not None
        assert all(r.bought_shares == 0 and r.trade_fee is None for r in rest)

    def test_배당락일과_재투자일과_분할일은_그날_사건을_모두_처리한_뒤의_상태다(self) -> None:
        out = run()
        daily = {r.date: r for r in out.daily}
        dividend = next(r for r in out.rows if r.kind == "dividend")
        reinvest = next(r for r in out.rows if r.kind == "reinvest")
        assert values(daily[dividend.date]) == values(dividend)
        assert values(daily[reinvest.date]) == values(reinvest)
        before, after = daily[D("2021-10-01")], daily[D("2021-10-04")]
        assert after.held_shares == before.held_shares * 2  # 분할 2:1이 그날 상태에 들어 있다

    def test_rows와_latest는_daily를_더하기_전과_같다(self) -> None:
        """기존 출력이 바뀌지 않는다 — `simulate`(표 행만)와 `simulate_detailed().rows`가 같다."""
        from src.simulation.reinvest import simulate

        out = run()
        assert out.rows == simulate(
            bars(),
            [DividendOn(D("2021-09-01"), M("1200"))],
            [SplitOn(D("2021-10-04"), 2, 1)],
            condition(),
        )
        assert all(r.kind in {"month_first", "dividend", "reinvest"} for r in out.rows)

    def test_한_주도_못_사도_매수일부터_상태가_있다(self) -> None:
        out = run(principal=M("1000"))
        assert out.daily[0].date == D("2021-08-02")
        assert out.daily[0].bought_shares == 0 and out.daily[0].trade_fee is None
        assert out.daily[0].cash == M("1000")

    def test_시세가_없으면_daily도_없다(self) -> None:
        out = simulate_detailed([], [], [], condition())
        assert out.daily == ()

    def test_daily를_빼고_만든_결과도_만들_수_있다(self) -> None:
        """손 조립하는 기존 테스트(005 `test_stock_series_build`)가 그대로 돈다 — 기본값이 빈
        튜플이다."""
        from src.simulation.reinvest import Outcome

        assert Outcome(rows=[], latest=None).daily == ()
        assert dataclasses.fields(Outcome)[-1].name == "daily"
