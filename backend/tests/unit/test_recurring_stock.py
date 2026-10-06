"""주식 적립식 (011 T014) — FR-006~FR-011, FR-014, SC-001~SC-004, research R11-4, 분석 B1.

순수 함수(DB·HTTP 없음, 헌법 원칙 IV)다. 기대값은 손으로 계산했다(각 테스트의 주석).

- 납입일마다 그날 **시가(원주가)**로, 매수 대기금 안에서 수수료를 포함해 살 수 있는 최대 정수 주식을
  산다. 남은 돈은 매수 대기금에 남는다
- 1주 + 수수료에 못 미치면 사지 않고 모은다
- 세후 배당은 배당락일에 **배당 현금**으로 들어온다(매수에 쓰이지 않는다)
  - 재투자 켬: 그 배당을 재투자일(배당락일 뒤 둘째 거래일)에 매수 대기금으로 옮겨 매수 대기금
    전액으로 산다. 그 전의 정기 매수는 그 배당을 쓰지 않는다(분석 B1)
  - 재투자 끔: 배당 현금에 계속 쌓인다
- 잔고 = 보유 × 종가. 총자산 = 잔고 + 매수 대기금 + 배당 현금
- 행: 납입(매수 0이어도) · 배당 · 재투자 · 그 달 첫 거래일(그날 납입이 없을 때만). 같은 날 사건은
  행이 따로다. 최신순
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

from src.simulation.contribution_schedule import Contribution
from src.simulation.recurring_stock import (
    RecurringCondition,
    RecurringRow,
    simulate_recurring_stock,
)
from src.simulation.reinvest import DayBar, DividendOn, SplitOn

D = dt.date.fromisoformat
M = Decimal
FEE = M("0.00015")
TAX = M("0.154")


def bar(day: str, open_: int, close: int) -> DayBar:
    return DayBar(D(day), M(open_), M(close))


def pay(day: str, amount: str, *scheduled: str) -> Contribution:
    """원화 자산의 납입 — 금액·분모가 같고 환율이 없다. 예정일을 주지 않으면 그날이다."""
    days = tuple(D(s) for s in scheduled) if scheduled else (D(day),)
    return Contribution(D(day), days, M(amount), M(amount), None, None, None)


def condition(*, reinvest: bool = True, fee: Decimal = FEE) -> RecurringCondition:
    return RecurringCondition(fee_rate=fee, tax_rate=TAX, reinvest=reinvest, reinvest_lag_days=2)


def state(row: RecurringRow) -> tuple[object, ...]:
    return (row.date.isoformat(), row.kind, row.bought_shares, row.held_shares, row.pending,
            row.balance, row.total, row.profit, row.return_rate)


class Test국내_매달:
    """시작 2024-01-15, 매달 500,000원, 수수료 0.015%. 4-15는 휴장이라 4-16에 들어간다.

    - 1-15: 500,000 ÷ (70,000 × 1.00015 = 70,010.5) → 7주, 490,073.5 지출, 수수료 73.5, 대기
      9,926.5. 잔고 7 × 71,000 = 497,000
    - 2-15: 대기 509,926.5 ÷ 69,010.35 → 7주, 483,072.45 지출, 대기 26,854.05, 보유 14
    - 3-15: 대기 526,854.05 ÷ 74,011.1 → 7주, 518,077.7 지출, 대기 8,776.35, 보유 21
    - 4-16: 대기 508,776.35 ÷ 76,011.4 → 6주, 456,068.4 지출, 대기 52,707.95, 보유 27. 잔고 27 ×
      76,500 = 2,065,500
    - 그 달 첫 거래일 행은 납입이 없는 2-01·3-04·4-01뿐이다(1월의 첫 거래일 1-15는 납입일)
    """

    BARS = [bar("2024-01-15", 70000, 71000), bar("2024-01-16", 71000, 71500),
            bar("2024-02-01", 72000, 72500), bar("2024-02-15", 69000, 69500),
            bar("2024-03-04", 73000, 73500), bar("2024-03-15", 74000, 74200),
            bar("2024-04-01", 75000, 75500), bar("2024-04-16", 76000, 76500)]
    PAYS = [pay("2024-01-15", "500000"), pay("2024-02-15", "500000"), pay("2024-03-15", "500000"),
            pay("2024-04-16", "500000", "2024-04-15")]

    def test_행마다_매수_대기금_잔고_수익률이_손계산과_같다(self) -> None:
        out = simulate_recurring_stock(self.BARS, [], [], self.PAYS, condition())
        assert [state(r) for r in out.rows] == [
            ("2024-04-16", "contribution", 6, 27, M("52707.95"), M("2065500"), M("2118207.95"),
             M("118207.95"), M("0.059104")),
            ("2024-04-01", "month_first", 0, 21, M("8776.35"), M("1585500"), M("1594276.35"),
             M("94276.35"), M("0.062851")),
            ("2024-03-15", "contribution", 7, 21, M("8776.35"), M("1558200"), M("1566976.35"),
             M("66976.35"), M("0.044651")),
            ("2024-03-04", "month_first", 0, 14, M("26854.05"), M("1029000"), M("1055854.05"),
             M("55854.05"), M("0.055854")),
            ("2024-02-15", "contribution", 7, 14, M("26854.05"), M("973000"), M("999854.05"),
             M("-145.95"), M("-0.000146")),
            ("2024-02-01", "month_first", 0, 7, M("9926.5"), M("507500"), M("517426.5"),
             M("17426.5"), M("0.034853")),
            ("2024-01-15", "contribution", 7, 7, M("9926.5"), M("497000"), M("506926.5"),
             M("6926.5"), M("0.013853")),
        ]

    def test_납입_행에_납입액_수수료_누적_원금_미뤄진_예정일이_있다(self) -> None:
        out = simulate_recurring_stock(self.BARS, [], [], self.PAYS, condition())
        last, first = out.rows[0], out.rows[-1]
        assert (last.contribution, last.trade_fee, last.contributed, last.basis_krw) == (
            M("500000"), M("68.4"), M("2000000"), M("2000000"))
        assert (last.contributions, last.deferred) == (4, (D("2024-04-15"),))
        assert (first.contribution, first.trade_fee, first.deferred) == (M("500000"), M("73.5"), ())
        month = out.rows[1]
        assert (month.contribution, month.trade_fee) == (None, None)
        assert month.contributed == M("1500000")

    def test_기준일_상태는_마지막_거래일이다(self) -> None:
        out = simulate_recurring_stock(self.BARS, [], [], self.PAYS, condition())
        assert out.latest is not None
        assert (out.latest.date, out.latest.kind, out.latest.held_shares, out.latest.total) == (
            D("2024-04-16"), "latest", 27, M("2118207.95"))
        # 매수 수수료 합(종목 통화) = 73.5 + 72.45 + 77.7 + 68.4
        assert out.buy_fee_total == M("292.05")


class Test모으다가_산다:
    def test_1주_더하기_수수료에_못_미치면_모으고_넘는_첫_납입일에_산다(self) -> None:
        # 1주 300,000 × 1.00015 = 300,045. 매주 100,000 — 셋째 주 300,000도 수수료 때문에 못 산다.
        # 넷째 주 400,000에 1주, 대기 99,955
        days = ("2024-01-01", "2024-01-08", "2024-01-15", "2024-01-22")
        bars = [bar(d, 300000, 300000) for d in days]
        pays = [pay(b.date.isoformat(), "100000") for b in bars]
        out = simulate_recurring_stock(bars, [], [], pays, condition())
        assert [(r.date.isoformat(), r.bought_shares, r.pending) for r in reversed(out.rows)] == [
            ("2024-01-01", 0, M("100000")), ("2024-01-08", 0, M("200000")),
            ("2024-01-15", 0, M("300000")), ("2024-01-22", 1, M("99955"))]
        assert all(r.trade_fee is None for r in out.rows[1:])

    def test_한_주도_못_사면_대기금만_쌓이고_납입은_버려지지_않는다(self) -> None:
        bars = [bar(d, 2000000, 2000000) for d in ("2024-01-02", "2024-02-01", "2024-03-04")]
        pays = [pay(b.date.isoformat(), "100000") for b in bars]
        out = simulate_recurring_stock(bars, [], [], pays, condition())
        assert out.latest is not None
        latest = out.latest
        assert (latest.held_shares, latest.pending, latest.total, latest.contributed) == (
            0, M("300000"), M("300000"), M("300000"))


class Test배당:
    """매일 10,000원, 시가 = 종가 = 10,000, 수수료 0. 3-05가 배당락(주당 1,000원) — 그날 아침 보유
    1주(그날 산 1주에는 배당이 없다).

    세전 1,000, 세금 154, 세후 846 → 배당 현금. 재투자일은 둘째 거래일 3-07.
    """

    BARS = [bar(d, 10000, 10000) for d in
            ("2024-03-04", "2024-03-05", "2024-03-06", "2024-03-07", "2024-03-08")]
    PAYS = [pay(b.date.isoformat(), "10000") for b in BARS]
    DIV = [DividendOn(D("2024-03-05"), M("1000"))]

    def test_배당락일에_배당_현금으로_들어오고_그날_산_주식에는_붙지_않는다(self) -> None:
        out = simulate_recurring_stock(self.BARS, self.DIV, [], self.PAYS, condition(fee=M("0")))
        dividend = next(r for r in out.rows if r.kind == "dividend")
        assert (dividend.dividend_total, dividend.dividend_tax, dividend.dividend_total_net) == (
            M("1000"), M("154.000"), M("846.000"))
        assert (dividend.held_shares, dividend.dividend_cash, dividend.pending) == (
            2, M("846"), M("0"))

    def test_재투자_켬이면_재투자일_전의_정기_매수는_배당을_쓰지_않는다(self) -> None:
        out = simulate_recurring_stock(self.BARS, self.DIV, [], self.PAYS, condition(fee=M("0")))
        by = {(r.date.isoformat(), r.kind): r for r in out.rows}
        # 3-06 납입 매수: 대기금 10,000(배당 제외) → 1주, 대기 0. 배당 현금 846은 그대로
        assert (by["2024-03-06", "contribution"].pending,
                by["2024-03-06", "contribution"].dividend_cash) == (M("0"), M("846"))
        # 3-07: 납입 매수(1주, 대기 0)가 먼저이고, 재투자 행이 배당 846을 대기금으로 옮겨 다시
        # 산다(846 < 10,000 → 0주)
        assert (by["2024-03-07", "contribution"].pending,
                by["2024-03-07", "contribution"].dividend_cash) == (M("0"), M("846"))
        reinvest = by["2024-03-07", "reinvest"]
        assert (reinvest.bought_shares, reinvest.pending, reinvest.dividend_cash) == (0, M("846"),
                                                                                      M("0"))
        # 3-08: 대기 846 + 10,000 → 1주, 대기 846
        assert by["2024-03-08", "contribution"].pending == M("846")

    def test_재투자_끔이면_배당_현금이_계속_쌓인다(self) -> None:
        out = simulate_recurring_stock(self.BARS, self.DIV, [], self.PAYS,
                                       condition(reinvest=False, fee=M("0")))
        assert all(r.kind != "reinvest" for r in out.rows)
        assert out.latest is not None
        # 닷새 × 하루 1주 = 5주(사용자 승인 2026-10-06 — 처음 기대값 6주·60,846원은 손계산 오류였다)
        assert (out.latest.pending, out.latest.dividend_cash, out.latest.held_shares) == (
            M("0"), M("846"), 5)
        # 총자산 = 5 × 10,000 + 0 + 846
        assert out.latest.total == M("50846")

    def test_재투자일이_계산_끝_뒤면_배당_현금으로_남는다(self) -> None:
        bars = self.BARS[:4]
        out = simulate_recurring_stock(bars, [DividendOn(D("2024-03-06"), M("1000"))], [],
                                       self.PAYS[:4], condition(fee=M("0")))
        assert out.latest is not None
        assert all(r.kind != "reinvest" for r in out.rows)
        assert out.latest.dividend_cash > 0

    def test_같은_날의_사건은_행이_따로이고_최신순이다(self) -> None:
        out = simulate_recurring_stock(self.BARS, self.DIV, [], self.PAYS, condition(fee=M("0")))
        same_day = [r.kind for r in out.rows if r.date == D("2024-03-05")]
        assert same_day == ["dividend", "contribution"]
        kinds = [r.kind for r in out.rows if r.date == D("2024-03-07")]
        assert kinds == ["reinvest", "contribution"]


class Test분할:
    def test_분할은_보유_수만_바꾸고_대기금과_배당_현금은_그대로다(self) -> None:
        bars = [bar("2024-06-03", 1000, 1000), bar("2024-06-10", 500, 500)]
        pays = [pay("2024-06-03", "3500"), pay("2024-06-10", "1000")]
        out = simulate_recurring_stock(bars, [], [SplitOn(D("2024-06-10"), 2, 1)], pays,
                                       condition(fee=M("0")))
        # 6-03: 3주, 대기 500. 6-10: 분할로 6주, 대기 1,500 → 500원에 3주, 대기 0, 보유 9
        got = [(r.held_shares, r.pending) for r in reversed(out.rows)]
        assert got == [(3, M("500")), (9, M("0"))]


class Test불변식:
    def test_매수_뒤_대기금은_1주_값에_못_미치고_음수가_아니다(self) -> None:
        prices = [53000, 61000, 48000, 75000, 52000, 69000, 44000, 80000, 58000, 63000]
        bars = [bar(f"2024-{i + 1:02d}-02", p, p + 500) for i, p in enumerate(prices)]
        pays = [pay(b.date.isoformat(), "123456") for b in bars]
        out = simulate_recurring_stock(bars, [], [], pays, condition())
        for r in out.rows:
            assert r.pending >= 0
            if r.kind == "contribution":
                assert r.pending < r.open_price * (1 + FEE)
        assert out.latest is not None and out.latest.contributed == M("123456") * len(bars)
