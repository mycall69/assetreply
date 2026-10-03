"""가상자산 보유 시뮬레이션 (T021) — 007 FR-025~FR-031, SC-004, SC-006, research R7-7·R7-9.

**순수 함수다**(헌법 원칙 IV) — DB·HTTP 없이 돈다. 시작 월의 첫 일봉 시가로 원금 전액을 써서 **한
번** 사고 보유한다. 배당· 분할·재투자가 없다. 수량은 소수 8자리에서 버리고, 수수료는 매수 금액에
더해 예수금에서 빠진다(FR-026, FR-027).

**외부 참조 구현이 없다**(헌법 원칙 VI) — 손으로 계산한 사례를 계산 과정과 함께 적어 기대값의 근거를
남긴다.
"""
from __future__ import annotations

import datetime as dt
from decimal import Decimal, localcontext

from src.simulation.crypto_hold import DayOpen, HoldCondition, simulate_hold

D = dt.date.fromisoformat
P = Decimal
FEE = P("0.001")


def bars(*pairs: tuple[str, str]) -> list[DayOpen]:
    return [DayOpen(D(d), P(p)) for d, p in pairs]


def daily(start: str, end: str, price: str = "100") -> list[DayOpen]:
    """매일 같은 시가. 날짜가 빠짐없이 이어진다(가상자산은 휴장이 없다)."""
    first, last = D(start), D(end)
    return [DayOpen(first + dt.timedelta(days=i), P(price))
            for i in range((last - first).days + 1)]


def cond(
    start: str, principal: str = "10000", *, first_available: str | None = None
) -> HoldCondition:
    return HoldCondition(start=D(start), principal=P(principal), fee_rate=FEE,
                         first_available=D(first_available) if first_available else None)


class Test매수:
    def test_손계산_참조값(self) -> None:
        """research R7-7 — BTC 2020-01-01 시가, 원금 10,000달러, 수수료 0.1%.

        단가(수수료 포함) = 7,196.39111328125 × 1.001 = 7,203.58750439453125 수량 = ⌊10,000 ÷
        7,203.58750439453125⌋₈ = ⌊1.388197199506…⌋₈ = 1.38819719 매수 금액 = 1.38819719 ×
        7,196.39111328125 = 9,990.0099215980029296875 수수료 = 9,990.0099215980029296875 × 0.001 =
        9.9900099215980029296875 예수금 = 10,000 − 9,990.0099215980029296875 −
        9.9900099215980029296875 = 0.0000684803990673828125
        """
        outcome = simulate_hold(bars(("2020-01-01", "7196.39111328125")), cond("2020-01-15"))
        [row] = outcome.rows
        assert row.bought_quantity == P("1.38819719")
        assert row.held_quantity == P("1.38819719")
        assert row.trade_fee == P("9.9900099215980029296875")
        assert row.cash == P("0.0000684803990673828125")
        assert row.cash >= 0
        assert outcome.bought_on == D("2020-01-01")

    def test_시작일이_15일이어도_시작_월_1일_시가로_산다(self) -> None:
        outcome = simulate_hold(daily("2020-01-01", "2020-01-31"), cond("2020-01-15"))
        assert outcome.bought_on == D("2020-01-01")
        assert [r.date for r in outcome.rows] == [D("2020-01-01")]

    def test_1개_값이_원금보다_커도_소수로_산다(self) -> None:
        """analyze L3 — 원금 100달러, 시가 84,513달러, 수수료 0.1%.

        단가 = 84,513 × 1.001 = 84,597.513
        수량 = ⌊100 ÷ 84,597.513⌋₈ = ⌊0.0011820674…⌋₈ = 0.00118206
        수수료 = 0.00118206 × 84,513 × 0.001 = 0.09989943678
        예수금 = 100 − 99.89943678 − 0.09989943678 = 0.00066378322
        """
        outcome = simulate_hold(bars(("2026-09-01", "84513")), cond("2026-09-01", "100"))
        [row] = outcome.rows
        assert row.bought_quantity == P("0.00118206")
        assert row.trade_fee == P("0.09989943678")
        assert row.cash == P("0.00066378322")

    def test_원금이_최소_단위값보다_작으면_수량_0_전액_예수금(self) -> None:
        # 1e-8개 × 84,513 × 1.001 = 0.00084597513 > 0.0005 — 한 단위도 살 수 없다
        outcome = simulate_hold(bars(("2026-09-01", "84513")), cond("2026-09-01", "0.0005"))
        [row] = outcome.rows
        assert (row.bought_quantity, row.held_quantity) == (0, 0)
        assert row.cash == P("0.0005")
        assert row.trade_fee is None

    def test_아주_작은_가격도_0으로_잘리지_않는다(self) -> None:
        """FR-031 — 시가 1e-12달러. 수량이 16자리를 넘어도 정밀도를 잃지 않는다.

        수량 = ⌊10,000 ÷ (1e-12 × 1.001)⌋₈ = ⌊9,990,009,990,009,990.00999000999…⌋₈
             = 9,990,009,990,009,990.00999000
        """
        outcome = simulate_hold(bars(("2026-09-01", "0.000000000001")), cond("2026-09-01"))
        [row] = outcome.rows
        assert row.bought_quantity == P("9990009990009990.00999000")
        assert row.cash >= 0
        assert row.balance > 0

    def test_수수료를_포함한_총액이_원금을_넘지_않는다(self) -> None:
        for price in ("7196.39111328125", "0.00000529999988", "84513", "1", "0.333333"):
            outcome = simulate_hold(bars(("2021-01-01", price)), cond("2021-01-01", "777.77"))
            [row] = outcome.rows
            assert row.cash >= 0, price
            # 검산도 정밀도를 넉넉히 — 기본 28자리 문맥에서 더하면 반올림이 끼어든다
            with localcontext() as ctx:
                ctx.prec = 60
                total = row.bought_quantity * P(price) + (row.trade_fee or 0) + row.cash
            assert total == P("777.77"), price


