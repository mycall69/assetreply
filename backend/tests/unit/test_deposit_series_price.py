"""예금 시계열의 그 달 금리 (010 T005) — FR-001~FR-003, FR-007, SC-002, research R10-5.

점의 `price` = 점 날짜의 달 `m`에 **발표된** 그 투자처의 금리 — 시뮬레이션이 그 달 가입·재예치에
읽는 바로 그 값(`rates[m]`, FR-002). 값이 없는 달은 지어내지 않는다(헌법 원칙 V).

- `m > latest_month`(아직 발표되지 않은 달) → `None` + `unpublished`. 계산은 마지막 발표 달 금리로
  잠정이지만(008), **대신 쓴 그 금리를
  그 달 금리로 내지 않는다** — 발표되지 않은 값이 발표된 것처럼 보인다
- `m ∉ rates`(발표 기간 안인데 통계가 빈 달) → `None` + `missing`. 만기 사이의 달이면 계산이 멈추지
  않아 점이 있다
- `rates`·`latest_month`는 **기본값 없는 필수 인자**다 — 기본값이 있으면 경로가 넘기기를 잊어도 모든
  점이 조용히 "미발표"가 된다
"""
from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest

from src.api.services.deposit_series import build_series
from src.simulation.deposit_rollover import DepositOutcome, simulate_deposit

D = dt.date.fromisoformat
START = D("2020-01-15")
LATEST = D("2021-12-01")
MISSING = D("2020-06-01")  # 만기 사이의 빈 달 — 가입·재예치가 읽지 않아 계산이 이어진다


def months(first: str, last: str) -> list[dt.date]:
    out, month, end = [], D(first), D(last)
    while month <= end:
        out.append(month)
        month = month.replace(year=month.year + month.month // 12, month=month.month % 12 + 1)
    return out


RATES = {m: Decimal("1.50") + Decimal(i) / 100
         for i, m in enumerate(months("2020-01-01", "2021-12-01")) if m != MISSING}


def outcome(end: str = "2022-03-10") -> DepositOutcome:
    return simulate_deposit(principal=Decimal("10000000"), start=START, end=D(end), rates=RATES,
                            first_month=D("2020-01-01"), latest_month=LATEST,
                            tax_rate=Decimal("0.154"))


def series(out: DepositOutcome | None = None, max_points: int = 1000):  # type: ignore[no-untyped-def]
    return build_series(out or outcome(), start=START, rates=RATES, latest_month=LATEST,
                        max_points=max_points)


def test_발표된_달은_그_달_금리다() -> None:
    for point in series().points:
        month = point.date.replace(day=1)
        if month <= LATEST and month in RATES:
            assert (point.price, point.price_missing) == (RATES[month], None), point.date


def test_발표되지_않은_달은_비고_미발표다() -> None:
    """2022-01-15 재예치는 잠정(2021-12 금리로 대신)이다 — 그 대신 쓴 금리가 점의 가격이 되면 안
    된다."""
    later = [p for p in series().points if p.date.replace(day=1) > LATEST]
    assert [p.date for p in later] == [
        D("2022-01-01"), D("2022-01-15"), D("2022-02-01"), D("2022-03-01"), D("2022-03-10")]
    assert all((p.price, p.price_missing) == (None, "unpublished") for p in later)


def test_발표_기간_안의_빈_달은_비고_결측이다() -> None:
    by_date = {p.date: p for p in series().points}
    assert (by_date[MISSING].price, by_date[MISSING].price_missing) == (None, "missing")


def test_가입_재예치_행의_적용_금리와_그_날_점의_가격이_같다() -> None:
    """FR-002 — 그 달 가입·재예치에 쓴 금리와 차트의 그 달 금리가 같다(잠정 행은 대신 쓴 금리라
    제외)."""
    out = outcome()
    by_date = {p.date: p for p in series(out).points}
    starts = [r for r in out.rows if r.kind in ("join", "reinvest")]
    assert len(starts) == 3
    for r in starts:
        if r.provisional:
            assert by_date[r.date].price is None
        else:
            assert by_date[r.date].price == r.rate, r.date


def test_값이_있으면_사유가_없다() -> None:
    for point in series().points:
        assert (point.price is None) == (point.price_missing is not None), point.date


def test_줄인_점의_가격은_그_날짜의_원래_값이다() -> None:
    full = {p.date: p for p in series().points}
    reduced = series(max_points=6)
    assert reduced.downsampled is True and len(reduced.points) == 6
    for point in reduced.points:
        assert (point.price, point.price_missing, point.balance) == (
            full[point.date].price, full[point.date].price_missing, full[point.date].balance)


def test_금리를_넘기지_않으면_만들지_않는다() -> None:
    """기본값이 있으면 경로가 넘기기를 잊어도 조용히 모든 점이 "미발표"다 — 필수 인자라 바로
    실패한다."""
    with pytest.raises(TypeError):
        build_series(outcome(), start=START)  # type: ignore[call-arg]
