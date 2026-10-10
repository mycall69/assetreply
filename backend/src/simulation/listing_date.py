"""상장일 고르기 — 순수 함수 (014 반복 2026-10-10f — FR-033, research R14-26).

주식은 **키움 국내 상장일**이 먼저다. 없으면 시세 출처(Yahoo)의 **첫 거래일** — 출처가 시세를 가진
첫 날이라 그보다 앞서 상장한 종목은 상장일보다 늦다(T158 — 도요타 1999-05-06). 코인은 출처가
상장일을 주지 않아 수집으로 알게 된 **첫 일봉**이다. 모르면 `None`이다 — 오늘·시작일·첫 저장
일봉으로 메우지 않는다(헌법 원칙 V). 기준(`basis`)을 함께 내야 화면이 출처의 날짜를 상장일로
오해하게 하지 않는다.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Literal

Basis = Literal["listing", "first_trade", "first_bar"]


@dataclass(frozen=True, slots=True)
class ListingDate:
    """상장일과 그 기준."""

    date: dt.date
    basis: Basis


def stock_listing_date(
    listed_on: dt.date | None, first_trade_date: dt.date | None,
) -> ListingDate | None:
    """주식 — 키움 상장일(`listing`) → Yahoo 첫 거래일(`first_trade`) → 없음."""
    if listed_on is not None:
        return ListingDate(listed_on, "listing")
    if first_trade_date is not None:
        return ListingDate(first_trade_date, "first_trade")
    return None


def coin_listing_date(first_bar: dt.date | None) -> ListingDate | None:
    """코인 — 수집으로 알게 된 첫 일봉(`first_bar`) → 없음."""
    return None if first_bar is None else ListingDate(first_bar, "first_bar")
