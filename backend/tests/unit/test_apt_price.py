"""시세 창 (T028) — 009 FR-008, FR-016~FR-018, SC-004, research R9-6.

DB·HTTP 없는 순수 함수다(헌법 원칙 IV). 규칙:

    그 달 평균 = 그 달(계약일 기준 달력 월) 해제·사라짐이 아닌 거래 금액 합 ÷ 건수, 원 미만
    반올림(0.5 이상 올림) 적용 시세 = 창 [1, 3, 6, 12, 24, 36]개월 중 거래가 있는 가장 짧은 창의
    평균 — 창 안 **모든 거래**의 평균이다
                (달별 평균의 평균이 아니다). 창은 기준 달을 끝으로 거꾸로 센다(기준 달 포함). 기준
                달 뒤 거래는 쓰지 않는다
    1개월 창 = 실측, 넓은 창 = 추정. 창 안에 잠정 달(오늘 기준 최근 12개월 — 설정)이 있으면 잠정
    36개월 안에 거래가 없으면 시세 없음(None) — 0이나 다른 달 값이 아니다(헌법 원칙 V)
"""
from __future__ import annotations

import datetime as dt

import pytest

from src.simulation.apt_price import (
    WINDOWS,
    MarketPrice,
    Trade,
    add_months,
    aggregate,
    first_trade_month,
    market_price,
    month_average,
    month_start,
    provisional_from,
)

D = dt.date.fromisoformat
EOK = 100_000_000
OLD = D("2000-01-01")  # 잠정 시작을 아주 옛날로 — 잠정 판정을 따로 본다


def trades(*rows: tuple[str, int]) -> list[Trade]:
    return [Trade(deal_date=D(day), amount=amount) for day, amount in rows]


def test_창은_여섯이다() -> None:
    assert WINDOWS == (1, 3, 6, 12, 24, 36)


def test_달_계산() -> None:
    assert month_start(D("2024-06-17")) == D("2024-06-01")
    assert add_months(D("2024-06-01"), -5) == D("2024-01-01")
    assert add_months(D("2024-01-01"), -1) == D("2023-12-01")
    assert add_months(D("2023-12-01"), 13) == D("2025-01-01")


class TestAggregate:
    def test_해제와_사라진_거래를_뺀다(self) -> None:
        rows = [
            Trade(D("2024-06-03"), 10 * EOK),
            Trade(D("2024-06-20"), 12 * EOK, cancelled=True),
            Trade(D("2024-06-25"), 11 * EOK, missing=True),
        ]
        monthly = aggregate(rows)
        assert monthly[D("2024-06-01")].count == 1
        assert monthly[D("2024-06-01")].total == 10 * EOK

    def test_참조값_비교용으로_해제를_넣을_수_있다(self) -> None:
        """헬리오시티 스프레드시트는 해제를 넣은 값이다(SC-003) — 사라진 거래는 그래도 뺀다."""
        rows = [
            Trade(D("2024-06-03"), 10 * EOK),
            Trade(D("2024-06-20"), 12 * EOK, cancelled=True),
            Trade(D("2024-06-25"), 11 * EOK, missing=True),
        ]
        monthly = aggregate(rows, include_cancelled=True)
        assert monthly[D("2024-06-01")].count == 2
        assert monthly[D("2024-06-01")].total == 22 * EOK

    def test_해제만_있는_달은_거래가_없다(self) -> None:
        monthly = aggregate([Trade(D("2024-06-03"), 10 * EOK, cancelled=True)])
        assert D("2024-06-01") not in monthly
        assert month_average(monthly, D("2024-06-01")) is None


class TestMonthAverage:
    def test_스프레드시트_예시(self) -> None:
        """사용자 스프레드시트의 예 — 30평대(국평) 12건 평균 2,107,083,333원, 10평대 3건 평균
        1,183,333,333원."""
        eleven = [("2021-01-10", 2_100_000_000)] * 11
        k30 = aggregate(trades(*eleven, ("2021-01-20", 2_185_000_000)))
        assert month_average(k30, D("2021-01-01")) == 2_107_083_333  # 2,107,083,333.33…
        k10 = aggregate(trades(("2021-01-05", 1_150_000_000), ("2021-01-06", 1_200_000_000),
                               ("2021-01-07", 1_200_000_000)))
        assert month_average(k10, D("2021-01-01")) == 1_183_333_333  # 1,183,333,333.33…

    @pytest.mark.parametrize(("amounts", "expected"), [
        ([1_183_333_333, 1_183_333_334], 1_183_333_334),   # …333.5 → 올림
        ([1, 2], 2),                                        # 1.5 → 올림
        ([2, 3], 3),                                        # 2.5 → 3(짝수 반올림이면 2)
        ([10, 10, 11], 10),                                 # 10.33… → 10
        ([10, 11, 11], 11),                                 # 10.66… → 11
    ])
    def test_원_미만_반올림(self, amounts: list[int], expected: int) -> None:
        monthly = aggregate(trades(*[("2024-06-01", a) for a in amounts]))
        assert month_average(monthly, D("2024-06-01")) == expected


