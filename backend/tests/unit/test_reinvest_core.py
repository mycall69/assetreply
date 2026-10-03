"""재투자 시뮬레이터 코어 (T024) — 005 FR-006·007·010·010a·025, SC-006.

**순수 함수다.** DB·HTTP 없이 단독으로 돈다 (헌법 원칙 IV). 이 경계가 원칙 VI 이식의
안전장치이기도 하다 — 참조 구현과 같은 입력을 넣어 같은 출력이 나오는지 단위 테스트로
확인할 수 있고, 정밀도 차이가 다른 실패에 묻히지 않는다.
"""
from __future__ import annotations

import datetime as dt
from decimal import Decimal

from src.simulation.reinvest import (
    Condition,
    DayBar,
    SplitOn,
    simulate,
)

D = dt.date.fromisoformat
ZERO = Decimal("0")


def bars(*pairs: tuple[str, str]) -> list[DayBar]:
    return [DayBar(D(d), Decimal(p)) for d, p in pairs]


def by_date(rows: list, date: str):
    """날짜로 행을 찾는다.

    `simulate`는 **최신순**으로 돌려준다 — 표가 최신부터 보이고 스크롤로 과거를
    훑기 때문이다(004의 방식). 인덱스로 집으면 그 순서에 묶여 읽기 어렵다.
    """
    return next(r for r in rows if r.date == D(date))


def condition(**over: object) -> Condition:
    base = dict(
        start=D("2021-08-01"),
        principal=Decimal("86997"),
        currency="KRW",
        reinvest=True,
        fee_rate=ZERO,
        tax_rate=Decimal("0.154"),
        reinvest_lag_days=0,  # 지연 0 = 005의 당일 재투자(006 FR-058 이전 동작)
    )
    base.update(over)
    return Condition(**base)  # type: ignore[arg-type]


class Test초기_매수:
    def test_시작_월의_첫_거래일_시가로_산다(self) -> None:
        """FR-006 — 시작일이 휴장일이어도 그 달의 첫 거래일이 기준이다."""
        rows = simulate(
            bars(("2021-08-02", "113500"), ("2021-09-01", "106000")),
            [], [], condition())
        first = by_date(rows, "2021-08-02")
        assert first.open_price == Decimal("113500")
        assert first.bought_shares == 0  # 86,997원으로 113,500원짜리를 살 수 없다

    def test_원금으로_살_수_있는_만큼_산다(self) -> None:
        rows = simulate(
            bars(("2021-08-02", "40000"), ("2021-09-01", "41000")),
            [], [], condition())
        first = by_date(rows, "2021-08-02")
        assert first.bought_shares == 2  # 86,997 ÷ 40,000 = 2
        assert first.held_shares == 2

    def test_추가_납입이_없다(self) -> None:
        """초기 1회 매수만 한다. 이후 달의 구매 주식수는 0이다."""
        rows = simulate(
            bars(("2021-08-02", "40000"), ("2021-09-01", "41000"),
                 ("2021-10-01", "42000")),
            [], [], condition())
        assert [by_date(rows, d).bought_shares
                for d in ("2021-08-02", "2021-09-01", "2021-10-01")] == [2, 0, 0]

    def test_투자금은_처음_값에서_바뀌지_않는다(self) -> None:
        rows = simulate(
            bars(("2021-08-02", "40000"), ("2021-09-01", "41000")),
            [], [], condition())
        assert all(r.principal == Decimal("86997") for r in rows)


class Test정수_매수와_예수금:
    def test_남은_돈은_예수금으로_남는다(self) -> None:
        """FR-007 — 소수점 주식을 만들지 않는다."""
        rows = simulate(bars(("2021-08-02", "40000")), [], [], condition())
        assert rows[0].held_shares == 2
        assert rows[0].cash == Decimal("6997")  # 86,997 - 80,000

    def test_보유_주식이_언제나_정수다(self) -> None:
        """SC-006."""
        rows = simulate(
            bars(("2021-08-02", "33333"), ("2021-09-01", "41000")),
            [], [], condition())
        assert all(isinstance(r.held_shares, int) for r in rows)

    def test_한_주도_못_사면_전액이_예수금이다(self) -> None:
        rows = simulate(bars(("2021-08-02", "113500")), [], [], condition())
        assert rows[0].held_shares == 0
        assert rows[0].cash == Decimal("86997")


