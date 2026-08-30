"""파생 환율 산출 (T066).

**순수 함수 모듈이다.** `repository`·`api`·`db`를 임포트하지 않으며 DB와 HTTP 없이 단독
테스트가 가능해야 한다 (헌법 원칙 IV).

헌법 원칙 VI: 전 계산에 `Decimal`을 쓰고 `float`을 쓰지 않는다. 반올림은 **표시 직전
한 번만** 수행한다 — 중간에 반올림하면 계산 순서에 따라 결과가 달라져 재현성이 깨진다.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

# 표시 자릿수 — research R7이 고정한 값
DISPLAY_QUANTUM = Decimal("0.01")

_ONE = Decimal("1")


@dataclass(frozen=True, slots=True)
class SpreadSet:
    """통화 하나의 4종 스프레드 비율. 0 이상 1 미만."""

    cash_buy: Decimal
    cash_sell: Decimal
    remit_send: Decimal
    remit_receive: Decimal


@dataclass(frozen=True, slots=True)
class DerivedRates:
    """스프레드를 적용한 4종 환율. 소수 2자리로 반올림된 값이다."""

    cash_buy: Decimal
    cash_sell: Decimal
    remit_send: Decimal
    remit_receive: Decimal


def _round(value: Decimal) -> Decimal:
    return value.quantize(DISPLAY_QUANTUM, rounding=ROUND_HALF_UP)


def derive_rates(base_rate: Decimal, spread: SpreadSet) -> DerivedRates:
    """매매기준율에 스프레드를 적용한다 (FR-023).

    매입 방향(현금 살 때·송금 보낼 때)은 가산하고, 매도 방향(현금 팔 때·송금 받을 때)은
    차감한다. 사용자가 원화를 더 내는 쪽이 매입이다.
    """
    return DerivedRates(
        cash_buy=_round(base_rate * (_ONE + spread.cash_buy)),
        cash_sell=_round(base_rate * (_ONE - spread.cash_sell)),
        remit_send=_round(base_rate * (_ONE + spread.remit_send)),
        remit_receive=_round(base_rate * (_ONE - spread.remit_receive)),
    )


def is_valid_spread(value: Decimal) -> bool:
    """허용 범위는 0 이상 1 미만이다 (FR-025)."""
    return Decimal("0") <= value < _ONE
