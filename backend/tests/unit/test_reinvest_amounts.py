"""표의 배당 소득세·매매 수수료 (T125) — 006 FR-059, SC-025, research R6-24. 반복 2026-10-03 #3.

세금과 수수료는 계산에서 빠지지만 행에 남지 않아, 사용자는 예수금이 왜 줄었는지 설명할 수 없었다.
시뮬레이터가 행에 남긴다(종목 통화, `Decimal`). 해당이 없는 행은 `None`이다 — "0"과 "없음"을
구별한다(005 FR-026과 같은 규약).
"""
from __future__ import annotations

import datetime as dt
from decimal import Decimal

from src.simulation.reinvest import Condition, DayBar, DividendOn, Row, simulate_detailed

D = dt.date.fromisoformat


def condition(**over: object) -> Condition:
    base = dict(start=D("2021-08-01"), principal=Decimal("100000"), currency="KRW",
                reinvest=True, fee_rate=Decimal("0.00015"), tax_rate=Decimal("0.154"),
                reinvest_lag_days=2)
    base.update(over)
    return Condition(**base)  # type: ignore[arg-type]


BARS = [DayBar(D("2021-08-02"), Decimal("10000")), DayBar(D("2021-09-01"), Decimal("2000")),
        DayBar(D("2021-09-02"), Decimal("2000")), DayBar(D("2021-09-03"), Decimal("2500")),
        DayBar(D("2021-10-01"), Decimal("2500"))]
DIVIDEND = [DividendOn(D("2021-09-01"), Decimal("1000"))]


def rows_of(**over: object) -> list[Row]:
    return simulate_detailed(BARS, DIVIDEND, [], condition(**over)).rows


def one(rows: list[Row], kind: str, date: str | None = None) -> Row:
    [row] = [r for r in rows if r.kind == kind and (date is None or r.date == D(date))]
    return row


class Test매매_수수료:
    def test_초기_매수_행에_수량_시가_수수료율의_곱이_있다(self) -> None:
        row = one(rows_of(), "month_first", "2021-08-02")
        # 100,000 ÷ (10,000 × 1.00015) → 9주. 9 × 10,000 × 0.00015 = 13.5
        assert row.bought_shares == 9
        assert row.trade_fee == Decimal("13.5")

    def test_재투자_행에도_있다(self) -> None:
        row = one(rows_of(), "reinvest")
        assert row.trade_fee == Decimal(row.bought_shares) * Decimal("2500") * Decimal("0.00015")
        assert row.bought_shares > 0

    def test_매수가_없는_행은_비어_있다(self) -> None:
        rows = rows_of()
        assert one(rows, "month_first", "2021-10-01").trade_fee is None
        assert one(rows, "dividend").trade_fee is None

    def test_수수료율이_0이어도_매수가_있으면_0이다(self) -> None:
        """"0"과 "없음"을 구별한다 — 매수가 있었고 수수료가 0이었다."""
        row = one(rows_of(fee_rate=Decimal("0")), "month_first", "2021-08-02")
        assert row.trade_fee == Decimal("0")


class Test배당_소득세:
    def test_배당락_행에_세전_배당과_세율의_곱이_있다(self) -> None:
        row = one(rows_of(), "dividend")
        # 배당락일 시작 시점의 보유 9주 × 1,000 × 0.154 = 1,386
        assert row.dividend_tax == Decimal("1386.000")

    def test_배당락_행이_아니면_비어_있다(self) -> None:
        rows = rows_of()
        assert one(rows, "reinvest").dividend_tax is None
        assert one(rows, "month_first", "2021-08-02").dividend_tax is None

    def test_예수금_감소와_맞는다(self) -> None:
        """세후 배당 = 세전 − 세금. 표의 세금으로 예수금 변화를 설명할 수 있어야 한다."""
        rows = rows_of()
        before = one(rows, "month_first", "2021-08-02").cash
        row = one(rows, "dividend")
        assert row.cash - before == Decimal(9) * Decimal("1000") - row.dividend_tax


class Test지연_0:
    def test_배당락_행에_세금과_수수료가_함께_있다(self) -> None:
        row = one(rows_of(reinvest_lag_days=0), "dividend")
        assert row.dividend_tax == Decimal("1386.000")
        assert row.bought_shares > 0
        assert row.trade_fee == Decimal(row.bought_shares) * Decimal("2000") * Decimal("0.00015")


def test_마지막_거래일_상태에는_없다() -> None:
    latest = simulate_detailed(BARS, DIVIDEND, [], condition()).latest
    assert latest is not None
    assert (latest.trade_fee, latest.dividend_tax) == (None, None)
