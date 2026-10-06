"""시세 단절 판정 (버그 stock-holiday-stale-warning) — 005 FR-014a·FR-014b, SC-026·SC-027.

계산의 마지막 날(`as_of` — 마지막 일봉)이 요청한 계산 끝(`end`, 기본 어제)보다 이르면 둘 중
하나다.

- **휴장·주말** — 시장이 쉬었다. 받을 시세가 빠진 것이 아니다. 결과는 최종이다
- **시세 단절**(상장폐지·거래정지) — 그 종목만 끊겼다. 끊긴 날짜를 알려야 한다(FR-014a).
  알리지 않으면 사용자는 마지막 행을 오늘까지의 결과로 읽는다

거래소 휴장일 표를 두지 않는다 — 날짜 상수와 매년 갱신 부담이 생긴다. 데이터로 가른다.

1. 같은 시장의 다른 종목이 `as_of` 뒤(계산 끝까지)에 거래했으면 단절이다
2. 그 시장 누구도 `as_of` 뒤에 거래하지 않았으면 데이터만으로는 휴장과 단절을 가를 수 없다
   - 비교할 종목이 없거나 그 종목들도 쉬었다
   - (`as_of`, `end`]의 **평일 수**가 허용치(거래소 연휴를 덮는 값, 설정) 이하면 휴장으로 본다
   - 허용치를 넘으면 단절이다

**순수 함수 모듈이다.** `repository`·`api`·`db`를 임포트하지 않는다(헌법 원칙 IV).
"""

from __future__ import annotations

import datetime as dt

_SATURDAY = 5


def blank_weekdays(as_of: dt.date, end: dt.date) -> int:
    """(`as_of`, `end`]의 평일(월~금) 수."""
    days = (end - as_of).days
    return sum(1 for n in range(1, days + 1)
               if (as_of + dt.timedelta(days=n)).weekday() < _SATURDAY)


def is_final(as_of: dt.date, end: dt.date, *, market_last: dt.date | None,
             tolerance_weekdays: int) -> bool:
    """계산 끝까지의 결과로 볼 수 있는가.

    `market_last`는 그 시장(이 종목 포함)의 계산 끝 이하 마지막 일봉 날짜다. 모르면 `None`이다.
    """
    if as_of >= end:
        return True
    if market_last is not None and market_last > as_of:
        return False
    return blank_weekdays(as_of, end) <= tolerance_weekdays
