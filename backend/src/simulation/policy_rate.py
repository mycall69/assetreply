"""기준금리 — 은행 표와 순수 규칙 (014 반복 2026-10-11d T208) — FR-040, FR-041, data-model 17.

DB·HTTP에 의존하지 않는다(헌법 원칙 IV). 은행 표는 화면에 보이는 이름·금리 종류·국기·차례의 **한
곳**이다 — 출처의 이름을 쓰지 않는다.
출처 국가 코드는 모른다(`ingestion/naver_rate/banks.py`).

- 전회대비 = 그 결정 금리 − 바로 앞(더 옛) 결정 금리(`Decimal`). 저장된 첫 결정은 없음 — 0으로
  메우지 않는다(원칙 V)
- 다음 결정 예정일은 오늘(한국)보다 이르면 없음이다 — 출처가 지난 날짜를 준다(아르헨티나 실측
  `20250201`)
- 글자는 소수 둘째 자리 이상이다 — 저장 열(`DECIMAL(8,4)`)의 끝 0은 빼고, 둘째 자리보다 짧으면 둘째
  자리까지 채운다
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Final, Literal

Direction = Literal["up", "down", "flat"]
_CENT: Final = Decimal("0.01")


@dataclass(frozen=True, slots=True)
class Bank:
    id: str
    #: 화면 이름(스크린샷 — 네이버 증권과 같은 글자)
    name: str
    #: 금리 종류 — 출처 계열의 뜻(R14-32 실측 대조)
    rate_kind: str
    flag: str


#: 칸의 차례(스크린샷 — 미국·한국·유럽·영국·일본).
BANKS: Final[tuple[Bank, ...]] = (
    Bank("fed", "미국연방준비은행", "연방기금금리 목표 범위 상단", "🇺🇸"),
    Bank("bok", "한국은행", "기준금리", "🇰🇷"),
    Bank("ecb", "유럽중앙은행", "주요 재융자 금리", "🇪🇺"),
    Bank("boe", "영국은행", "Bank Rate", "🇬🇧"),
    Bank("boj", "일본은행", "단기 정책금리", "🇯🇵"),
)

_BY_ID: Final[dict[str, Bank]] = {bank.id: bank for bank in BANKS}


def get_bank(bank_id: str) -> Bank | None:
    return _BY_ID.get(bank_id)


@dataclass(frozen=True, slots=True)
class Decision:
    decided_on: dt.date
    #: UTC — 모르면 `None`
    announced_at: dt.datetime | None
    rate: Decimal


@dataclass(frozen=True, slots=True)
class DecisionView:
    decision: Decision
    #: 앞 결정과의 차이. 저장된 첫 결정이면 `None`
    change: Decimal | None
    direction: Direction | None


def direction_of(change: Decimal) -> Direction:
    if change > 0:
        return "up"
    if change < 0:
        return "down"
    return "flat"


def with_changes(decisions: Sequence[Decision]) -> list[DecisionView]:
    """최신부터의 결정마다 전회대비. 받은 차례(최신부터)를 그대로 둔다."""
    views: list[DecisionView] = []
    for index, decision in enumerate(decisions):
        if index + 1 < len(decisions):
            change = decision.rate - decisions[index + 1].rate
            views.append(DecisionView(decision, change, direction_of(change)))
        else:
            views.append(DecisionView(decision, None, None))
    return views


def rate_text(value: Decimal) -> str:
    """소수 둘째 자리 이상의 글자 — `4.0000` → `4.00`, `4.1250` → `4.125`, `-0.10`."""
    normalized = value.normalize()
    exponent = normalized.as_tuple().exponent
    if isinstance(exponent, int) and exponent >= -2:
        normalized = value.quantize(_CENT)
    return format(normalized, "f")


def visible_next_meeting(next_on: dt.date | None, today: dt.date) -> dt.date | None:
    """다음 결정 예정일 — 오늘(한국)보다 이르면 없음. 오늘이면 그대로(결정 날 발표 전)."""
    if next_on is None or next_on < today:
        return None
    return next_on