class Test월_행:
    def test_매달_첫_일봉이_최신순으로_행이다(self) -> None:
        outcome = simulate_hold(daily("2020-01-01", "2020-04-10"), cond("2020-01-15"))
        assert [r.date for r in outcome.rows] == [
            D("2020-04-01"), D("2020-03-01"), D("2020-02-01"), D("2020-01-01")]
        # 매수는 첫 행에만, 수수료도 매수 행에만
        assert [r.bought_quantity > 0 for r in outcome.rows] == [False, False, False, True]
        assert [r.trade_fee is not None for r in outcome.rows] == [False, False, False, True]

    def test_1일이_결측이면_그_달의_첫_일봉이_행이고_결측을_표시한다(self) -> None:
        data = [b for b in daily("2021-01-01", "2021-04-05") if b.date != D("2021-03-01")]
        outcome = simulate_hold(data, cond("2021-01-01"))
        march = next(r for r in outcome.rows if r.date.month == 3)
        assert march.date == D("2021-03-02")
        assert march.first_day_missing == D("2021-03-01")
        assert all(r.first_day_missing is None for r in outcome.rows if r.date.month != 3)

    def test_시작_월_1일이_결측이면_그_달의_첫_일봉으로_사고_표시한다(self) -> None:
        outcome = simulate_hold(daily("2021-03-03", "2021-04-02"), cond("2021-03-01"))
        assert outcome.bought_on == D("2021-03-03")
        first = outcome.rows[-1]
        assert (first.date, first.first_day_missing) == (D("2021-03-03"), D("2021-03-01"))

    def test_출처의_첫_일봉_전은_결측이_아니다(self) -> None:
        """ETH는 2016-03-10에 시작한다 — 3월 1~9일은 빠진 것이 아니라 없던 날이다."""
        outcome = simulate_hold(daily("2016-03-10", "2016-04-02"),
                                cond("2016-03-10", first_available="2016-03-10"))
        first = outcome.rows[-1]
        assert (first.date, first.first_day_missing) == (D("2016-03-10"), None)

    def test_시작_월_전의_일봉은_쓰지_않는다(self) -> None:
        outcome = simulate_hold(daily("2019-12-01", "2020-02-02"), cond("2020-01-15"))
        assert outcome.rows[-1].date == D("2020-01-01")


class Test평가:
    def test_잔고는_수량_곱하기_그_행의_시가이고_예수금을_뺀다(self) -> None:
        data = bars(("2020-01-01", "100"), ("2020-02-01", "150"), ("2020-02-10", "120"))
        outcome = simulate_hold(data, cond("2020-01-01", "1000"))
        feb = outcome.rows[0]
        # 수량 = ⌊1,000 ÷ 100.1⌋₈ = 9.99000999, 잔고 = 9.99000999 × 150
        assert feb.held_quantity == P("9.99000999")
        assert feb.balance == P("9.99000999") * P("150")
        assert feb.profit == feb.balance + feb.cash - P("1000")
        assert feb.return_rate == (feb.profit / P("1000")).quantize(P("0.000001"))

    def test_latest는_마지막_일봉의_평가다(self) -> None:
        data = bars(("2020-01-01", "100"), ("2020-02-01", "150"), ("2020-02-10", "120"))
        outcome = simulate_hold(data, cond("2020-01-01", "1000"))
        assert outcome.latest is not None
        assert outcome.latest.date == D("2020-02-10")
        assert outcome.latest.bought_quantity == 0
        assert outcome.latest.trade_fee is None
        assert outcome.latest.balance == P("9.99000999") * P("120")

    def test_일봉이_없으면_빈_결과다(self) -> None:
        outcome = simulate_hold([], cond("2020-01-01"))
        assert (outcome.rows, outcome.latest, outcome.bought_on) == ([], None, None)

    def test_같은_입력은_같은_결과다(self) -> None:
        """FR-029, SC-006."""
        data = daily("2020-01-01", "2020-06-30", "7196.39111328125")
        again = simulate_hold(list(data), cond("2020-01-15"))
        assert simulate_hold(data, cond("2020-01-15")) == again
