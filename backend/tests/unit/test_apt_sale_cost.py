"""부동산 매도비용 — 중개 보수 + 양도소득세(1세대 1주택, 부부 5:5) (010 반복 5, T075) — FR-031,
research R10-21.

순수 함수(DB·HTTP 없음, 헌법 원칙 IV). 기대값은 손으로 계산했다(각 테스트의 주석). 원화 금액은 원
미만을 버린다.

- 중개 보수: 매수와 같은 규칙(서울 조례, 일방, 부가세 없음) — 기준일 규칙
- 양도차익 = 양도가액 − 매입가 − 취득 비용 − 매도 중개 보수. 보유 2년·거주 2년이면 비과세(12억 이하
  0, 넘으면 12억 초과 비율만)
- 장기보유특별공제: 보유 3년·거주 2년 이상 표2(보유 연 4% + 거주 연 4%, 각 최대 40%), 거주 2년
  미만이면 표1(연 2%, 최대 30%)
- 부부 5:5 — 소득금액을 반씩, 각자 기본공제 250만 원·세율·지방소득세 10%. 2년 미만 60%, 1년 미만 70%
- 거주 기간 = 보유 일수 × 비율. 규칙 표 밖(2023-01-01 앞)은 세금을 비운다
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

from src.simulation.apt_sale_cost import sale_cost

D = dt.date.fromisoformat
ONE = Decimal("1")
SALE = D("2026-10-06")
EOK = 100_000_000


def helio(ratio: Decimal = ONE):  # type: ignore[no-untyped-def]
    """25억에 판다 — 18억 매입(2021-03-15), 취득 비용 7,000만."""
    return sale_cost(
        sale_price=25 * EOK,
        buy_price=18 * EOK,
        acquisition_total=70_000_000,
        buy_date=D("2021-03-15"),
        sale_date=SALE,
        residence_ratio=ratio,
    )


class Test고가주택:
    def test_12억_초과분만_과세하고_장특공_표2를_뺀다(self) -> None:
        cost = helio()
        # 중개 보수: 15억 이상 0.7% → 17,500,000
        # 차익 = 25억 − 18억 − 7,000만 − 1,750만 = 612,500,000
        # 과세 차익 = 차익 × (25억 − 12억)/25억 = 318,500,000
        # 보유 5년·거주 5년 → 장특공 20% + 20% = 40% → 소득금액 191,100,000
        # 1인 95,550,000 − 250만 = 93,050,000 → 35% − 누진공제 1,544만 = 17,127,500
        # 지방세 1,712,750
        # 둘이면 34,255,000 + 3,425,500
        assert (cost.kind, cost.holding_years, cost.residence_years) == ("high_price", 5, 5)
        assert (cost.brokerage, cost.gain, cost.taxable_gain) == (
            17_500_000,
            612_500_000,
            318_500_000,
        )
        assert (cost.ltsd_rate, cost.base_per_owner) == (Decimal("0.40"), 93_050_000)
        assert (cost.income_tax, cost.local_tax, cost.total) == (34_255_000, 3_425_500, 55_180_500)

    def test_거주가_2년이면_장특공은_보유_20퍼센트_더하기_거주_8퍼센트다(self) -> None:
        cost = helio(Decimal("0.5"))
        # 보유 2,031일 × 0.5 = 1,015일 → 거주 2년 → 비과세 요건 충족, 장특공 20% + 8% = 28%
        # 318,500,000 × 72% = 229,320,000 → 1인 114,660,000 − 250만 = 112,160,000 → 35% − 1,544만 =
        # 23,816,000
        assert (cost.kind, cost.residence_years, cost.ltsd_rate) == (
            "high_price",
            2,
            Decimal("0.28"),
        )
        assert (cost.income_tax, cost.local_tax, cost.total) == (47_632_000, 4_763_200, 69_895_200)

    def test_거주가_2년_미만이면_비과세가_아니고_장특공은_표1이다(self) -> None:
        cost = helio(Decimal("0.3"))
        # 2,031일 × 0.3 = 609일 → 거주 1년 → 비과세 아님(차익 전부), 표1 보유 5년 10% 612,500,000 ×
        # 90% = 551,250,000 → 1인 275,625,000 − 250만 = 273,125,000 → 38% − 1,994만 = 83,847,500
        assert (cost.kind, cost.residence_years, cost.taxable_gain, cost.ltsd_rate) == (
            "taxed",
            1,
            612_500_000,
            Decimal("0.10"),
        )
        assert (cost.income_tax, cost.local_tax, cost.total) == (
            167_695_000,
            16_769_500,
            201_964_500,
        )

    def test_장특공은_보유_거주_각각_40퍼센트까지(self) -> None:
        cost = sale_cost(
            sale_price=30 * EOK,
            buy_price=10 * EOK,
            acquisition_total=40_000_000,
            buy_date=D("2012-01-02"),
            sale_date=SALE,
            residence_ratio=ONE,
        )
        assert (cost.holding_years, cost.ltsd_rate) == (14, Decimal("0.80"))


class Test비과세와_차익_없음:
    def test_12억_이하는_세금이_없다(self) -> None:
        cost = sale_cost(
            sale_price=11 * EOK,
            buy_price=8 * EOK,
            acquisition_total=30_000_000,
            buy_date=D("2019-01-10"),
            sale_date=SALE,
            residence_ratio=ONE,
        )
        # 9억~12억 0.5% → 5,500,000. 차익 264,500,000이지만 비과세
        assert (cost.kind, cost.brokerage, cost.gain, cost.taxable_gain) == (
            "exempt",
            5_500_000,
            264_500_000,
            0,
        )
        assert (cost.income_tax, cost.local_tax, cost.total) == (0, 0, 5_500_000)

    def test_차익이_없으면_세금이_없다(self) -> None:
        cost = sale_cost(
            sale_price=10 * EOK,
            buy_price=11 * EOK,
            acquisition_total=40_000_000,
            buy_date=D("2022-01-10"),
            sale_date=SALE,
            residence_ratio=ONE,
        )
        assert (cost.kind, cost.income_tax, cost.local_tax, cost.total) == (
            "no_gain",
            0,
            0,
            5_000_000,
        )

    def test_과세표준이_기본공제_이하면_세금이_없다(self) -> None:
        cost = sale_cost(
            sale_price=1_210_000_000,
            buy_price=11 * EOK,
            acquisition_total=30_000_000,
            buy_date=D("2019-01-10"),
            sale_date=SALE,
            residence_ratio=ONE,
        )
        assert cost.kind == "high_price"
        assert (cost.base_per_owner, cost.income_tax, cost.total) == (0, 0, cost.brokerage)


class Test단기:
    def test_2년_미만은_60퍼센트다(self) -> None:
        cost = sale_cost(
            sale_price=15 * EOK,
            buy_price=14 * EOK,
            acquisition_total=50_000_000,
            buy_date=D("2025-06-01"),
            sale_date=SALE,
            residence_ratio=ONE,
        )
        # 15억은 1.5억 미만 구간이 아니라 0.7% → 10,500,000. 차익 39,500,000(비과세·장특공 없음)
        # 1인 19,750,000 − 250만 = 17,250,000 × 60% = 10,350,000, 지방세 1,035,000
        assert (cost.kind, cost.holding_years, cost.brokerage, cost.ltsd_rate) == (
            "short_term",
            1,
            10_500_000,
            Decimal("0"),
        )
        assert (cost.income_tax, cost.local_tax, cost.total) == (20_700_000, 2_070_000, 33_270_000)

    def test_1년_미만은_70퍼센트다(self) -> None:
        cost = sale_cost(
            sale_price=15 * EOK,
            buy_price=14 * EOK,
            acquisition_total=50_000_000,
            buy_date=D("2026-01-10"),
            sale_date=SALE,
            residence_ratio=ONE,
        )
        # 1인 과세표준 17,250,000 × 70% = 12,075,000, 지방세 1,207,500
        assert (cost.kind, cost.holding_years) == ("short_term", 0)
        assert (cost.income_tax, cost.local_tax) == (24_150_000, 2_415_000)


def test_규칙_표_밖_기준일은_세금을_비운다() -> None:
    cost = sale_cost(
        sale_price=25 * EOK,
        buy_price=18 * EOK,
        acquisition_total=70_000_000,
        buy_date=D("2018-03-15"),
        sale_date=D("2022-06-01"),
        residence_ratio=ONE,
    )
    assert (cost.kind, cost.income_tax, cost.local_tax, cost.total) == (
        "outside_table",
        None,
        None,
        None,
    )
    assert cost.brokerage == 17_500_000
