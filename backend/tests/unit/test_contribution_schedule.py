"""적립식 납입 일정·납입마다의 환전 (011 T004) — FR-003~FR-005, FR-010, FR-018, SC-002, research
R11-3·R11-5.

순수 함수(DB·HTTP 없음, 헌법 원칙 IV)다.

- 예정일은 **늘 시작일에서 센다** — 미룬 날을 다음 예정일의 기준으로 삼지 않는다.
  - 매주: 시작일 + 7k
  - 매달: 시작일 날짜, 없으면 그 달 말일
  - 매년: 같은 월·일, 2월 29일은 평년에 2월 28일
  - 매일: 주식은 거래일, 가상자산은 달력일
- 실제 납입일 = 예정일 이후(그날 포함) 시세가 있는 첫날. 여럿이 한 날로 모이면 합친다. 계산 끝까지
  날이 없으면 아직 넣지 않는다.
- 환전
  - 원화 원금·외화 종목: 납입마다 그날 현금 살 때 환율(스프레드 90% 우대)
  - 외화 원금: 원화 분모 = 납입액 × 그날 매매기준율
  - 그날 고시가 없으면 가장 가까운 이전 확정일, 그것도 없으면 멈춘다
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest

from src.simulation.contribution_schedule import (
    Contribution,
    ContributionFxMissing,
    ScheduledContribution,
    assign,
    fund,
    scheduled_dates,
)
from src.simulation.fx_convert import RateLookup

D = dt.date.fromisoformat
M = Decimal


def days(*isos: str) -> list[dt.date]:
    return [D(x) for x in isos]


class Test예정일:
    def test_매달은_시작일_날짜이고_없는_달은_말일이다(self) -> None:
        got = scheduled_dates(D("2024-01-31"), D("2024-06-30"), "monthly", trading_days=None)
        assert got == days("2024-01-31", "2024-02-29", "2024-03-31", "2024-04-30", "2024-05-31",
                           "2024-06-30")

    def test_매달은_늘_시작일에서_센다(self) -> None:
        # 4-30 다음이 5-30이 아니라 5-31이다 — 말일로 줄어든 날을 다음 기준으로 삼지 않는다
        got = scheduled_dates(D("2023-01-31"), D("2023-05-31"), "monthly", trading_days=None)
        assert got[-2:] == days("2023-04-30", "2023-05-31")

    def test_매주는_시작일_더하기_7일씩이다(self) -> None:
        got = scheduled_dates(D("2024-01-03"), D("2024-01-31"), "weekly", trading_days=None)
        assert got == days("2024-01-03", "2024-01-10", "2024-01-17", "2024-01-24", "2024-01-31")

    def test_매년_2월_29일은_평년에_2월_28일이다(self) -> None:
        got = scheduled_dates(D("2020-02-29"), D("2024-03-01"), "yearly", trading_days=None)
        assert got == days("2020-02-29", "2021-02-28", "2022-02-28", "2023-02-28", "2024-02-29")

    def test_매일_주식은_넘긴_거래일만이다(self) -> None:
        trading = days("2024-01-02", "2024-01-03", "2024-01-05", "2024-01-08")
        got = scheduled_dates(D("2024-01-03"), D("2024-01-07"), "daily", trading_days=trading)
        assert got == days("2024-01-03", "2024-01-05")

    def test_매일_가상자산은_달력일이다(self) -> None:
        got = scheduled_dates(D("2024-02-27"), D("2024-03-01"), "daily", trading_days=None)
        assert got == days("2024-02-27", "2024-02-28", "2024-02-29", "2024-03-01")

    def test_계산_끝을_포함하고_시작이_끝보다_늦으면_비어_있다(self) -> None:
        assert scheduled_dates(D("2024-01-15"), D("2024-01-15"), "monthly", trading_days=None) == [
            D("2024-01-15")]
        assert scheduled_dates(D("2024-01-16"), D("2024-01-15"), "weekly", trading_days=None) == []

    def test_모르는_주기는_막는다(self) -> None:
        with pytest.raises(ValueError, match="주기"):
            scheduled_dates(D("2024-01-15"), D("2024-02-15"), "hourly",  # type: ignore[arg-type]
                            trading_days=None)


class Test실제_납입일:
    def test_휴장일_예정일은_다음_거래일로_간다(self) -> None:
        got, pending = assign(days("2024-01-01"), days("2024-01-02", "2024-01-03"))
        assert got == [ScheduledContribution(D("2024-01-02"), (D("2024-01-01"),))]
        assert pending == 0

    def test_긴_연휴로_모인_예정일은_한_날에_합친다(self) -> None:
        # 매주 납입일 9-15(월)·9-22(월) 사이가 모두 휴장 — 둘 다 9-23에 들어간다
        got, pending = assign(days("2026-09-15", "2026-09-22"), days("2026-09-14", "2026-09-23"))
        assert got == [ScheduledContribution(D("2026-09-23"), (D("2026-09-15"), D("2026-09-22")))]
        assert pending == 0

    def test_그날이_거래일이면_미뤄짐이_없다(self) -> None:
        got, _ = assign(days("2024-01-02", "2024-01-09"), days("2024-01-02", "2024-01-09"))
        assert got == [ScheduledContribution(D("2024-01-02"), (D("2024-01-02"),)),
                       ScheduledContribution(D("2024-01-09"), (D("2024-01-09"),))]

    def test_계산_끝_뒤로_미뤄지는_납입은_넣지_않고_센다(self) -> None:
        got, pending = assign(days("2026-09-29", "2026-10-03"), days("2026-09-29", "2026-09-30"))
        assert got == [ScheduledContribution(D("2026-09-29"), (D("2026-09-29"),))]
        assert pending == 1

    def test_예정일_수는_합쳐도_줄지_않는다(self) -> None:
        scheduled = scheduled_dates(D("2024-01-01"), D("2024-03-31"), "weekly", trading_days=None)
        available = [d for d in (D("2024-01-01") + dt.timedelta(days=i) for i in range(91))
                     if d.weekday() < 5 and d not in {D("2024-02-09"), D("2024-02-12")}]
        got, pending = assign(scheduled, available)
        assert sum(len(c.scheduled) for c in got) + pending == len(scheduled)


class Test환전:
    LOOKUP = RateLookup({D("2024-01-02"): M("1300.000000"), D("2024-01-09"): M("1310.000000")})

    def test_원화로_원화_자산을_사면_그대로다(self) -> None:
        got = fund([ScheduledContribution(D("2024-01-02"), (D("2024-01-02"),))], M("500000"),
                   principal_currency="KRW", quote_currency="KRW", lookup=None, spread=None)
        assert got == [Contribution(D("2024-01-02"), (D("2024-01-02"),), M("500000"), M("500000"),
                                    None, None, None)]

    def test_원화_원금은_납입마다_그날_현금_살_때_환율로_바꾼다(self) -> None:
        # 1300 × (1 + 0.0175 × 0.1) = 1302.275000 → 500,000 ÷ 1302.275 = 383.94달러
        got = fund([ScheduledContribution(D("2024-01-02"), (D("2024-01-02"),))], M("500000"),
                   principal_currency="KRW", quote_currency="USD", lookup=self.LOOKUP,
                   spread=M("0.0175"))
        assert got == [Contribution(D("2024-01-02"), (D("2024-01-02"),), M("383.94"), M("500000"),
                                    M("1302.275000"), D("2024-01-02"), "cash_buy_discounted")]

    def test_그날_고시가_없으면_가장_가까운_이전_확정일을_쓴다(self) -> None:
        got = fund([ScheduledContribution(D("2024-01-05"), (D("2024-01-05"),))], M("500000"),
                   principal_currency="KRW", quote_currency="USD", lookup=self.LOOKUP,
                   spread=M("0.0175"))
        assert (got[0].fx_rate, got[0].fx_rate_date) == (M("1302.275000"), D("2024-01-02"))

    def test_납입마다_그날_환율이다(self) -> None:
        got = fund([ScheduledContribution(D("2024-01-02"), (D("2024-01-02"),)),
                    ScheduledContribution(D("2024-01-09"), (D("2024-01-09"),))], M("500000"),
                   principal_currency="KRW", quote_currency="USD", lookup=self.LOOKUP,
                   spread=M("0.0175"))
        # 1310 × 1.00175 = 1312.292500 → 500,000 ÷ 1312.2925 = 381.01달러
        assert [(c.amount, c.fx_rate) for c in got] == [(M("383.94"), M("1302.275000")),
                                                       (M("381.01"), M("1312.292500"))]

    def test_외화_원금은_원화_분모를_그날_매매기준율로_정한다(self) -> None:
        got = fund([ScheduledContribution(D("2024-01-02"), (D("2024-01-02"),))], M("300"),
                   principal_currency="USD", quote_currency="USD", lookup=self.LOOKUP, spread=None)
        assert got == [Contribution(D("2024-01-02"), (D("2024-01-02"),), M("300"), M("390000"),
                                    M("1300.000000"), D("2024-01-02"), "base")]

    def test_모인_예정일만큼_금액이_는다(self) -> None:
        got = fund([ScheduledContribution(D("2024-01-02"), (D("2024-01-01"), D("2024-01-02")))],
                   M("500000"), principal_currency="KRW", quote_currency="USD", lookup=self.LOOKUP,
                   spread=M("0.0175"))
        # 1,000,000 ÷ 1302.275 = 767.89달러
        assert (got[0].amount, got[0].basis_krw) == (M("767.89"), M("1000000"))

    def test_그날_이전_환율이_없으면_멈춘다(self) -> None:
        with pytest.raises(ContributionFxMissing) as caught:
            fund([ScheduledContribution(D("2023-12-29"), (D("2023-12-29"),))], M("500000"),
                 principal_currency="KRW", quote_currency="USD", lookup=self.LOOKUP,
                 spread=M("0.0175"))
        assert caught.value.on == D("2023-12-29")
