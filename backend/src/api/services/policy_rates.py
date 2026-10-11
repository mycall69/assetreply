"""기준금리 칸·모달의 본문 (014 반복 2026-10-11d T208) — FR-040, FR-041, SC-025, contracts A14·A15.

**DB만 읽는다** — 출처를 부르지 않는다(수집은 워커 — FR-043). 금리·전회대비는 서버 `Decimal`의
글자다(원칙 VI) — 화면은 형식만 입힌다.

- 상태: 결정이 있으면 `ready`(마지막 성공보다 늦은 실패가 있으면 `failure`도 — "최근 갱신 실패"),
  결정이 없고 그런 실패도 없으면 `collecting`,
  결정이 없고 실패했으면 `failed`
- 다음 결정 예정일은 오늘(한국)보다 이르면 `null`이다. 결정일은 한국 날짜, 발표 시각은 UTC(모르면
  `null`)
- 모달의 머리 칸은 칸 행과 같은 함수다 — 두 화면의 같은 은행 값이 다르지 않다(FR-010과 같은 뜻)
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Sequence

from src.db.models import PolicyRateBank, PolicyRateDecision
from src.repository.policy_rate_repository import as_decision
from src.simulation.policy_rate import (
    Bank,
    DecisionView,
    rate_text,
    visible_next_meeting,
    with_changes,
)

Json = dict[str, object]

SOURCE = "네이버 증권"
SOURCE_URL = "https://stock.naver.com/market/marketindex/bondAndInterest/standardInterest"


def _iso(instant: dt.datetime | None) -> str | None:
    """저장 시각(UTC, 시간대 없음) → `…Z`."""
    if instant is None:
        return None
    return instant.replace(tzinfo=None, microsecond=0).isoformat() + "Z"


def _failure(state: PolicyRateBank | None) -> Json | None:
    """마지막 성공보다 늦은 실패만 — 성공한 뒤의 옛 실패는 보이지 않는다."""
    if state is None or state.last_failure_at is None:
        return None
    if state.last_success_at is not None and state.last_success_at >= state.last_failure_at:
        return None
    return {
        "kind": state.failure_kind or "connection",
        "message": state.failure_message or "",
        "at": _iso(state.last_failure_at),
    }


def _decision_json(view: DecisionView) -> Json:
    decision = view.decision
    announced = decision.announced_at
    return {
        "decidedOn": decision.decided_on.isoformat(),
        "announcedAt": None if announced is None else _iso(announced.astimezone(dt.UTC)),
        "rate": rate_text(decision.rate),
        "change": None if view.change is None else rate_text(view.change),
        "direction": view.direction,
    }


def _views(rows: Sequence[PolicyRateDecision]) -> list[DecisionView]:
    return with_changes([as_decision(row) for row in rows])


def _next_meeting(state: PolicyRateBank | None, today: dt.date) -> str | None:
    day = visible_next_meeting(None if state is None else state.next_meeting_on, today)
    return None if day is None else day.isoformat()


def row_json(
    bank: Bank, rows: Sequence[PolicyRateDecision], state: PolicyRateBank | None, *, today: dt.date
) -> Json:
    """칸 한 행(A14). `rows`는 그 은행의 결정 전부 — 최신부터."""
    failure = _failure(state)
    views = _views(rows[:2])
    latest = _decision_json(views[0]) if views else None
    if views:
        status = "ready"
    else:
        status = "failed" if failure is not None else "collecting"
    return {
        "bank": bank.id,
        "name": bank.name,
        "flag": bank.flag,
        "rateKind": bank.rate_kind,
        "rate": None if latest is None else latest["rate"],
        "change": None if latest is None else latest["change"],
        "direction": None if latest is None else latest["direction"],
        "decidedOn": None if latest is None else latest["decidedOn"],
        "announcedAt": None if latest is None else latest["announcedAt"],
        "nextMeetingOn": _next_meeting(state, today),
        "state": status,
        "failure": failure,
        "lastSuccessAt": None if state is None else _iso(state.last_success_at),
    }


def detail_json(
    bank: Bank, rows: Sequence[PolicyRateDecision], state: PolicyRateBank | None, *, today: dt.date
) -> Json:
    """모달(A15) — 칸 행 + 결정 전부(최신부터) + 저장된 기간."""
    return {
        **row_json(bank, rows, state, today=today),
        "firstDecidedOn": rows[-1].decided_on.isoformat() if rows else None,
        "lastDecidedOn": rows[0].decided_on.isoformat() if rows else None,
        "decisions": [_decision_json(view) for view in _views(rows)],
    }