class TestMarketPrice:
    BASE = D("2024-06-01")

    def price(self, *rows: tuple[str, int]) -> MarketPrice | None:
        return market_price(aggregate(trades(*rows)), self.BASE, provisional_from=OLD)

    def test_1개월은_실측(self) -> None:
        p = self.price(("2024-06-10", 10 * EOK), ("2024-06-20", 12 * EOK))
        assert p is not None
        assert (p.price, p.window, p.trades) == (11 * EOK, 1, 2)
        assert (p.estimated, p.provisional) == (False, False)
        assert p.month == self.BASE

    @pytest.mark.parametrize(("day", "window"), [
        ("2024-04-01", 3), ("2024-01-31", 6), ("2023-07-15", 12), ("2022-07-01", 24),
        ("2021-07-31", 36),
    ])
    def test_넓힌_창은_추정(self, day: str, window: int) -> None:
        p = self.price((day, 10 * EOK))
        assert p is not None
        assert (p.price, p.window, p.trades, p.estimated) == (10 * EOK, window, 1, True)

    def test_창의_첫_달_바로_앞은_다음_창(self) -> None:
        """3개월 창은 2024-04~06이다 — 2024-03 거래는 6개월 창에서 잡힌다."""
        p = self.price(("2024-03-31", 10 * EOK))
        assert p is not None and p.window == 6

    def test_36개월_밖이면_시세_없음(self) -> None:
        assert self.price(("2021-06-30", 10 * EOK)) is None
        assert self.price() is None

    def test_기준_달_뒤의_거래는_쓰지_않는다(self) -> None:
        """그때는 알 수 없던 미래 가격으로 과거를 평가하지 않는다(FR-016)."""
        assert self.price(("2024-07-01", 10 * EOK)) is None
        p = self.price(("2024-07-01", 99 * EOK), ("2024-05-10", 10 * EOK))
        assert p is not None and (p.price, p.window) == (10 * EOK, 3)

    def test_창_안_모든_거래의_평균이다(self) -> None:
        """달별 평균의 평균(11.5억)이 아니라 거래 넷의 평균(12.25억)이다."""
        p = self.price(("2024-05-10", 10 * EOK), ("2024-04-01", 13 * EOK), ("2024-04-02", 13 * EOK),
                       ("2024-04-03", 13 * EOK))
        assert p is not None
        assert (p.price, p.window, p.trades) == (1_225_000_000, 3, 4)

    def test_가장_짧은_창을_쓴다(self) -> None:
        p = self.price(("2024-06-10", 10 * EOK), ("2024-02-10", 20 * EOK))
        assert p is not None and (p.price, p.window, p.trades) == (10 * EOK, 1, 1)


class TestProvisional:
    TODAY = D("2026-10-05")

    def test_잠정_기간의_첫_달(self) -> None:
        assert provisional_from(self.TODAY, 12) == D("2025-11-01")
        assert provisional_from(self.TODAY, 3) == D("2026-08-01")
        assert provisional_from(self.TODAY, 1) == D("2026-10-01")

    def test_창에_잠정_달이_있으면_잠정(self) -> None:
        start = provisional_from(self.TODAY, 12)
        monthly = aggregate(trades(("2025-10-15", 10 * EOK), ("2025-11-15", 11 * EOK)))
        october = market_price(monthly, D("2025-10-01"), provisional_from=start)
        november = market_price(monthly, D("2025-11-01"), provisional_from=start)
        january = market_price(monthly, D("2026-01-01"), provisional_from=start)
        assert october is not None and october.provisional is False
        assert november is not None and november.provisional is True
        assert january is not None and (january.window, january.provisional) == (3, True)

    def test_잠정_달에_거래가_없어도_창이_덮으면_잠정(self) -> None:
        """2025-12의 6개월 창(2025-07~12)은 거래가 2025-09에만 있어도 잠정 달(2025-11·12)을 덮는다 —
        신고가 더 들어올 수 있다."""
        start = provisional_from(self.TODAY, 12)
        monthly = aggregate(trades(("2025-09-15", 10 * EOK)))
        p = market_price(monthly, D("2025-12-01"), provisional_from=start)
        assert p is not None and (p.window, p.provisional) == (6, True)


def test_첫_거래_달() -> None:
    assert first_trade_month(aggregate([])) is None
    rows = [Trade(D("2005-12-20"), EOK, cancelled=True), Trade(D("2006-02-03"), EOK),
            Trade(D("2007-01-01"), EOK)]
    assert first_trade_month(aggregate(rows)) == D("2006-02-01")
    assert first_trade_month(aggregate(rows, include_cancelled=True)) == D("2005-12-01")
