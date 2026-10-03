"""환전과 평가 환산 (T073, T074, T075) — 005 FR-019~023, FR-041a~041c.

**두 환율을 한 함수에 두지 않는다.** 초기 환전은 **실제로 돈을 바꾸는** 1회 행위라
현금 살 때 환율에 우대가 붙고, 평가 환산은 **값어치를 재는 것**이라 매매기준율을
쓴다. 한 함수에 두면 어느 쪽인지 호출부마다 판단해야 하고, 틀려도 값이 그럴듯하다
(FR-041b).

**순수 함수 모듈이다.** `repository`·`api`·`db`를 임포트하지 않는다 (헌법 원칙 IV).
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from decimal import Decimal

from src.simulation.money import quantize_money

#: 외환 수수료 우대율. **스프레드의 90%를 깎는다** — 결과적으로 스프레드의 10%만
#: 적용된다 (FR-020). 방향을 반대로 잡으면 환전 금액이 조용히 달라지는데, 오류도
#: 나지 않고 자릿수도 비슷해 검산하지 않으면 알 수 없다.
SPREAD_DISCOUNT = Decimal("0.9")

_ONE = Decimal("1")
#: 환율 자릿수. 001이 쓰는 정밀도와 같다.
_RATE_PLACES = Decimal("0.000001")


def per_unit(rate: Decimal, quote_unit: int) -> Decimal:
    """고시 단위로 나눈 **1단위당** 값 (006 FR-042, research R6-9).

    외환 DB의 엔화는 100엔당 값이다. 단위를 버리면 원금 1,000,000원이 약 110,900엔이
    아니라 1,109엔으로 환전된다(100배) — 주식을 한 주도 사지 못하고 수익률이 0%에
    가깝게 나와, 그 종목이 움직이지 않았다고 읽힌다.

    단위는 행마다 있다. 통화별 상수로 두면 출처가 단위를 바꿀 때 과거 행이 틀린다.
    100은 10의 거듭제곱이라 `Decimal` 나눗셈이 정확하다.
    """
    if quote_unit <= 0:
        raise ValueError(f"고시 단위는 양수여야 합니다: {quote_unit}")
    return (rate / Decimal(quote_unit)).quantize(_RATE_PLACES)


def exchange_rate(
    base_rate: Decimal, cash_buy_spread: Decimal, *, discount: Decimal = SPREAD_DISCOUNT
) -> Decimal:
    """**초기 환전**에 쓰는 환율 (FR-019, FR-020).

    현금 살 때 환율에 수수료 우대를 적용한다. 현금을 **사는** 것이므로 가산이다 —
    차감하면 방향이 뒤집힌 것이고, 사용자가 실제로 내는 돈보다 적게 계산된다.
    """
    applied = cash_buy_spread * (_ONE - discount)
    return (base_rate * (_ONE + applied)).quantize(_RATE_PLACES)


def to_foreign(amount: Decimal, rate: Decimal, currency: str) -> Decimal:
    """원금을 종목 통화로 바꾼다. 통화의 자릿수로 맞춘다."""
    if rate <= 0:
        return Decimal("0")
    return quantize_money(amount / rate, currency)


def to_principal(amount: Decimal, base_rate: Decimal, currency: str) -> Decimal:
    """**평가 환산** — 종목 통화 금액을 `currency`로 (FR-041b). 006부터는 KRW 평가에 쓴다(FR-068).

    매매기준율을 쓴다. 환전이 아니라 값어치를 재는 것이므로 매수 스프레드를 얹으면
    잔고가 실제보다 크게 나온다 (SC-021).
    """
    return quantize_money(amount * base_rate, currency)


@dataclass(frozen=True, slots=True)
class RateLookup:
    """날짜별 매매기준율. 조회만 하는 자료구조라 순수 함수에 넘길 수 있다."""

    by_date: dict[dt.date, Decimal]


def resolve_rate(
    lookup: RateLookup, on: dt.date
) -> tuple[Decimal, dt.date] | None:
    """그 날짜에 쓸 환율과 **실제로 쓴 날짜** (FR-041c).

    고시가 없으면 **가장 가까운 이전 고시일**의 값을 쓴다. 주식 거래일과 환율 고시일은
    일치하지 않는다 — 미국 증시가 열린 날이 한국 공휴일일 수 있다.

    **이후 고시일을 쓰지 않는다.** 미래 값으로 과거를 평가하면 그날 몰랐던 정보가 섞인다.

    값을 만들어내는 것이 아니라 **어느 날짜의 값을 썼는지 밝히고 쓰는 것**이라는 점이
    헌법 원칙 V와의 경계다. 밝히지 않으면 곧바로 위반이므로 날짜를 함께 돌려준다.

    이전 고시일이 하나도 없으면 `None`이다 — 환산할 수 없다는 사실이 드러나야 한다.
    """
    exact = lookup.by_date.get(on)
    if exact is not None:
        return exact, on

    earlier = [d for d in lookup.by_date if d < on]
    if not earlier:
        return None
    used = max(earlier)
    return lookup.by_date[used], used
