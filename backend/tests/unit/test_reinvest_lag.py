"""재투자 시점 (T124) — 006 FR-058, SC-024, research R6-22. 반복 2026-10-03 #3.

세후 배당은 **배당락일에 예수금에 들어오고**, 재투자 매수는 **배당락일 뒤 2번째 거래일의 시가**로
그날 예수금 전액을 써서 한다. 005 FR-008(배당락일 당일 시가 매수)을 대체한다. 거래일은 **그 종목의
시세 날짜**로 센다 — 달력일로 세면 휴장일에 매수가 걸려 시가가 없고 매수가 조용히 사라진다.

지연은 순수 함수의 매개변수(`reinvest_lag_days`)다. 0이면 005와 같다 — 참조 구현 대조가 그것을 쓴다.
"""
from __future__ import annotations

import datetime as dt
from decimal import Decimal

from src.simulation.reinvest import Condition, DayBar, DividendOn, Row, simulate, simulate_detailed

D = dt.date.fromisoformat


def condition(**over: object) -> Condition:
    base = dict(start=D("2021-08-01"), principal=Decimal("100000"), currency="KRW",
                reinvest=True, fee_rate=Decimal("0"), tax_rate=Decimal("0.154"),
                reinvest_lag_days=2)
    base.update(over)
    return Condition(**base)  # type: ignore[arg-type]


def bars(*pairs: tuple[str, str]) -> list[DayBar]:
    return [DayBar(D(d), Decimal(p)) for d, p in pairs]


#: 2021-08-02(월) 1만 원에 10주. 2021-09-01(수) 배당락, 그 뒤 거래일 09-02(목)·09-03(금)·09-06(월).
WEEK = bars(("2021-08-02", "10000"), ("2021-09-01", "2000"), ("2021-09-02", "2000"),
            ("2021-09-03", "2500"), ("2021-09-06", "3000"))
DIVIDEND = [DividendOn(D("2021-09-01"), Decimal("1000"))]


def of(rows: list[Row], kind: str) -> list[Row]:
    return [r for r in rows if r.kind == kind]


class Test배당락일:
    def test_세후_배당이_들어오고_그날은_사지_않는다(self) -> None:
        [row] = of(simulate(WEEK, DIVIDEND, [], condition()), "dividend")
        assert row.date == D("2021-09-01")
        # 10주 × 1,000 × (1 - 0.154) = 8,460 — 아직 사지 않았다.
        assert row.bought_shares == 0
        assert row.held_shares == 10
        assert row.cash == Decimal("8460.000")


class Test두_번째_거래일에_산다:
    def test_배당락_뒤_두_번째_거래일_시가로_예수금_전액을_쓴다(self) -> None:
        [row] = of(simulate(WEEK, DIVIDEND, [], condition()), "reinvest")
        # 09-01(수) 배당락 → 09-02(목) 1번째, 09-03(금) 2번째. 2,500원짜리 3주.
        assert row.date == D("2021-09-03")
        assert row.open_price == Decimal("2500")
        assert row.bought_shares == 3
        assert row.held_shares == 13
        assert row.cash == Decimal("960.000")

    def test_휴장일은_세지_않는다(self) -> None:
        """2021-09-17(금) 배당락, 09-20~22 추석 연휴 — 1번째 09-23(목), 2번째 09-24(금)."""
        holiday = bars(("2021-08-02", "10000"), ("2021-09-17", "2000"),
                       ("2021-09-23", "2000"), ("2021-09-24", "2400"))
        [row] = of(simulate(holiday, [DividendOn(D("2021-09-17"), Decimal("1000"))], [],
                            condition()), "reinvest")
        assert row.date == D("2021-09-24")
        assert row.bought_shares == 3  # 8,460 ÷ 2,400

    def test_두_번째_거래일이_기간_밖이면_예수금으로_남는다(self) -> None:
        short = bars(("2021-08-02", "10000"), ("2021-09-01", "2000"), ("2021-09-02", "2000"))
        outcome = simulate_detailed(short, DIVIDEND, [], condition())
        assert of(outcome.rows, "reinvest") == []
        assert outcome.latest is not None
        assert outcome.latest.held_shares == 10
        assert outcome.latest.cash == Decimal("8460.000")

    def test_한_주에도_못_미치면_재투자_행이_없다(self) -> None:
        rows = simulate(WEEK, [DividendOn(D("2021-09-01"), Decimal("10"))], [], condition())
        assert of(rows, "reinvest") == []

    def test_월_첫_거래일과_겹치면_재투자를_먼저_하고_스냅샷을_찍는다(self) -> None:
        """09-29(수) 배당락 → 09-30(목) 1번째, 10-01(금) 2번째 = 10월 첫 거래일."""
        month_end = bars(("2021-08-02", "10000"), ("2021-09-29", "2000"),
                         ("2021-09-30", "2000"), ("2021-10-01", "2000"))
        rows = simulate(month_end, [DividendOn(D("2021-09-29"), Decimal("1000"))], [],
                        condition())
        [reinvest] = of(rows, "reinvest")
        [october] = [r for r in of(rows, "month_first") if r.date == D("2021-10-01")]
        assert reinvest.date == D("2021-10-01")
        assert reinvest.bought_shares == 4
        # 월 행의 보유 수는 재투자 뒤다 — 월 행에서 산 것은 없다.
        assert october.held_shares == 14
        assert october.bought_shares == 0


class Test재투자_끔:
    def test_매수가_없고_예수금에_쌓인다(self) -> None:
        outcome = simulate_detailed(WEEK, DIVIDEND, [], condition(reinvest=False))
        assert of(outcome.rows, "reinvest") == []
        assert outcome.latest is not None
        assert outcome.latest.held_shares == 10
        assert outcome.latest.cash == Decimal("8460.000")


class Test지연_0:
    """참조 구현 대조(005 T108)가 쓰는 길이다. 005와 같아야 한다."""

    def test_배당락일_당일_시가로_산다(self) -> None:
        rows = simulate(WEEK, DIVIDEND, [], condition(reinvest_lag_days=0))
        [row] = of(rows, "dividend")
        assert row.bought_shares == 4  # 8,460 ÷ 2,000
        assert row.held_shares == 14
        assert of(rows, "reinvest") == []
