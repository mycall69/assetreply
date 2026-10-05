"""매입·보유 계산 (T032) — 009 FR-005, FR-006, FR-021, FR-022, FR-025~FR-027, SC-008, research
R9-7·R9-8.

DB·HTTP 없는 순수 함수다(헌법 원칙 IV). 거래는 그 단지·평형 구분의 달별 집계(해제·사라짐 제외)로
받는다.

    행 = 매입 달 ~ 이번 달, 한 달에 한 줄, 최신순 평가액 = 그 달 적용 시세(없으면 비움 — 0이 아니다)
    누적 비용 = 취득 비용 + 그 달까지 낸 보유세 투자 수익 = 평가액 − 매입가 − 누적 비용, 수익률 =
    투자 수익 ÷ (매입가 + 취득 비용) 보유세 = 매입일 ≤ 그해 6월 1일인 해마다. 기준 금액 = 그해 6월
    적용 시세 × 비율(기본 0.6, 공시가격 대용)
                재산세 7월·9월(일괄이면 7월), 종부세 12월. 6월 시세가 없으면 그해 세금은 계산
                불가(0이 아니다)
    시작 가능 날짜 = 첫 거래 달 1일과 세법 표의 첫 날(2006-01-01) 중 늦은 날

세액 자체는 `test_apt_tax.py`의 참조값이 지킨다 — 여기서는 그 세액이 **어느 달에 얼마나**
들어가는지를 본다. 기본 장면: 매달 한 건씩 10억 원에 거래된 30평대(국평), 2021-03-15 매입, 오늘
2023-02-10.

    취득 비용 = 취득세 30,000,000 + 지방교육세 3,000,000 + 중개 보수 9,000,000 = 42,000,000
    2021년 기준 금액 6억 → 재산세 1,260,000(7월 630,000 · 9월 630,000), 종부세 0(1인 3억 ≤ 공제 6억)
    2022년 기준 금액 6억 → 재산세 810,000(7월 405,000 · 9월 405,000), 종부세 0
"""
from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest

from src.simulation.apt_area import bucket_by_key
from src.simulation.apt_holding import (
    BeforeStartable,
    HoldingResult,
    HoldingRow,
    NoPriceAtPurchase,
    NoTradesInArea,
    simulate_holding,
)
from src.simulation.apt_price import MonthTotal, Trade, add_months, aggregate

D = dt.date.fromisoformat
EOK = 100_000_000
K30 = bucket_by_key("30k")
L30 = bucket_by_key("30l")
TODAY = D("2023-02-10")


def every_month(first: str, last: str, amount: int = 10 * EOK,
                skip: tuple[str, ...] = ()) -> list[Trade]:
    rows: list[Trade] = []
    month = D(first + "-01")
    end = D(last + "-01")
    while month <= end:
        if f"{month:%Y-%m}" not in skip:
            rows.append(Trade(deal_date=month.replace(day=15), amount=amount))
        month = add_months(month, 1)
    return rows


def run(trades: list[Trade], buy: str = "2021-03-15", *, price: int | None = None,
        today: dt.date = TODAY, ratio: str = "0.6", area: str = "30k") -> HoldingResult:
    monthly: dict[dt.date, MonthTotal] = aggregate(trades)
    return simulate_holding(monthly, buy_date=D(buy), buy_price=price, area=bucket_by_key(area),
                            today=today, holding_tax_base_ratio=Decimal(ratio),
                            provisional_months=12)


def row(result: HoldingResult, month: str) -> HoldingRow:
    return next(r for r in result.rows if r.month == D(month + "-01"))


BASE = every_month("2019-01", "2023-02")
#: 2010년 거래 뒤 2014-07까지 거래가 없다 — 2013-12 ~ 2014-06은 36개월 안에 거래가 없다.
GAPPED = [*every_month("2010-01", "2010-12", amount=5 * EOK),
          *every_month("2014-07", "2014-12", amount=5 * EOK)]


