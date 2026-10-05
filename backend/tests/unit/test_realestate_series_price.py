"""부동산 시계열의 그 달 실거래가 평균 (010 T006) — FR-001, FR-003, FR-006, FR-007, FR-011, research
R10-6.

점의 `price` = 그 점이 나온 행의 `month_average`(같은 단지·같은 평형, 해제 제외 — 표의 "그 달
평균"). 첫 점(매입일)은 매입 달 행, 끝점(계산 끝)은 그 달 행(`rows[0]` — 행은 내림차순)이다.

- 거래 없는 달 → `None` + `no_trades`. 그 점의 평가액·수익률·추정은 **지금처럼 적용 시세**(넓힌 창의
  추정 포함)다 — 적용 시세를 실거래가
  자리에 넣으면 거래가 없던 달에 거래가 있던 것처럼 읽힌다(FR-011)
- 시세 없음 달은 지금처럼 점이 없고 `gaps`(`no_price`)다 — 36개월 창 안에 거래가 없으니 그 달
  실거래도 없다
"""
from __future__ import annotations

import datetime as dt
from decimal import Decimal

from src.api.services.realestate_series import build_series
from src.simulation.apt_area import bucket_by_key
from src.simulation.apt_holding import HoldingResult, HoldingRow, simulate_holding
from src.simulation.apt_price import Trade, add_months, aggregate

D = dt.date.fromisoformat
EOK = 100_000_000
TODAY = D("2023-02-10")


def every_month(first: str, last: str, amount: int = 10 * EOK,
                skip: tuple[str, ...] = ()) -> list[Trade]:
    rows: list[Trade] = []
    month, end = D(first + "-01"), D(last + "-01")
    while month <= end:
        if f"{month:%Y-%m}" not in skip:
            rows.append(Trade(deal_date=month.replace(day=15),
                              amount=amount + month.month * 1_000_000))
        month = add_months(month, 1)
    return rows


def run(trades: list[Trade], buy: str = "2021-03-15") -> HoldingResult:
    return simulate_holding(aggregate(trades), buy_date=D(buy), buy_price=None,
                            area=bucket_by_key("30k"), today=TODAY,
                            holding_tax_base_ratio=Decimal("0.6"), provisional_months=12)


SKIPPED = run(every_month("2019-01", "2023-02", skip=("2021-05", "2021-06", "2022-09")))
#: 2010년 거래 뒤 2014-07까지 거래가 없다 — 2013-12 ~ 2014-06은 시세 없음.
GAPPED = simulate_holding(
    aggregate([*every_month("2010-01", "2010-12", amount=5 * EOK),
               *every_month("2014-07", "2014-12", amount=5 * EOK)]),
    buy_date=D("2010-03-15"), buy_price=None, area=bucket_by_key("30k"), today=D("2014-12-20"),
    holding_tax_base_ratio=Decimal("0.6"), provisional_months=12)


def month_rows(result: HoldingResult) -> dict[dt.date, HoldingRow]:
    return {r.month: r for r in result.rows}


def test_점의_가격은_그_달_행의_실거래가_평균이다() -> None:
    rows = month_rows(SKIPPED)
    for point in build_series(SKIPPED).points:
        row = rows[point.date.replace(day=1)]
        assert point.price == row.month_average, point.date


def test_첫_점은_매입_달_끝점은_그_달_행이다() -> None:
    points = build_series(SKIPPED).points
    assert points[0].date == D("2021-03-15")
    assert points[0].price == month_rows(SKIPPED)[D("2021-03-01")].month_average
    assert points[-1].date == TODAY
    assert points[-1].price == SKIPPED.rows[0].month_average
    assert SKIPPED.rows[0].month == D("2023-02-01")


def test_거래_없는_달은_비고_사유가_있고_평가는_적용_시세다() -> None:
    rows = month_rows(SKIPPED)
    by_date = {p.date: p for p in build_series(SKIPPED).points}
    for month in (D("2021-05-01"), D("2021-06-01"), D("2022-09-01")):
        point, row = by_date[month], rows[month]
        assert (point.price, point.price_missing) == (None, "no_trades")
        assert (point.balance, point.return_rate) == (row.value, row.return_rate)
        assert point.estimated is True  # 넓힌 창 — 추정 표식은 평가액에만 붙는다(FR-006)


def test_값이_있으면_사유가_없다() -> None:
    for point in build_series(SKIPPED).points:
        assert (point.price is None) == (point.price_missing is not None), point.date


def test_시세_없음_달은_점이_없고_gaps는_그대로다() -> None:
    series = build_series(GAPPED)
    gaps = [(g.start, g.end, g.reason) for g in series.gaps]
    assert gaps == [(D("2013-12-01"), D("2014-06-01"), "no_price")]
    assert not any(D("2013-12-01") <= p.date <= D("2014-06-01") for p in series.points)


def test_줄인_점의_가격은_그_날짜의_원래_값이다() -> None:
    full = {p.date: p for p in build_series(SKIPPED).points}
    reduced = build_series(SKIPPED, max_points=8)
    assert reduced.downsampled is True and len(reduced.points) == 8
    for point in reduced.points:
        assert (point.price, point.price_missing, point.balance) == (
            full[point.date].price, full[point.date].price_missing, full[point.date].balance)
