"""적립식 납입 일정과 납입마다의 환전 (011 T010) — FR-003~FR-005, FR-010, FR-018, research
R11-3·R11-5.

**순수 함수 모듈이다.** `repository`·`api`·`db`·`ingestion`을 임포트하지 않는다(헌법 원칙 IV).
주식·가상자산 적립식이 함께 쓴다.

**예정일은 늘 시작일에서 센다**(명확화 2026-10-06).
- 매주: 시작일 + 7k일
- 매달: 시작일의 k개월 뒤 같은 날, 없는 날이면 그 달 말일
- 매년: k년 뒤 같은 월·일, 2월 29일은 평년에 2월 28일
- 매일: 주식은 거래일만, 가상자산은 달력일

말일로 줄어든 날이나 휴장으로 미룬 날을 다음 예정일의 기준으로 삼으면 날짜가 조금씩 밀린다.

**실제 납입일 = 예정일 이후(그날 포함) 시세가 있는 첫날이다.** 휴장일·출처 결측일의 납입을 건너뛰지
않고, 다른 날의 가격으로 사지도 않는다 (헌법 원칙 V).
- 여러 예정일이 한 날로 모이면 합쳐 넣고 원래 예정일을 남긴다.
- 계산 끝까지 시세가 있는 날이 없으면 그 납입은 아직 넣지 않은 것이다. 총 납입 원금에 들지 않고 수만
  센다.

**환전은 납입마다 그날이다** — 일시금의 "돈은 살 때 바꾼다"(`build_exchange`)를 납입마다 적용한다.
- 원화 원금으로 외화 자산을 사면 그날 현금 살 때 환율(스프레드 90% 우대)로 바꾼다.
- 외화 원금이면 원화 분모를 그날 매매기준율로 정한다.
- 그날 고시가 없으면 가장 가까운 이전 확정 고시일의 값을 쓰고 그 날짜를 남긴다(`resolve_rate`).
  그것도 없으면 멈춘다 — 그 납입을 빼고 계산하면
  총 납입 원금이 조용히 준다.
"""

from __future__ import annotations

import bisect
import calendar
import datetime as dt
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Final, Literal

from src.simulation.fx_convert import (
    RateLookup,
    exchange_rate,
    resolve_rate,
    to_foreign,
    to_principal,
)

Frequency = Literal["daily", "weekly", "monthly", "yearly"]

#: 화면 순서다. 이 밖의 값은 막는다 — 기본값(매달)으로 바꿔 실행하면 사용자가 고른 것과 다른 일정의
#: 결과가 사유 없이 나온다(FR-002).
FREQUENCIES: Final[tuple[Frequency, ...]] = ("daily", "weekly", "monthly", "yearly")

FxKind = Literal["cash_buy_discounted", "base"]


class ContributionFxMissing(Exception):  # noqa: N818 — 그 납입일에 쓸 환율이 없다는 사유의 이름이다
    """그 납입일 이전의 확정 환율이 하나도 없다. 호출부가 409로 올린다."""

    def __init__(self, on: dt.date) -> None:
        super().__init__(
            f"{on.isoformat()} 이전의 환율이 없어 그날의 납입을 환전·평가할 수 없습니다.")
        self.on = on


@dataclass(frozen=True, slots=True)
class ScheduledContribution:
    """실제 납입일과 거기로 모인 예정일들. 예정일이 그날 하나뿐이면 미뤄진 것이 없다."""

    on: dt.date
    scheduled: tuple[dt.date, ...]


@dataclass(frozen=True, slots=True)
class Contribution:
    """납입 하나. `amount`는 종목·코인 통화로 바꾼 금액(예정일 n개가 모였으면 납입액 × n을 바꾼
    값)이다.

    `basis_krw`는 수익률 분모(원화)에 더할 금액이다. 원화 원금이면 넣은 원화 그대로, 외화 원금이면
    그날 매매기준율로 평가한 값이다.
    """

    on: dt.date
    scheduled: tuple[dt.date, ...]
    amount: Decimal
    basis_krw: Decimal
    #: 환전(원화 원금 — 현금 살 때 + 우대) 또는 평가(외화 원금 — 매매기준율)에 쓴 환율과 그 고시일.
    #: 원화 자산이면 없다.
    fx_rate: Decimal | None
    fx_rate_date: dt.date | None
    fx_kind: FxKind | None


