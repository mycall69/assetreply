"""기준금리 결정·원본·은행 상태 저장소 (014 반복 2026-10-11d T207) — FR-043, SC-026, data-model 17.

- 결정은 (은행, 결정일) 유일이다. **없는 날만 넣는다** — 있는 날의 금리가 다르면 덮지 않고 개정을
  돌려준다(수집 로그에 남긴다 —
  008 금리 개정과 같은 뜻, plan "해석이 필요한 선택"). 그래서 방언 upsert가 아니라 "있는 날 읽기 →
  새 날만 넣기"다
- 원본은 정규화와 따로, 본문 그대로다
- 은행 상태의 실패는 성공이 지우지 않는다 — 화면이 시각을 견줘 "성공 뒤의 실패"만 보인다(지표
  커버리지와 같다)
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Final, Protocol

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import PolicyRateBank, PolicyRateDecision, PolicyRateRaw, PolicyRateRawKind
from src.simulation.policy_rate import Decision

#: 행에 남기는 출처 이름 — 어느 어댑터가 넣었는지 행에서 알 수 있어야 한다.
SOURCE: Final = "naver:standard_interest"
#: 실패 문구 열의 길이(data-model 17.3).
_MESSAGE_MAX: Final = 255


class DecisionLike(Protocol):
    """넣을 결정 — 출처 어댑터의 값(`naver_rate.parse.SourceDecision`)이든 도메인 값이든 이 셋이면
    된다."""

    @property
    def decided_on(self) -> dt.date: ...

    @property
    def announced_at(self) -> dt.datetime | None: ...

    @property
    def rate(self) -> Decimal: ...


@dataclass(frozen=True, slots=True)
class Revision:
    """저장한 결정의 금리가 출처에서 달랐다 — 저장 값은 그대로다."""

    decided_on: dt.date
    stored_rate: Decimal
    source_rate: Decimal


@dataclass(frozen=True, slots=True)
class StoreResult:
    inserted: int
    revisions: list[Revision] = field(default_factory=list)


def _naive(instant: dt.datetime | None) -> dt.datetime | None:
    """저장용 — UTC, 시간대 없는 값(헌법 시계열 불변식)."""
    return None if instant is None else instant.astimezone(dt.UTC).replace(tzinfo=None)


async def store_raw(
    session: AsyncSession,
    kind: PolicyRateRawKind,
    *,
    bank: str | None,
    page: int | None,
    body: str,
    fetched_at: dt.datetime,
) -> None:
    session.add(PolicyRateRaw(
        kind=kind, bank=bank, page=page, body=body, source=SOURCE, fetched_at=fetched_at))
    await session.flush()


async def store_decisions(
    session: AsyncSession,
    bank: str,
    decisions: Sequence[DecisionLike],
    *,
    ingested_at: dt.datetime,
) -> StoreResult:
    """없는 날만 넣고, 있는 날의 금리가 다르면 개정을 돌려준다. 있는 행은 고치지 않는다."""
    if not decisions:
        return StoreResult(0)
    days = [d.decided_on for d in decisions]
    existing = {
        row.decided_on: row.rate
        for row in (
            await session.execute(
                select(PolicyRateDecision).where(
                    PolicyRateDecision.bank == bank,
                    PolicyRateDecision.decided_on >= min(days),
                    PolicyRateDecision.decided_on <= max(days),
                )
            )
        ).scalars()
    }
    inserted = 0
    revisions: list[Revision] = []
    for decision in decisions:
        stored = existing.get(decision.decided_on)
        if stored is None:
            session.add(PolicyRateDecision(
                bank=bank,
                decided_on=decision.decided_on,
                announced_at=_naive(decision.announced_at),
                rate=decision.rate,
                source=SOURCE,
                ingested_at=ingested_at,
            ))
            existing[decision.decided_on] = decision.rate
            inserted += 1
        elif stored != decision.rate:
            revisions.append(Revision(decision.decided_on, stored, decision.rate))
    await session.flush()
    return StoreResult(inserted, revisions)


async def decisions(session: AsyncSession, bank: str) -> list[PolicyRateDecision]:
    """그 은행의 결정 전부 — 최신부터."""
    rows = await session.execute(
        select(PolicyRateDecision)
        .where(PolicyRateDecision.bank == bank)
        .order_by(PolicyRateDecision.decided_on.desc())
    )
    return list(rows.scalars())


def as_decision(row: PolicyRateDecision) -> Decision:
    """저장 행 → 도메인 값(발표 시각은 UTC 시간대를 붙인다)."""
    at = None if row.announced_at is None else row.announced_at.replace(tzinfo=dt.UTC)
    return Decision(decided_on=row.decided_on, announced_at=at, rate=row.rate)


async def latest(session: AsyncSession, bank: str) -> Decision | None:
    row = (
        await session.execute(
            select(PolicyRateDecision)
            .where(PolicyRateDecision.bank == bank)
            .order_by(PolicyRateDecision.decided_on.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    return None if row is None else as_decision(row)


async def get_state(session: AsyncSession, bank: str) -> PolicyRateBank | None:
    return await session.get(PolicyRateBank, bank, populate_existing=True)


async def _ensure_state(session: AsyncSession, bank: str) -> PolicyRateBank:
    row = await get_state(session, bank)
    if row is None:
        row = PolicyRateBank(bank=bank, history_complete=False)
        session.add(row)
        await session.flush()
    return row


async def set_next_meeting(session: AsyncSession, bank: str, day: dt.date | None) -> None:
    row = await _ensure_state(session, bank)
    row.next_meeting_on = day
    await session.flush()


async def mark_history_complete(session: AsyncSession, bank: str) -> None:
    row = await _ensure_state(session, bank)
    row.history_complete = True
    await session.flush()


async def set_overlap_day(session: AsyncSession, bank: str, day: dt.date) -> None:
    row = await _ensure_state(session, bank)
    row.last_overlap_on = day
    await session.flush()


async def record_success(session: AsyncSession, bank: str, *, at: dt.datetime) -> None:
    row = await _ensure_state(session, bank)
    row.last_success_at = at
    await session.flush()


async def record_failure(
    session: AsyncSession, bank: str, *, at: dt.datetime, kind: str, message: str | None
) -> None:
    """마지막 실패를 남긴다. 성공 기록은 지우지 않는다 — 화면은 시각을 견줘 "성공 뒤의 실패"만
    보인다."""
    row = await _ensure_state(session, bank)
    row.last_failure_at = at
    row.failure_kind = kind
    row.failure_message = None if message is None else message[:_MESSAGE_MAX]
    await session.flush()
