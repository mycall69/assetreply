"""외환 등락 계산 (014 반복 2026-10-10d T142) — FR-031, SC-016, research R14-24.

요약 칸(`/api/fx/latest`)의 전일 대비와 일자별 표(`/api/fx/daily`)의 등락이 이 함수 하나를 쓴다 —
같은 두 날이면 같은 글자다. 화면은 계산하지 않는다(헌법 원칙 VI).
"""
from __future__ import annotations

import datetime as dt
from decimal import Decimal

from src.simulation.fx_change import Quote, RateChange, rate_change

PREV_DAY = dt.date(2026, 10, 7)


def _prev(rate: str) -> Quote:
    return Quote(date=PREV_DAY, rate=Decimal(rate))


def test_오르면_up이고_차이와_비율을_낸다() -> None:
    change = rate_change(Decimal("1425.30"), _prev("1423.00"))
    assert change == RateChange(
        compared_to=PREV_DAY, absolute=Decimal("2.30"), percent=Decimal("0.16"),
        direction="up")


def test_내리면_down이고_부호가_음수다() -> None:
    change = rate_change(Decimal("1423.00"), _prev("1424.10"))
    assert change is not None
    assert (str(change.absolute), str(change.percent), change.direction) == (
        "-1.10", "-0.08", "down")


def test_같으면_flat이고_0이다() -> None:
    change = rate_change(Decimal("1300.00"), _prev("1300.00"))
    assert change is not None
    assert (str(change.absolute), str(change.percent), change.direction) == (
        "0.00", "0.00", "flat")


def test_등락폭은_저장_정밀도_그대로다() -> None:
    """반올림하지 않는다 — 요약 칸과 같은 규칙(001 FR-013)."""
    change = rate_change(Decimal("1356.123456"), _prev("1350.000001"))
    assert change is not None
    assert change.absolute == Decimal("6.123455")


def test_등락율은_소수_둘째_자리다_반올림은_짝수_쪽() -> None:
    """`Decimal.quantize`의 기본 반올림 — `/api/fx/latest`가 쓰던 것과 같다(응답 불변)."""
    tie_down = rate_change(Decimal("1001.25"), _prev("1000.00"))  # 0.125 → 0.12
    tie_up = rate_change(Decimal("1001.35"), _prev("1000.00"))  # 0.135 → 0.14
    assert tie_down is not None and tie_up is not None
    assert (str(tie_down.percent), str(tie_up.percent)) == ("0.12", "0.14")


def test_비교할_행이_없으면_없음이다() -> None:
    """저장된 첫 고시 — 0으로 메우지 않는다(헌법 원칙 V)."""
    assert rate_change(Decimal("1186.90"), None) is None


def test_직전_값이_0_이하면_등락율만_없다() -> None:
    """나눌 수 없는 비율을 지어내지 않는다. 등락폭과 방향은 그대로다."""
    zero = rate_change(Decimal("1.00"), _prev("0"))
    negative = rate_change(Decimal("1.00"), _prev("-1.00"))
    assert zero == RateChange(
        compared_to=PREV_DAY, absolute=Decimal("1.00"), percent=None, direction="up")
    assert negative is not None
    assert (negative.absolute, negative.percent) == (Decimal("2.00"), None)
