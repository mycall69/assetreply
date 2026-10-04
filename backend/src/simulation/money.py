"""금액·수량 정밀도 (T006) — 005 data-model 4절, 헌법 원칙 VI.

**이 파일이 정밀도 규칙이 존재하는 유일한 곳이다.** 통화별 자릿수를 코드에 흩뿌리면
한 군데만 틀려도 **그 통화만 조용히 어긋난다** — 오류가 나지 않고 숫자도 그럴듯하다.

참조 구현(Google Apps Script)은 JavaScript `number`로 모든 금액을 계산하고
`Math.round`로 자릿수를 맞춘다. 그대로 옮기면 원칙 VI 위반이므로 전부 `Decimal`로
다룬다. 이것이 005에서 가장 크고 조용한 위험이다.

**순수 함수 모듈이다.** `repository`·`api`·`db`를 임포트하지 않는다 (헌법 원칙 IV).
"""

from __future__ import annotations

from decimal import ROUND_FLOOR, Decimal, localcontext

#: 통화별 소수 자릿수. 원화·엔화에 소수점 금액은 존재하지 않는다.
CURRENCY_SCALE: dict[str, int] = {
    "KRW": 0,
    "JPY": 0,
    "USD": 2,
    "EUR": 2,
}

#: 수익률·배당율의 소수 자릿수. 참조 구현과 같다.
RATE_SCALE = 6

#: 가상자산 수량의 소수 자릿수 (007 FR-026). 대개의 거래소 최소 단위(1e-8, 비트코인의 사토시)다.
QUANTITY_PLACES = 8
_QUANTUM = Decimal(1).scaleb(-QUANTITY_PLACES)
#: 소수 수량 계산의 정밀도. 1e-12달러 시가에 원금 수천만 원이면 수량이 정수부 18자리 + 소수 8자리라,
#: 기본 28자리 문맥에서 곱하면 반올림이 끼어들어 총액이 예수금을 넘을 수 있다.
CALC_PRECISION = 60

_ONE = Decimal("1")


def quantize_money(amount: Decimal, currency: str) -> Decimal:
    """금액을 통화의 자릿수로 맞춘다.

    알 수 없는 통화를 조용히 기본값으로 처리하지 않는다 — 그러면 그 통화만 다른
    자릿수로 계산되고, 값은 그럴듯해 보인다.
    """
    scale = CURRENCY_SCALE[currency]
    return amount.quantize(Decimal(1).scaleb(-scale))


def quantize_rate(rate: Decimal) -> Decimal:
    """비율을 소수 6자리로 맞춘다."""
    return rate.quantize(Decimal(1).scaleb(-RATE_SCALE))


def buy_quantity(cash: Decimal, price: Decimal, fee_rate: Decimal) -> int:
    """살 수 있는 최대 정수 수량 (FR-007, FR-007a).

    `수량 = ⌊예수금 ÷ (시가 × (1 + 수수료율))⌋`

    **수수료를 포함한 총액이 예수금을 넘지 않는다.** 수량을 시가로만 정하고 수수료를
    나중에 빼면, 남은 돈보다 수수료가 클 때 **예수금이 음수가 된다** — 음수 예수금은
    총자산을 줄여 수익률이 틀리는데 값이 작아 눈에 띄지 않는다 (SC-024).

    시가가 0 이하면 사지 않는다. 0으로 나누는 경로를 만들지 않는다.
    """
    if price <= 0 or cash <= 0:
        return 0
    unit_cost = price * (_ONE + fee_rate)
    return int((cash / unit_cost).to_integral_value(rounding=ROUND_FLOOR))


def spend_for(quantity: int, price: Decimal, fee_rate: Decimal) -> Decimal:
    """`quantity`주를 살 때 예수금에서 빠지는 총액. 수수료를 포함한다."""
    return Decimal(quantity) * price * (_ONE + fee_rate)


def apply_split(held: int, numerator: int, denominator: int) -> int:
    """분할·병합을 보유 주식 수에 반영한다 (FR-010).

    결과가 정수로 떨어지지 않으면 **버린다.** FR-007이 소수점 주식을 금지하므로
    1:10 병합에서 15주는 1주가 되고 5주 몫은 사라진다.

    올리거나 반올림하면 **없던 주식이 생긴다.** 어느 쪽이든 오류가 나지 않아 보유
    주식이 틀린 채로 수십 년이 복리로 벌어진다.
    """
    if held == 0 or denominator == 0:
        return held
    return (held * numerator) // denominator


def buy_fraction(cash: Decimal, price: Decimal, fee_rate: Decimal) -> Decimal:
    """살 수 있는 최대 **소수** 수량 (007 FR-026, research R7-7).

    `수량 = ⌊예수금 ÷ (시가 × (1 + 수수료율))⌋₈` — 소수 8자리에서 **버린다.** 올리거나 반올림하면
    수수료를 포함한 총액이 예수금을 넘어 예수금이 음수가 된다 — 값이 작아 눈에 띄지 않는다(SC-004).
    정수 수량(`buy_quantity`)과 따로 둔다 — 주식은 소수 주식을 사지 않는다(005 FR-007).

    시가·예수금이 0 이하면 사지 않는다. 0으로 나누는 경로를 만들지 않는다.
    """
    if price <= 0 or cash <= 0:
        return Decimal(0)
    with localcontext() as ctx:
        ctx.prec = CALC_PRECISION
        return (cash / (price * (_ONE + fee_rate))).quantize(_QUANTUM, rounding=ROUND_FLOOR)