class TestRows:
    def test_매입_달부터_이번_달까지_최신순(self) -> None:
        result = run(BASE)
        months = [r.month for r in result.rows]
        assert months[0] == D("2023-02-01") and months[-1] == D("2021-03-01")
        assert len(months) == 24
        assert months == sorted(months, reverse=True)

    def test_매입_행(self) -> None:
        result = run(BASE)
        first = row(result, "2021-03")
        assert first.acquisition is not None
        cost = first.acquisition
        assert (cost.acquisition_tax, cost.education_tax, cost.rural_tax, cost.brokerage_fee) == (
            30_000_000, 3_000_000, 0, 9_000_000)
        assert cost.total == 42_000_000
        assert (first.cumulative_cost, first.value, first.profit) == (
            42_000_000, 10 * EOK, -42_000_000)
        assert first.return_rate == Decimal("-0.040307")
        assert all(r.acquisition is None for r in result.rows if r.month != D("2021-03-01"))

    def test_그_달_거래와_평균(self) -> None:
        trades = [*BASE, Trade(D("2022-05-20"), 12 * EOK)]
        r = row(run(trades), "2022-05")
        assert (r.trades, r.month_average) == (2, 11 * EOK)
        assert r.price is not None and (r.price.price, r.price.window) == (11 * EOK, 1)

    def test_보유세는_납부_달에만(self) -> None:
        result = run(BASE)
        july = row(result, "2021-07").property_tax
        september = row(result, "2021-09").property_tax
        december = row(result, "2021-12").comprehensive_tax
        assert july is not None and (july.amount, july.installment) == (630_000, "1/2")
        assert september is not None
        assert (september.amount, september.installment) == (630_000, "2/2")
        assert december is not None and december.amount == 0  # 공제 이하
        assert row(result, "2022-07").property_tax is not None
        assert row(result, "2022-07").property_tax.amount == 405_000  # type: ignore[union-attr]
        paid_months = {r.month for r in result.rows if r.property_tax is not None}
        assert paid_months == {D("2021-07-01"), D("2021-09-01"), D("2022-07-01"), D("2022-09-01")}
        assert all(r.comprehensive_tax is None for r in result.rows if r.month.month != 12)
        assert all(r.property_tax is None for r in result.rows if r.month.month not in (7, 9))

    def test_보유세의_기준_시세(self) -> None:
        tax = row(run(BASE), "2021-07").property_tax
        assert tax is not None
        assert (tax.base_price, tax.rule_date) == (6 * EOK, D("2021-06-01"))
        assert (tax.basis.month, tax.basis.price, tax.basis.window, tax.basis.estimated) == (
            D("2021-06-01"), 10 * EOK, 1, False)

    def test_누적_비용과_수익률(self) -> None:
        result = run(BASE)
        last = result.rows[0]
        assert last.cumulative_cost == 42_000_000 + 1_260_000 + 810_000
        assert (last.value, last.profit) == (10 * EOK, -44_070_000)
        assert last.return_rate == Decimal("-0.042294")
        assert row(result, "2021-08").cumulative_cost == 42_000_000 + 630_000


class TestTaxYears:
    def test_6월_1일_매입은_그해_보유세가_있다(self) -> None:
        result = run(BASE, "2021-06-01")
        assert row(result, "2021-07").property_tax is not None

    def test_6월_2일_매입은_그해_보유세가_없다(self) -> None:
        result = run(BASE, "2021-06-02")
        assert all(r.property_tax is None for r in result.rows if r.month.year == 2021)
        assert row(result, "2022-07").property_tax is not None

    def test_납부_달이_오지_않은_세금은_넣지_않는다(self) -> None:
        result = run(BASE, today=D("2022-07-10"))
        assert result.rows[0].month == D("2022-07-01")
        assert result.summary.property_tax_total == 1_260_000 + 405_000
        assert all(r.comprehensive_tax is None for r in result.rows if r.month.year == 2022)

    def test_소액이면_7월_일괄(self) -> None:
        low = every_month("2019-01", "2023-02", amount=EOK)
        result = run(low, "2022-03-15")
        july = row(result, "2022-07").property_tax
        assert july is not None and july.installment == "1/1"
        assert row(result, "2022-09").property_tax is None

    def test_6월_시세가_없는_해는_계산_불가(self) -> None:
        """2010년 거래 뒤 2014-07까지 거래가 없다 — 2014-06의 36개월 창(2011-07~2014-06)이 비어 그해
        보유세를 계산하지 못한다."""
        trades = GAPPED
        result = run(trades, "2010-03-15", today=D("2015-01-10"))
        assert result.summary.tax_gaps == (2014,)
        for month in ("2014-07", "2014-09"):
            r = row(result, month)
            assert (r.property_tax, r.property_tax_gap) == (None, True)
        december = row(result, "2014-12")
        assert (december.comprehensive_tax, december.comprehensive_tax_gap) == (None, True)
        # 2013-06은 36개월 창에 2010-07~12가 있다
        assert row(result, "2013-07").property_tax is not None

    def test_기준_비율(self) -> None:
        tax = row(run(BASE, ratio="0.7"), "2021-07").property_tax
        assert tax is not None and tax.base_price == 7 * EOK


