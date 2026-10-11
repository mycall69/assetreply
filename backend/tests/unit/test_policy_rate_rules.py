"""기준금리 규칙 — 순수 함수 (014 반복 2026-10-11d T204) — FR-040, FR-041, SC-025, data-model 17.

- 은행 다섯의 차례·이름·금리 종류·국기는 표 한 곳이다(출처 이름을 쓰지 않는다)
- 전회대비 = 그 결정 금리 − 바로 앞(더 옛) 결정 금리. 저장된 첫 결정은 없음(`None`) — 0으로 메우지
  않는다
- 금리·전회대비 글자는 소수 둘째 자리 이상(저장 열의 끝 0은 뺀다)
- 다음 결정 예정일은 오늘(한국)보다 이르면 없다 — 출처가 지난 날짜를 준다(아르헨티나 실측)
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

from src.simulation.policy_rate import (
    BANKS,
    Decision,
    get_bank,
    rate_text,
    visible_next_meeting,
    with_changes,
)

D = dt.date


def decision(day: dt.date, rate: str) -> Decision:
    return Decision(decided_on=day, announced_at=None, rate=Decimal(rate))


class Test은행표:
    def test_차례와_이름(self) -> None:
        assert [b.id for b in BANKS] == ["fed", "bok", "ecb", "boe", "boj"]
        assert [b.name for b in BANKS] == [
            "미국연방준비은행", "한국은행", "유럽중앙은행", "영국은행", "일본은행"]

    def test_금리_종류와_국기(self) -> None:
        kinds = {b.id: b.rate_kind for b in BANKS}
        assert kinds == {
            "fed": "연방기금금리 목표 범위 상단",
            "bok": "기준금리",
            "ecb": "주요 재융자 금리",
            "boe": "Bank Rate",
            "boj": "단기 정책금리",
        }
        assert [b.flag for b in BANKS] == ["🇺🇸", "🇰🇷", "🇪🇺", "🇬🇧", "🇯🇵"]

    def test_모르는_은행은_없음(self) -> None:
        assert get_bank("bok") is BANKS[1]
        assert get_bank("arg") is None


class Test전회대비:
    def test_최신부터_앞_결정과의_차이(self) -> None:
        views = with_changes([
            decision(D(2026, 8, 27), "3.00"),
            decision(D(2026, 7, 16), "2.75"),
            decision(D(2026, 5, 28), "2.75"),
            decision(D(2025, 5, 29), "3.00"),
        ])
        assert [(v.change, v.direction) for v in views] == [
            (Decimal("0.25"), "up"),
            (Decimal("0.00"), "flat"),
            (Decimal("-0.25"), "down"),
            (None, None),
        ]
        assert [v.decision.decided_on for v in views] == [
            D(2026, 8, 27), D(2026, 7, 16), D(2026, 5, 28), D(2025, 5, 29)]

    def test_마이너스_금리도_차이다(self) -> None:
        views = with_changes([decision(D(2024, 3, 19), "0.10"), decision(D(2024, 1, 23), "-0.10")])
        assert views[0].change == Decimal("0.20")
        assert views[0].direction == "up"

    def test_빈_이력(self) -> None:
        assert with_changes([]) == []


class Test글자:
    def test_소수_둘째_자리_이상(self) -> None:
        assert rate_text(Decimal("4.0000")) == "4.00"
        assert rate_text(Decimal("-0.1000")) == "-0.10"
        assert rate_text(Decimal("4.1250")) == "4.125"
        assert rate_text(Decimal("0.2500")) == "0.25"
        assert rate_text(Decimal("0")) == "0.00"
        assert rate_text(Decimal("-0.25")) == "-0.25"
        assert rate_text(Decimal("14")) == "14.00"


class Test다음_결정:
    def test_오늘_이후만_보인다(self) -> None:
        today = D(2026, 10, 11)
        assert visible_next_meeting(D(2026, 10, 22), today) == D(2026, 10, 22)
        assert visible_next_meeting(today, today) == today
        assert visible_next_meeting(D(2025, 2, 1), today) is None
        assert visible_next_meeting(None, today) is None
