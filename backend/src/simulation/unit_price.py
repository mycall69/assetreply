"""단가 등락 (013 반복 2026-10-09 T089) — spec FR-011a, research R13-18, data-model 3.2.

비교 표의 시작일 단가·기준일 단가·등락(차이·등락률). 단가 값은 부르는 쪽(비교 경로)이 지금 계산이
이미 가진 값에서 고른다 — 주식은 수정주가(`split_adjust.split_restated_close` — 메뉴 차트의 주가
선과 같은 함수), 가상자산은 UTC 일봉 시가, 예금은 발표 금리, 부동산은 그 달 시세. 이 모듈은 두 값의
차이와 비율, 분할 누적 비율 글자만 낸다.

- 값이 하나라도 없으면 차이·등락률은 `None`이다 — 가까운 날·달의 값으로 메우지 않는다(헌법 원칙 V)
- 금리는 차이(%p)만이다 — 금리의 변화율은 읽기 어렵다(사용자 답 2026-10-09)
- 비율 표기는 수익률(`returnRate`)과 같다 — 비율 값, 소수 6자리(`quantize_rate`)

**순수 함수 모듈이다.** `repository`·`api`·`db`를 임포트하지 않는다(헌법 원칙 IV). 계산은
`Decimal`이다(헌법 원칙 VI).
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal
from math import gcd
from typing import Literal

from src.simulation.money import quantize_rate
from src.simulation.reinvest import SplitOn

UnitKind = Literal["share", "coin", "home", "rate"]
UnitBasis = Literal["split_restated_close", "daily_open", "market_price", "published_rate"]
#: 값이 없는 까닭 — `no_price` 그 날(달)의 값이 없음, `no_trades` 그 평형의 거래가 없어 시세가 없음.
Missing = Literal["no_price", "no_trades"]


@dataclass(frozen=True, slots=True)
class PricePoint:
    """단가 하나 — `date`는 값의 실제 날짜다(휴장이면 매수일, 금리·부동산은 그 달 1일)."""

    date: dt.date
    value: Decimal | None
    provisional: bool = False
    estimated: bool = False
    missing: Missing | None = None


@dataclass(frozen=True, slots=True)
class UnitPrice:
    kind: UnitKind
    basis: UnitBasis
    #: 주식 상장국 통화·가상자산 시세 통화·부동산 `KRW`. 금리는 `None`.
    currency: str | None
    start: PricePoint
    as_of: PricePoint
    #: 기준일 − 시작일(금리는 %p). 어느 한쪽이 없으면 `None`.
    change: Decimal | None
    #: 차이 ÷ 시작일(비율 값). 금리·시작일 0은 `None`.
    change_rate: Decimal | None
    #: 주식 — 시작일 뒤 분할·병합의 누적 비율 글자(`"50:1"`, 병합 `"1:10"`). 없으면 `None`.
    split_ratio: str | None = None


def unit_price(kind: UnitKind, basis: UnitBasis, currency: str | None, start: PricePoint,
               as_of: PricePoint, *, split_ratio: str | None = None) -> UnitPrice:
    """두 단가의 차이와 등락률을 붙인다."""
    change: Decimal | None = None
    change_rate: Decimal | None = None
    # 시작일 단가 0은 금리(0%)만 뜻이 있다 — 가격이 0이면 등락을 비운다.
    usable = start.value is not None and as_of.value is not None and (
        kind == "rate" or start.value != 0)
    if usable and start.value is not None and as_of.value is not None:
        change = as_of.value - start.value
        if kind != "rate":
            change_rate = quantize_rate(change / start.value)
    return UnitPrice(kind=kind, basis=basis, currency=currency, start=start, as_of=as_of,
                     change=change, change_rate=change_rate, split_ratio=split_ratio)


def split_ratio(splits: Iterable[SplitOn], after: dt.date) -> str | None:
    """`after` 뒤에 효력이 생긴 분할·병합의 누적 비율 — `split_restated_close`가 시작일 종가를
    나누는 그 비율이다. 없거나 서로 지워져 1:1이면 `None`."""
    numerator = denominator = 1
    for split in splits:
        if split.date > after:
            numerator *= split.numerator
            denominator *= split.denominator
    common = gcd(numerator, denominator)
    numerator, denominator = numerator // common, denominator // common
    if numerator == denominator:
        return None
    return f"{numerator}:{denominator}"