class Test월_행_생성:
    def test_달마다_첫_거래일에_한_행이다(self) -> None:
        """FR-025 — 월 첫 거래일 스냅샷."""
        rows = simulate(
            bars(("2021-08-02", "40000"), ("2021-08-03", "40100"),
                 ("2021-09-01", "41000"), ("2021-09-02", "41100")),
            [], [], condition())
        assert [r.date for r in rows] == [D("2021-09-01"), D("2021-08-02")]

    def test_월_행은_배당_칸이_비어_있다(self) -> None:
        """FR-026 — 0을 넣으면 "배당이 0원"과 "배당이 없음"을 구별할 수 없다."""
        rows = simulate(bars(("2021-08-02", "40000")), [], [], condition())
        assert rows[0].dividend_per_share is None
        assert rows[0].dividend_yield is None

    def test_시작일_이전_달은_행을_만들지_않는다(self) -> None:
        rows = simulate(
            bars(("2021-06-01", "38000"), ("2021-08-02", "40000")),
            [], [], condition(start=D("2021-08-01")))
        assert [r.date for r in rows] == [D("2021-08-02")]

    def test_행은_최신순이다(self) -> None:
        """표가 최근부터 보이고 스크롤로 과거를 훑는다 (004의 방식)."""
        rows = simulate(
            bars(("2021-08-02", "40000"), ("2021-09-01", "41000"),
                 ("2021-10-01", "42000")),
            [], [], condition())
        assert [r.date for r in rows] == [
            D("2021-10-01"), D("2021-09-01"), D("2021-08-02")]


class Test분할:
    def test_제공처가_준_분할을_그대로_반영한다(self) -> None:
        """FR-010, FR-010a — 가격 점프로 재판정하지 않는다."""
        rows = simulate(
            bars(("2021-08-02", "40000"), ("2021-09-01", "820")),
            [], [SplitOn(D("2021-09-01"), 50, 1)], condition())
        assert by_date(rows, "2021-08-02").held_shares == 2
        assert by_date(rows, "2021-09-01").held_shares == 100

    def test_가격_점프가_없어도_적용한다(self) -> None:
        """참조 구현의 휴리스틱을 가져오지 않는다 — 원본에 없는 판단이다."""
        rows = simulate(
            bars(("2021-08-02", "40000"), ("2021-09-01", "40100")),
            [], [SplitOn(D("2021-09-01"), 2, 1)], condition())
        assert by_date(rows, "2021-09-01").held_shares == 4

    def test_역분할에서_정수로_안_떨어지면_버린다(self) -> None:
        """FR-010 — 올리거나 반올림하면 없던 주식이 생긴다."""
        rows = simulate(
            bars(("2021-08-02", "5000"), ("2021-09-01", "50000")),
            [], [SplitOn(D("2021-09-01"), 1, 10)], condition())
        assert by_date(rows, "2021-08-02").held_shares == 17  # 86,997 ÷ 5,000
        assert by_date(rows, "2021-09-01").held_shares == 1  # 17 ÷ 10 버림


class Test잔고와_수익:
    def test_잔고는_보유_주식_곱하기_시가다(self) -> None:
        """FR-013 — 예수금을 포함하지 않는다."""
        rows = simulate(
            bars(("2021-08-02", "40000"), ("2021-09-01", "50000")),
            [], [], condition())
        september = by_date(rows, "2021-09-01")
        assert september.balance == Decimal("100000")  # 2주 × 50,000
        assert september.cash == Decimal("6997")

    def test_수익은_총자산에서_투자금을_뺀_값이다(self) -> None:
        """총자산 = 잔고 + 예수금. 예수금을 빼먹으면 모든 행에서 조금씩 틀린다."""
        rows = simulate(
            bars(("2021-08-02", "40000"), ("2021-09-01", "50000")),
            [], [], condition())
        row = by_date(rows, "2021-09-01")
        assert row.profit == row.balance + row.cash - row.principal
        assert row.profit == Decimal("20000")  # 100,000 + 6,997 - 86,997


class Test빈_입력:
    def test_시세가_없으면_행이_없다(self) -> None:
        """없는 값을 만들어내지 않는다 (헌법 원칙 V)."""
        assert simulate([], [], [], condition()) == []

    def test_시작일_이후_시세가_없으면_행이_없다(self) -> None:
        rows = simulate(bars(("2021-06-01", "38000")), [], [],
                        condition(start=D("2021-08-01")))
        assert rows == []
