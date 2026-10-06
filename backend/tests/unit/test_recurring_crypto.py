"""가상자산 적립식 (011 T031) — FR-017~FR-019, SC-001, SC-002, research R11-6.

납입마다 그날 시가로 **매수 대기금 전액**을 써서 소수 8자리까지 산다(`buy_fraction` — 수수료
포함, 버림). 남은 돈은 다음 납입에 이어 쓴다. 잔고 = 보유 × 그날 시가(007 규칙 그대로),
총자산 = 잔고 + 매수 대기금.

손계산(수수료율 0.1%, 원화 시세 코인 — 환전 없음):

- A. 매일 1만 원, 2024-01-01 ~ 01-06
  - 01-03·01-04는 출처 결측이다. 그 둘의 납입이 01-05로 합쳐진다(3만 원)
  - 01-01 시가 5천만: 수량 ⌊10,000 ÷ 50,050,000⌋₈ = 0.00019980, 매수 9,990,
    수수료 9.99, 대기금 0.01
  - 01-02 시가 4,900만: 수량 ⌊10,000.01 ÷ 49,049,000⌋₈ = 0.00020387,
    매수 9,989.63, 수수료 9.98963, 대기금 0.39037, 보유 0.00040367
  - 01-05 시가 5,200만: 수량 ⌊30,000.39037 ÷ 52,052,000⌋₈ = 0.00057635,
    매수 29,970.2, 수수료 29.9702, 대기금 0.22017, 보유 0.00098002
    - 잔고 50,961.04, 총자산 50,961.26017, 납입 5만(5회)
    - 수익 961.26017, 수익률 0.019225
  - 01-06 시가 5,100만: 수량 0.00019588, 매수 9,989.88, 수수료 9.98988,
    대기금 0.35029, 보유 0.00117590
    - 잔고 59,970.9, 총자산 59,971.25029, 납입 6만(6회)
    - 수익 −28.74971, 수익률 −0.000479
  - 수수료 합 59.93971
- B. 매달 10만 원, 2024-01-15 시작
  - 01-01 일봉은 시작 전이다(행 없음)
  - 02-01·03-02는 그날 납입이 없는 그 달 첫 일봉이다
  - 03-01은 출처 결측이다 → 03-02 행에 `first_day_missing` 03-01
  - 01-15 시가 4,200만: 0.00237857, 대기금 0.16006
  - 02-01 시가 4,500만: 잔고 107,035.65, 총자산 107,035.81006, 수익률 0.070358
  - 02-15 시가 4,400만: 0.00227046, 보유 0.00464903, 대기금 0.01982
  - 03-02 시가 5천만: 잔고 232,451.5, 수익률 0.162258
  - 03-15 시가 4,800만: 0.00208125, 보유 0.00673028, 대기금 0.11982
  - 03-20 시가 4,900만(납입 없음, 첫 일봉 아님 → 행 없음): 잔고 329,783.72,
    총자산 329,783.83982, 수익률 0.099279
- C. 달러 시세 코인, 원화 원금
  - 환전은 `fund`가 이미 했다(금액은 달러)
  - 행은 그 납입의 환율·종류·원화 분모를 그대로 싣는다
  - 01-01 7.50달러, 시가 4만: 0.00018731, 대기금 0.0001076
  - 01-08 7.40달러, 시가 4만 2천: 0.00017601, 보유 0.00036332,
    대기금 0.00029518, 총자산 15.25973518

**순수 함수다** — DB·HTTP 없이 돈다(헌법 원칙 IV).
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

from src.simulation.contribution_schedule import (
    Contribution,
    Frequency,
    assign,
    fund,
    scheduled_dates,
)
from src.simulation.crypto_hold import DayOpen
from src.simulation.recurring_crypto import (
    RecurringCryptoOutcome,
    RecurringCryptoRow,
    simulate_recurring_crypto,
)

D = dt.date.fromisoformat
M = Decimal
FEE = M("0.001")
UNIT = M("0.00000001")


def bars(*pairs: tuple[str, str]) -> list[DayOpen]:
    return [DayOpen(D(day), M(price)) for day, price in pairs]


A_BARS = bars(("2024-01-01", "50000000"), ("2024-01-02", "49000000"),
              ("2024-01-05", "52000000"), ("2024-01-06", "51000000"))
B_BARS = bars(("2024-01-01", "40000000"), ("2024-01-15", "42000000"),
              ("2024-02-01", "45000000"), ("2024-02-15", "44000000"),
              ("2024-03-02", "50000000"), ("2024-03-15", "48000000"),
              ("2024-03-20", "49000000"))


def krw_contributions(start: str, end: str, frequency: Frequency, days: list[DayOpen],
                      amount: str) -> list[Contribution]:
    """서비스와 같은 순서 — 달력일 예정일 → 일봉 날짜에 배정 → 금액(원화 자산이라 그대로)."""
    available = [b.date for b in days if b.date >= D(start)]
    scheduled = scheduled_dates(D(start), D(end), frequency, trading_days=None)
    assigned, after_end = assign(scheduled, available)
    assert after_end == 0
    return fund(assigned, M(amount), principal_currency="KRW", quote_currency="KRW",
                lookup=None, spread=None)


def daily_a() -> RecurringCryptoOutcome:
    return simulate_recurring_crypto(
        A_BARS, krw_contributions("2024-01-01", "2024-01-06", "daily", A_BARS, "10000"),
        fee_rate=FEE, first_available=None)


def monthly_b() -> RecurringCryptoOutcome:
    return simulate_recurring_crypto(
        B_BARS, krw_contributions("2024-01-15", "2024-03-20", "monthly", B_BARS, "100000"),
        fee_rate=FEE, first_available=None)


def by_date(outcome: RecurringCryptoOutcome) -> dict[str, RecurringCryptoRow]:
    return {r.date.isoformat(): r for r in outcome.rows}


class Test매일_원화:
    def test_행은_납입마다이고_최신순이다(self) -> None:
        rows = daily_a().rows
        assert [(r.date.isoformat(), r.kind) for r in rows] == [
            ("2024-01-06", "contribution"), ("2024-01-05", "contribution"),
            ("2024-01-02", "contribution"), ("2024-01-01", "contribution")]

    def test_첫_납입은_소수_8자리로_버려_사고_남은_돈을_대기금에_둔다(self) -> None:
        first = by_date(daily_a())["2024-01-01"]
        assert first.bought_quantity == M("0.00019980")
        assert first.trade_fee == M("9.99")
        assert first.pending == M("0.01")
        assert first.held_quantity == M("0.00019980")

    def test_남은_돈은_다음_납입에_이어_쓴다(self) -> None:
        second = by_date(daily_a())["2024-01-02"]
        assert second.bought_quantity == M("0.00020387")
        assert second.trade_fee == M("9.98963")
        assert (second.pending, second.held_quantity) == (M("0.39037"), M("0.00040367"))

    def test_출처_결측일의_납입은_다음_일봉에_합친다(self) -> None:
        row = by_date(daily_a())["2024-01-05"]
        assert row.contribution == M("30000")
        assert row.deferred == (D("2024-01-03"), D("2024-01-04"))
        assert row.bought_quantity == M("0.00057635")
        assert row.trade_fee == M("29.9702")
        assert (row.held_quantity, row.pending) == (M("0.00098002"), M("0.22017"))
        assert (row.contributed, row.basis_krw, row.contributions) == (M("50000"), M("50000"), 5)

    def test_잔고는_보유_곱하기_그날_시가이고_총자산은_대기금을_더한다(self) -> None:
        row = by_date(daily_a())["2024-01-05"]
        assert row.open_price == M("52000000")
        assert row.balance == M("50961.04")
        assert row.total == M("50961.26017")
        assert (row.profit, row.return_rate) == (M("961.26017"), M("0.019225"))

    def test_미뤄지지_않은_납입에는_미뤄진_날이_없다(self) -> None:
        row = by_date(daily_a())["2024-01-02"]
        assert (row.contribution, row.deferred) == (M("10000"), ())

    def test_마지막_평가와_수수료_합(self) -> None:
        outcome = daily_a()
        latest = outcome.latest
        assert latest is not None
        assert latest.date == D("2024-01-06")
        assert (latest.held_quantity, latest.pending) == (M("0.00117590"), M("0.35029"))
        assert (latest.balance, latest.total) == (M("59970.9"), M("59971.25029"))
        assert (latest.contributed, latest.contributions) == (M("60000"), 6)
        assert (latest.profit, latest.return_rate) == (M("-28.74971"), M("-0.000479"))
        assert outcome.buy_fee_total == M("59.93971")

    def test_일봉마다의_평가는_오름차순이다(self) -> None:
        daily = daily_a().daily
        assert [d.date.isoformat() for d in daily] == [
            "2024-01-01", "2024-01-02", "2024-01-05", "2024-01-06"]
        assert daily[-1].total == M("59971.25029")

    def test_원화_시세_코인은_환율이_없다(self) -> None:
        for row in daily_a().rows:
            assert (row.fx_rate, row.fx_rate_date, row.fx_kind) == (None, None, None)


class Test매달과_그_달_첫_일봉:
    def test_그날_납입이_없는_그_달_첫_일봉만_행이다(self) -> None:
        rows = monthly_b().rows
        assert [(r.date.isoformat(), r.kind) for r in rows] == [
            ("2024-03-15", "contribution"), ("2024-03-02", "month_first"),
            ("2024-02-15", "contribution"), ("2024-02-01", "month_first"),
            ("2024-01-15", "contribution")]

    def test_그_달_첫_일봉_행은_사지_않고_그날_상태를_보인다(self) -> None:
        row = by_date(monthly_b())["2024-02-01"]
        assert (row.bought_quantity, row.trade_fee, row.contribution, row.deferred) == (
            M("0"), None, None, ())
        assert (row.held_quantity, row.pending) == (M("0.00237857"), M("0.16006"))
        assert (row.balance, row.total) == (M("107035.65"), M("107035.81006"))
        assert row.return_rate == M("0.070358")
        assert row.first_day_missing is None

    def test_1일이_결측이면_그_달_첫_일봉_행이_그_1일을_싣는다(self) -> None:
        """007 FR-030과 같은 뜻 — 결측일을 채우지 않고(헌법 원칙 V) 그 사실을 보인다."""
        row = by_date(monthly_b())["2024-03-02"]
        assert (row.kind, row.first_day_missing) == ("month_first", D("2024-03-01"))
        assert (row.balance, row.return_rate) == (M("232451.5"), M("0.162258"))

    def test_시작_전_일봉은_행도_평가도_없다(self) -> None:
        outcome = monthly_b()
        assert "2024-01-01" not in by_date(outcome)
        assert outcome.daily[0].date == D("2024-01-15")
        assert len(outcome.daily) == 6

    def test_첫_납입_행은_그_달_첫_일봉이_아니면_결측을_싣지_않는다(self) -> None:
        assert by_date(monthly_b())["2024-01-15"].first_day_missing is None

    def test_마지막_평가는_마지막_일봉이다(self) -> None:
        latest = monthly_b().latest
        assert latest is not None
        assert latest.date == D("2024-03-20")
        assert (latest.held_quantity, latest.pending) == (M("0.00673028"), M("0.11982"))
        assert (latest.balance, latest.total) == (M("329783.72"), M("329783.83982"))
        assert (latest.contributed, latest.contributions) == (M("300000"), 3)
        assert latest.return_rate == M("0.099279")


class Test출처의_첫_일봉:
    def _run(self, first_available: dt.date | None) -> RecurringCryptoOutcome:
        days = bars(("2024-01-10", "40000000"), ("2024-02-03", "41000000"))
        contributions = krw_contributions("2024-01-10", "2024-01-31", "monthly", days, "100000")
        return simulate_recurring_crypto(days, contributions, fee_rate=FEE,
                                         first_available=first_available)

    def test_출처의_첫_일봉_전의_1일은_결측이_아니라_없던_날이다(self) -> None:
        rows = by_date(self._run(D("2024-01-10")))
        assert rows["2024-01-10"].first_day_missing is None
        assert rows["2024-02-03"].first_day_missing == D("2024-02-01")

    def test_첫_일봉을_모르면_그_달의_첫_행이_1일_결측을_싣는다(self) -> None:
        """그 달의 첫 일봉이 납입 행이어도 같다 — 그 달의 행이 1일이 아니라는 007의 사실이다."""
        rows = by_date(self._run(None))
        assert (rows["2024-01-10"].kind, rows["2024-01-10"].first_day_missing) == (
            "contribution", D("2024-01-01"))


class Test외화_시세:
    def _run(self) -> RecurringCryptoOutcome:
        days = bars(("2024-01-01", "40000"), ("2024-01-08", "42000"))
        contributions = [
            Contribution(D("2024-01-01"), (D("2024-01-01"),), M("7.50"), M("10000"),
                         M("1333.33"), D("2023-12-29"), "cash_buy_discounted"),
            Contribution(D("2024-01-08"), (D("2024-01-08"),), M("7.40"), M("10000"),
                         M("1351.35"), D("2024-01-08"), "cash_buy_discounted"),
        ]
        return simulate_recurring_crypto(days, contributions, fee_rate=FEE, first_available=None)

    def test_행은_납입의_환율과_고시일과_종류를_싣는다(self) -> None:
        rows = by_date(self._run())
        assert (rows["2024-01-01"].fx_rate, rows["2024-01-01"].fx_rate_date,
                rows["2024-01-01"].fx_kind) == (M("1333.33"), D("2023-12-29"),
                                                "cash_buy_discounted")

    def test_코인_통화로_사고_원화_분모를_쌓는다(self) -> None:
        rows = by_date(self._run())
        first, second = rows["2024-01-01"], rows["2024-01-08"]
        assert (first.bought_quantity, first.pending) == (M("0.00018731"), M("0.0001076"))
        assert (second.bought_quantity, second.held_quantity) == (M("0.00017601"),
                                                                  M("0.00036332"))
        assert second.pending == M("0.00029518")
        assert (second.contributed, second.basis_krw) == (M("14.90"), M("20000"))
        assert second.total == M("15.25973518")


class Test불변식:
    def test_매수_뒤_대기금은_0_이상이고_한_단위를_더_살_돈보다_적다(self) -> None:
        """SC-003과 같은 뜻의 가상자산 판 — 8자리 한 단위를 더 살 수 있으면 덜 산 것이다."""
        prices = [M(30000000 + 137000 * ((i * 7) % 23)) for i in range(60)]
        days = [DayOpen(D("2024-01-01") + dt.timedelta(days=i), p) for i, p in enumerate(prices)]
        contributions = krw_contributions("2024-01-01", "2024-02-29", "daily", days, "12345")
        outcome = simulate_recurring_crypto(days, contributions, fee_rate=FEE,
                                            first_available=None)
        for row in outcome.rows:
            assert row.pending >= 0
            assert row.pending < row.open_price * UNIT * (1 + FEE)
        latest = outcome.latest
        assert latest is not None
        assert latest.contributed == M("12345") * 60  # SC-002 — 넣은 예정일 수 × 납입액

    def test_일봉이_없으면_빈_결과다(self) -> None:
        outcome = simulate_recurring_crypto([], [], fee_rate=FEE, first_available=None)
        assert (outcome.rows, outcome.latest, outcome.daily, outcome.buy_fee_total) == (
            [], None, [], M("0"))
