"""주식 적립식 하루하루 상태 (012 T014) — FR-004, FR-005, FR-017, research R12-4, data-model 4.

일 단위 표는 거래일마다 상태가 필요하다. `rows`(사건 행·그 달 첫 거래일 행 — 차트·보드의 재료)와
`latest`는 그대로 두고 `daily`를 더한다.

- 첫 납입일부터 일봉마다 하나이고 `kind = "day"`다. 그날 사건(분할·납입·배당·재투자)을 모두 처리한
  뒤의 상태다
- 납입·배당·재투자 날은 그날 **마지막 사건 행**과 값이 같다 — 그 사건 행이 그날의 상태를
  보인다(FR-005)
- 그 달 첫 거래일 행이 있는 날은 그 행과 같다. 마지막은 `latest`와 같다
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

from src.simulation.contribution_schedule import Contribution
from src.simulation.recurring_stock import (
    RecurringCondition,
    RecurringOutcome,
    RecurringRow,
    simulate_recurring_stock,
)
from src.simulation.reinvest import DayBar, DividendOn, SplitOn

D = dt.date.fromisoformat
M = Decimal

DAYS = [
    "2026-08-31",
    "2026-09-01",
    "2026-09-02",
    "2026-09-03",
    "2026-09-04",
    "2026-09-07",
    "2026-09-08",
    "2026-09-09",
    "2026-10-01",
    "2026-10-02",
]


def bars() -> list[DayBar]:
    return [DayBar(D(day), M(50000 + 700 * i), M(50300 + 700 * i)) for i, day in enumerate(DAYS)]


def pay(day: str, amount: str = "300000") -> Contribution:
    return Contribution(D(day), (D(day),), M(amount), M(amount), None, None, None)


def run() -> RecurringOutcome:
    # 9-01·9-04·10-02 납입, 9-04 배당락(납입과 같은 날), 재투자는 둘째 거래일 9-08, 9-09 분할 2:1.
    # 10-01은 납입 없는 그 달 첫 거래일
    return simulate_recurring_stock(
        bars(),
        [DividendOn(D("2026-09-04"), M("500"))],
        [SplitOn(D("2026-09-09"), 2, 1)],
        [pay("2026-09-01"), pay("2026-09-04"), pay("2026-10-02")],
        RecurringCondition(
            fee_rate=M("0.00015"), tax_rate=M("0.154"), reinvest=True, reinvest_lag_days=2
        ),
    )


def values(row: RecurringRow) -> tuple[object, ...]:
    return (
        row.date,
        row.open_price,
        row.close_price,
        row.held_shares,
        row.pending,
        row.dividend_cash,
        row.contributed,
        row.basis_krw,
        row.contributions,
        row.balance,
        row.total,
        row.profit,
        row.return_rate,
    )


class Test하루하루_상태:
    def test_첫_납입일부터_일봉마다_하나이고_kind는_day다(self) -> None:
        out = run()
        assert [r.date.isoformat() for r in out.daily] == DAYS[1:]  # 8-31은 첫 납입 전이다
        assert {r.kind for r in out.daily} == {"day"}

    def test_사건_날은_그날_마지막_사건_행과_값이_같다(self) -> None:
        out = run()
        daily = {r.date: r for r in out.daily}
        by_day: dict[dt.date, list[RecurringRow]] = {}
        for row in reversed(out.rows):  # 처리 차례(행은 최신순 — 같은 날은 늦은 사건이 위다)
            if row.kind != "month_first":
                by_day.setdefault(row.date, []).append(row)
        assert {d.isoformat() for d in by_day} == {
            "2026-09-01",
            "2026-09-04",
            "2026-09-08",
            "2026-10-02",
        }
        assert [r.kind for r in by_day[D("2026-09-04")]] == ["contribution", "dividend"]
        for day, events in by_day.items():
            assert values(daily[day]) == values(events[-1]), day

    def test_그_달_첫_거래일_행이_있는_날은_그_행과_같다(self) -> None:
        out = run()
        daily = {r.date: r for r in out.daily}
        months = [r for r in out.rows if r.kind == "month_first"]
        assert [r.date.isoformat() for r in months] == [
            "2026-10-01"
        ]  # 9월 첫 거래일(9-01)은 납입 행이 보인다
        for row in months:
            assert values(daily[row.date]) == values(row)

    def test_마지막은_latest와_같다(self) -> None:
        out = run()
        assert out.latest is not None
        assert values(out.daily[-1]) == values(out.latest)

    def test_분할일은_분할을_반영한_상태다(self) -> None:
        out = run()
        daily = {r.date: r for r in out.daily}
        assert daily[D("2026-09-09")].held_shares == daily[D("2026-09-08")].held_shares * 2

    def test_rows와_latest는_그대로다(self) -> None:
        out = run()
        assert all(
            r.kind in {"contribution", "dividend", "reinvest", "month_first"} for r in out.rows
        )
        assert RecurringOutcome(rows=[], latest=None, buy_fee_total=M("0")).daily == ()
