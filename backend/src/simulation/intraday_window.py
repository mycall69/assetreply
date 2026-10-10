"""장중 그래프의 처음 보이는 범위 (014 반복 2026-10-10c T133) — FR-011, FR-028, research R14-22.

**순수 함수 모듈이다**(헌법 원칙 IV). 받은 장중 점(UTC 시각)을 그 시장의 거래일로 가르고, 마지막
`sessions`개 세션의 처음 점 ~ 끝 점을 낸다 — 일은 마지막 세션, 주는 최근 5세션이다. 왼쪽으로 끌면 그
앞의 받은 점이 이어서 보인다.

- 거래일은 `market_session.trading_date`와 같다 — 정규 시장은 현지 날짜, 환율은 런던 날짜(출처
  일봉의 하루 경계), 선물(CME)은 뉴욕 18:00 뒤가 다음 거래일. 일봉 표의 날짜와 같은 규칙이라 세션이
  일봉 하루와 맞는다
- 세션은 **점이 있는 날**뿐이다 — 휴장·출처가 비운 날을 꾸미지 않는다(원칙 V). 세션이 모자라면 받은
  점 전부다
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Sequence

from src.simulation.market_session import trading_date


def session_window(
    times: Sequence[dt.datetime], market_key: str, sessions: int
) -> tuple[dt.datetime, dt.datetime] | None:
    """마지막 `sessions`개 세션의 (처음, 끝). 점이 없으면 `None`. `times`는 시각 차례다."""
    if not times:
        return None
    days = sorted({trading_date(market_key, at) for at in times})
    keep = set(days[-sessions:])
    chosen = [at for at in times if trading_date(market_key, at) in keep]
    return chosen[0], chosen[-1]
