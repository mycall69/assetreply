"""시세 단절 판정 (버그 stock-holiday-stale-warning) — 005 FR-014a·FR-014b, SC-026·SC-027.

계산의 마지막 날(`as_of`)이 요청한 계산 끝(`end`, 기본 어제)보다 이를 때 **휴장·주말**과
**시세 단절**(상장폐지·거래정지)을 가른다.

- 그 시장의 다른 종목이 `as_of` 뒤에 거래했으면 이 종목만 끊겼다 — 단절이다
- 그 시장 누구도 `as_of` 뒤에 거래하지 않았으면(시장 마지막 거래일 = `as_of`) 데이터만으로는
  휴장과 단절을 가를 수 없다. (`as_of`, `end`]의 평일 수가 허용치(거래소 연휴를 덮는 값) 이하면
  휴장이다
- 2026-10-05(월)는 개천절(10-03, 토)의 대체공휴일이었다 — 10-02(금)까지의 결과는 최종이다(버그
  재현일 2026-10-06)

**순수 함수다** — DB 없이 돈다(헌법 원칙 IV).
"""

from __future__ import annotations

import datetime as dt

import pytest

from src.simulation.quote_finality import is_final

D = dt.date.fromisoformat
TOLERANCE = 7


def test_계산_끝까지_시세가_있으면_최종이다() -> None:
    assert is_final(D("2026-10-02"), D("2026-10-02"), market_last=D("2026-10-02"),
                    tolerance_weekdays=TOLERANCE)


def test_계산_끝이_대체공휴일이면_최종이다() -> None:
    """버그 재현 — 10-05(월) 휴장, 그 시장의 마지막 거래일도 10-02다."""
    assert is_final(D("2026-10-02"), D("2026-10-05"), market_last=D("2026-10-02"),
                    tolerance_weekdays=TOLERANCE)


def test_계산_끝이_주말이면_최종이다() -> None:
    assert is_final(D("2026-10-02"), D("2026-10-04"), market_last=D("2026-10-02"),
                    tolerance_weekdays=TOLERANCE)


def test_같은_시장의_다른_종목이_그_뒤에_거래했으면_단절이다() -> None:
    assert not is_final(D("2026-10-02"), D("2026-10-05"), market_last=D("2026-10-05"),
                        tolerance_weekdays=TOLERANCE)


def test_비교할_거래가_없고_평일이_오래_비면_단절이다() -> None:
    """`test_delisted.py`의 시나리오 — 09-02 뒤로 11-30까지 평일 60여 일."""
    assert not is_final(D("2021-09-02"), D("2021-11-30"), market_last=D("2021-09-02"),
                        tolerance_weekdays=TOLERANCE)


def test_시장_데이터가_없으면_평일_허용치로_가른다() -> None:
    assert is_final(D("2026-10-02"), D("2026-10-05"), market_last=None,
                    tolerance_weekdays=TOLERANCE)
    assert not is_final(D("2021-09-02"), D("2021-11-30"), market_last=None,
                        tolerance_weekdays=TOLERANCE)


@pytest.mark.parametrize(("end", "expected"), [
    # 10-02(금) 뒤의 평일 — 10-05~10-09가 5일, 10-12~10-13까지 7일, 10-14까지 8일
    ("2026-10-13", True),
    ("2026-10-14", False),
])
def test_허용치는_빈_평일_수다(end: str, expected: bool) -> None:
    assert is_final(D("2026-10-02"), D(end), market_last=D("2026-10-02"),
                    tolerance_weekdays=TOLERANCE) is expected


def test_허용치가_0이면_빈_평일이_하나만_있어도_단절이다() -> None:
    assert not is_final(D("2026-10-02"), D("2026-10-05"), market_last=D("2026-10-02"),
                        tolerance_weekdays=0)
    assert is_final(D("2026-10-02"), D("2026-10-04"), market_last=D("2026-10-02"),
                    tolerance_weekdays=0)