def months_later(start: dt.date, months: int) -> dt.date:
    """시작일의 `months`개월 뒤 같은 날. 없는 날이면 그 달 말일 — 늘 시작일의 날짜에서 센다.

    적금의 회차일(`installment_ladder`)도 같은 규칙이다(FR-024).
    """
    index = start.month - 1 + months
    year, month = start.year + index // 12, index % 12 + 1
    return dt.date(year, month, min(start.day, calendar.monthrange(year, month)[1]))


def scheduled_dates(start: dt.date, end: dt.date, frequency: Frequency, *,
                    trading_days: Sequence[dt.date] | None) -> list[dt.date]:
    """시작일부터 계산 끝(포함)까지의 예정일. 매일은 `trading_days`(주식 — 거래일)가 있으면 그것,
    없으면(가상자산) 달력일이다."""
    if frequency not in FREQUENCIES:
        raise ValueError(f"주기는 {' · '.join(FREQUENCIES)} 중 하나여야 합니다: {frequency}")
    if start > end:
        return []
    if frequency == "daily":
        if trading_days is not None:
            return sorted(d for d in trading_days if start <= d <= end)
        return [start + dt.timedelta(days=i) for i in range((end - start).days + 1)]
    out: list[dt.date] = []
    k = 0
    while True:
        if frequency == "weekly":
            day = start + dt.timedelta(days=7 * k)
        elif frequency == "monthly":
            day = months_later(start, k)
        else:
            day = months_later(start, 12 * k)
        if day > end:
            return out
        out.append(day)
        k += 1


def assign(scheduled: Sequence[dt.date],
           available: Sequence[dt.date]) -> tuple[list[ScheduledContribution], int]:
    """예정일 → 그날 이후 시세가 있는 첫날. `(실제 납입 목록, 계산 끝 뒤로 미뤄진 수)`를
    돌려준다."""
    days = sorted(available)
    grouped: dict[dt.date, list[dt.date]] = {}
    pending = 0
    for day in sorted(scheduled):
        at = bisect.bisect_left(days, day)
        if at == len(days):
            pending += 1
            continue
        grouped.setdefault(days[at], []).append(day)
    merged = [ScheduledContribution(on, tuple(group)) for on, group in sorted(grouped.items())]
    return merged, pending


def fund(contributions: Sequence[ScheduledContribution], amount: Decimal, *,
         principal_currency: str, quote_currency: str, lookup: RateLookup | None,
         spread: Decimal | None) -> list[Contribution]:
    """납입마다 금액·환전·원화 분모를 정한다. `amount`는 한 번 납입액(원금 통화)이다."""
    out: list[Contribution] = []
    for c in contributions:
        total = amount * len(c.scheduled)
        if lookup is None:
            # 원화 자산(국내 종목·원화 시세 코인) — 바꿀 것이 없다.
            out.append(Contribution(c.on, c.scheduled, total, total, None, None, None))
            continue
        resolved = resolve_rate(lookup, c.on)
        if resolved is None:
            raise ContributionFxMissing(c.on)
        base, used = resolved
        if principal_currency == "KRW":
            if spread is None:
                raise ValueError("원화 원금을 외화로 바꾸려면 현금 살 때 스프레드가 필요합니다.")
            rate = exchange_rate(base, spread)
            working = to_foreign(total, rate, quote_currency)
            out.append(Contribution(c.on, c.scheduled, working, total, rate, used,
                                    "cash_buy_discounted"))
        else:
            out.append(Contribution(c.on, c.scheduled, total, to_principal(total, base, "KRW"),
                                    base, used, "base"))
    return out
