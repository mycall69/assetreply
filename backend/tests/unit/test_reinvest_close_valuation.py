"""잔고의 종가 평가 (010 반복 3, T058) — FR-028, research R10-18.

잔고 = 보유 주식 × 그 행의 **종가**(원주가)다. 수익·수익률은 이 잔고를 따른다. **매수는 그대로 그 날
시가**다 — 첫 매수·배당 재투자의 수량·금액·수수료, 배당율(주당 배당금 ÷ 시가)이 종가로 바뀌면 주식
수와 예수금이 달라져 반복 3 전의 거래가 조용히 바뀐다.

시가와 종가를 일부러 크게 다르게 둔다 — 둘이 섞이면 어느 값이든 눈에 띄게 어긋난다.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

from src.simulation.money import quantize_rate
from src.simulation.reinvest import Condition, DayBar, DividendOn, simulate

D = dt.date.fromisoformat
M = Decimal


def condition(**over: object) -> Condition:
    base = dict(
        start=D("2021-08-01"),
        principal=M("100000"),
        currency="KRW",
        reinvest=True,
        fee_rate=M("0"),
        tax_rate=M("0"),
        reinvest_lag_days=0,
    )
    base.update(over)
    return Condition(**base)  # type: ignore[arg-type]


# 시가 30,000 → 3주(90,000), 종가 40,000이면 2주가 된다 — 매수가 시가인지 바로 드러난다.
BARS = [
    DayBar(D("2021-08-02"), M("30000"), M("40000")),
    DayBar(D("2021-09-01"), M("20000"), M("25000")),
    DayBar(D("2021-10-01"), M("50000"), M("45000")),
]


def by_date(rows: list, day: str):  # type: ignore[no-untyped-def,type-arg]
    return next(r for r in rows if r.date == D(day))


class Test잔고는_종가:
    def test_행의_종가가_그_날_일봉의_종가다(self) -> None:
        rows = simulate(BARS, [], [], condition())
        assert [
            (r.date, r.open_price, r.close_price) for r in sorted(rows, key=lambda r: r.date)
        ] == [
            (D("2021-08-02"), M("30000"), M("40000")),
            (D("2021-09-01"), M("20000"), M("25000")),
            (D("2021-10-01"), M("50000"), M("45000")),
        ]

    def test_잔고는_보유_주식_곱하기_종가다(self) -> None:
        first = by_date(simulate(BARS, [], [], condition()), "2021-08-02")
        assert (first.held_shares, first.balance) == (
            3,
            M("120000"),
        )  # 3 × 40,000 — 시가였다면 90,000

    def test_수익과_수익률이_종가_평가_잔고를_따른다(self) -> None:
        for row in simulate(BARS, [], [], condition()):
            assert row.profit == row.balance + row.cash - row.principal
            assert row.return_rate == quantize_rate(row.profit / row.principal)
        october = by_date(simulate(BARS, [], [], condition()), "2021-10-01")
        assert october.profit == M("3") * M("45000") + M("10000") - M("100000")


class Test매수는_시가:
    def test_첫_매수_수량과_예수금은_시가로_정한다(self) -> None:
        first = by_date(simulate(BARS, [], [], condition()), "2021-08-02")
        assert (first.bought_shares, first.cash) == (3, M("10000"))  # 100,000 − 3 × 30,000

    def test_수수료도_시가로_계산한다(self) -> None:
        first = by_date(simulate(BARS, [], [], condition(fee_rate=M("0.001"))), "2021-08-02")
        # 3주 × 30,000 × 0.1% = 90 — 종가로 계산했다면 120
        assert first.trade_fee == M("90.000")

    def test_배당_재투자는_그_날_시가로_사고_배당율도_시가로_나눈다(self) -> None:
        rows = simulate(BARS, [DividendOn(D("2021-09-01"), M("5000"))], [], condition())
        row = next(r for r in rows if r.kind == "dividend")
        # 배당 3주 × 5,000 = 15,000 + 예수금 10,000 = 25,000 → 시가 20,000으로 1주(종가 25,000이어도
        # 1주지만 남는 돈이 다르다)
        assert (row.bought_shares, row.held_shares, row.cash) == (1, 4, M("5000"))
        assert row.dividend_yield == quantize_rate(M("5000") / M("20000"))
        assert row.balance == M("4") * M("25000")
