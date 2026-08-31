"""스프레드 기본값의 **단일 출처** (T049).

FR-030: 스프레드를 설정하지 않은 통화에는 정해진 기본값이 적용된다.
FR-031: 사용자가 언제든 이 값으로 되돌릴 수 있다.

시드 리비전과 복원 로직이 **각각 값을 갖고 있으면 언젠가 어긋난다.** 한쪽만 고쳐도
아무 오류가 나지 않고, 사용자는 "기본값으로 되돌렸는데 처음과 다르다"를 겪는다.
그래서 여기 한 곳에만 둔다 (data-model 4절).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Final

FIELDS: Final = ("cash_buy", "cash_sell", "remit_send", "remit_receive")

#: 통화별 기본 스프레드. 001에서 정해 시드로 넣은 값과 같다.
DEFAULT_SPREADS: Final[dict[str, dict[str, Decimal]]] = {
    "USD": {"cash_buy": Decimal("0.001800"), "cash_sell": Decimal("0.001800"),
            "remit_send": Decimal("0.000500"), "remit_receive": Decimal("0.000500")},
    "JPY": {"cash_buy": Decimal("0.002000"), "cash_sell": Decimal("0.002000"),
            "remit_send": Decimal("0.000600"), "remit_receive": Decimal("0.000600")},
    "EUR": {"cash_buy": Decimal("0.002000"), "cash_sell": Decimal("0.002000"),
            "remit_send": Decimal("0.000600"), "remit_receive": Decimal("0.000600")},
}


def default_for(currency_code: str) -> dict[str, Decimal]:
    """통화의 기본 스프레드. 없는 통화는 오류다 — 조용히 0을 주면 안 된다."""
    try:
        return dict(DEFAULT_SPREADS[currency_code])
    except KeyError as exc:
        raise ValueError(f"{currency_code}의 기본 스프레드가 정의되지 않았습니다.") from exc


def is_default(values: dict[str, Decimal], currency_code: str) -> bool:
    """현재 값이 기본값과 같은지 (FR-033)."""
    base = DEFAULT_SPREADS.get(currency_code)
    if base is None:
        return False
    return all(values[f] == base[f] for f in FIELDS)