class TestPrices:
    def test_시세_없음_달은_평가하지_않는다(self) -> None:
        trades = GAPPED
        result = run(trades, "2010-03-15", today=D("2015-01-10"))
        for month in ("2013-12", "2014-03", "2014-06"):
            r = row(result, month)
            assert (r.price, r.value, r.profit, r.return_rate) == (None, None, None, None)
        assert row(result, "2013-11").value == 5 * EOK  # 2013-11의 36개월 창에 2010-12가 있다

    def test_넓힌_창은_추정(self) -> None:
        trades = every_month("2019-01", "2023-02", skip=("2022-05",))
        r = row(run(trades), "2022-05")
        assert r.trades == 0 and r.month_average is None
        assert r.price is not None and (r.price.window, r.price.estimated) == (3, True)

    def test_잠정은_최근_12개월(self) -> None:
        result = run(BASE)
        assert row(result, "2022-03").price.provisional is True  # type: ignore[union-attr]
        assert row(result, "2022-02").price.provisional is False  # type: ignore[union-attr]
        assert result.summary.provisional is True

    def test_지금_시세가_없으면_마지막_시세_달까지의_결과(self) -> None:
        result = run(every_month("2019-01", "2019-12"), "2019-03-15")
        assert result.summary.value is None
        assert result.summary.last_priced_month == D("2022-11-01")
        assert result.summary.profit == row(result, "2022-11").profit
        assert result.summary.return_rate == row(result, "2022-11").return_rate


class TestPurchase:
    def test_시세로_산다(self) -> None:
        result = run(BASE)
        assert (result.buy_price, result.buy_price_source) == (10 * EOK, "market")
        assert result.buy_price_window is not None and result.buy_price_window.window == 1
        assert result.invested == 10 * EOK + 42_000_000

    def test_직접_넣은_매입가(self) -> None:
        result = run(BASE, price=9 * EOK)
        assert (result.buy_price, result.buy_price_source) == (9 * EOK, "input")
        assert result.acquisition.total == 27_000_000 + 2_700_000 + 8_100_000
        last = result.rows[0]
        assert last.value == 10 * EOK  # 평가액은 그대로 시세다
        assert last.profit == 60_130_000
        assert last.return_rate == Decimal("0.064118")

    def test_매입_달_시세가_없으면_막는다(self) -> None:
        trades = GAPPED
        with pytest.raises(NoPriceAtPurchase) as caught:
            run(trades, "2014-03-15", today=D("2015-01-10"))
        assert caught.value.month == D("2014-03-01")
        result = run(trades, "2014-03-15", price=5 * EOK, today=D("2015-01-10"))
        assert result.buy_price_window is None

    def test_85제곱미터_초과는_농어촌특별세(self) -> None:
        result = run(BASE, area="30l")
        assert (result.acquisition.rural_tax, result.acquisition.total) == (2_000_000, 44_000_000)


class TestStartable:
    def test_첫_거래_달보다_이르면_막는다(self) -> None:
        with pytest.raises(BeforeStartable) as caught:
            run(BASE, "2018-12-31")
        assert (caught.value.startable_from, caught.value.basis) == (D("2019-01-01"), "first_trade")
        assert run(BASE, "2019-01-01").startable_from == D("2019-01-01")

    def test_세법_표보다_이르면_막는다(self) -> None:
        """출처는 2005-12 계약분부터 주지만 세법 표는 2006-01-01부터다(FR-005, FR-023)."""
        trades = every_month("2005-12", "2007-12", amount=3 * EOK)
        with pytest.raises(BeforeStartable) as caught:
            run(trades, "2005-12-20", today=D("2008-01-10"))
        assert (caught.value.startable_from, caught.value.basis) == (D("2006-01-01"), "tax_rules")

    def test_거래가_없으면_막는다(self) -> None:
        with pytest.raises(NoTradesInArea):
            run([])


def test_같은_입력은_같은_결과() -> None:
    """확정 달의 결과는 다시 계산해도 같다(SC-008)."""
    assert run(BASE) == run(BASE)


def test_요약() -> None:
    summary = run(BASE).summary
    assert summary.as_of == TODAY
    assert summary.property_tax_total == 2_070_000
    assert (summary.comprehensive_tax_total, summary.holding_tax_total) == (0, 2_070_000)
    assert (summary.value, summary.value_month) == (10 * EOK, D("2023-02-01"))
    assert summary.profit == -44_070_000
    assert summary.return_rate == Decimal("-0.042294")
    assert (summary.tax_gaps, summary.last_priced_month, summary.estimated) == ((), None, False)
