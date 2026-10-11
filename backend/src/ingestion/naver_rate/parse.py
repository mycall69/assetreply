"""기준금리 응답 읽기 (014 반복 2026-10-11d T207) — FR-043, research R14-32, data-model 17.

순수 함수다(네트워크·DB 없음). 출처의 칸
이름(`localTradedAt`·`closePrice`·`isRelease`·`nationType`·`nextReleaseKoreaDate`)은 이 파일
밖으로 나가지 않는다.

- **결정일은 출처 시각(한국 시각)의 한국 날짜**다(spec FR-040). 옛 행의 시각은 자리 표시
  `23:59:59`라 날짜만 안다 — 발표 시각을 비운다
  (시각을 만들지 않는다)
- **발표 전 행**(`isRelease:false` · 금리 `"-"`)은 결정이 아니라 다음 결정 예정이다
- **같은 날 두 행**(실측 여섯 날 — 모두 같은 값): 금리가 같으면 한 행이고 발표 시각은 실제 시각
  행의 것이다(자리 표시보다 먼저). 다르면
  그 날을 결정으로 내지 않고 충돌로 낸다 — 하나를 고르지 않는다
- 결정 행의 금리를 읽을 수 없거나 본문이 배열이 아니면 `PolicyRateInvalidBody`다
"""

from __future__ import annotations

import datetime as dt
import json
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Final
from zoneinfo import ZoneInfo

from src.ingestion.naver_rate.banks import bank_of
from src.ingestion.naver_rate.errors import PolicyRateInvalidBody

_KST: Final = ZoneInfo("Asia/Seoul")
#: 출처가 시각을 모를 때 두는 자리 표시(한국 시각) — 날짜만 안다(실측 2016~ 행).
_PLACEHOLDER: Final = dt.time(23, 59, 59)
#: 발표 전 행의 금리 글자.
_UNRELEASED: Final = "-"


@dataclass(frozen=True, slots=True)
class SourceDecision:
    """출처의 결정 하나(동결 포함)."""

    decided_on: dt.date
    #: UTC. 출처가 자리 표시 시각을 주면 `None`
    announced_at: dt.datetime | None
    rate: Decimal


@dataclass(frozen=True, slots=True)
class Conflict:
    """같은 결정일에 다른 금리 둘 이상 — 고르지 않는다(출처 차례의 금리들)."""

    decided_on: dt.date
    rates: tuple[Decimal, ...]


@dataclass(frozen=True, slots=True)
class CalendarPage:
    """결정 이력 한 쪽."""

    #: 최신부터, 같은 날은 한 번
    decisions: list[SourceDecision]
    conflicts: list[Conflict]
    #: 발표 전 행의 결정일(한국 날짜) — 다음 결정 예정. 없으면 `None`
    upcoming: dt.date | None
    #: 응답의 행 수(발표 전 행 포함) — 쪽 크기보다 적으면 마지막 쪽이다
    row_count: int


@dataclass(frozen=True, slots=True)
class ListEntry:
    """목록의 은행 한 줄."""

    #: 최근 결정일(한국 날짜)
    decided_on: dt.date | None
    rate: Decimal | None
    #: 다음 결정일(한국 날짜)
    next_meeting_on: dt.date | None


def _rows(raw: str) -> list[dict[str, object]]:
    try:
        body = json.loads(raw)
    except ValueError as exc:
        raise PolicyRateInvalidBody("기준금리 출처 응답이 JSON이 아닙니다.") from exc
    if not isinstance(body, list) or not all(isinstance(row, dict) for row in body):
        raise PolicyRateInvalidBody("기준금리 출처 응답이 행의 배열이 아닙니다.")
    return body


def _moment(value: object) -> tuple[dt.date, dt.datetime | None]:
    """출처 시각 → (한국 날짜, UTC 발표 시각 — 자리 표시면 `None`)."""
    if not isinstance(value, str):
        raise PolicyRateInvalidBody("기준금리 출처 행에 결정 시각이 없습니다.")
    try:
        moment = dt.datetime.fromisoformat(value.strip())
    except ValueError as exc:
        raise PolicyRateInvalidBody("기준금리 출처 행의 결정 시각을 읽을 수 없습니다.") from exc
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=_KST)
    local = moment.astimezone(_KST)
    announced = None if local.time() == _PLACEHOLDER else local.astimezone(dt.UTC)
    return local.date(), announced


def _released(row: dict[str, object]) -> bool:
    return row.get("isRelease") is not False and row.get("closePrice") != _UNRELEASED


def _rate(value: object) -> Decimal:
    if not isinstance(value, str):
        raise PolicyRateInvalidBody("기준금리 출처 행에 금리가 없습니다.")
    try:
        rate = Decimal(value.strip())
    except InvalidOperation as exc:
        raise PolicyRateInvalidBody("기준금리 출처 행의 금리를 읽을 수 없습니다.") from exc
    if not rate.is_finite():
        raise PolicyRateInvalidBody("기준금리 출처 행의 금리를 읽을 수 없습니다.")
    return rate


def parse_calendars(raw: str) -> CalendarPage:
    """결정 이력 한 쪽 → 결정(최신부터·같은 날 한 번)·충돌·다음 결정 예정."""
    rows = _rows(raw)
    upcoming: dt.date | None = None
    grouped: dict[dt.date, list[tuple[dt.datetime | None, Decimal]]] = {}
    for row in rows:
        day, announced = _moment(row.get("localTradedAt"))
        if not _released(row):
            upcoming = day if upcoming is None else min(upcoming, day)
            continue
        grouped.setdefault(day, []).append((announced, _rate(row.get("closePrice"))))
    decisions: list[SourceDecision] = []
    conflicts: list[Conflict] = []
    for day, items in grouped.items():
        rates = tuple(rate for _, rate in items)
        if len(set(rates)) > 1:
            conflicts.append(Conflict(day, rates))
            continue
        announced = next((at for at, _ in items if at is not None), None)
        decisions.append(SourceDecision(day, announced, rates[0]))
    decisions.sort(key=lambda decision: decision.decided_on, reverse=True)
    return CalendarPage(decisions, conflicts, upcoming, len(rows))


def _korea_day(value: object) -> dt.date | None:
    """`"20261029"` → 날짜. 읽을 수 없으면 `None`(다음 결정일은 표시용이다)."""
    if not isinstance(value, str):
        return None
    try:
        return dt.datetime.strptime(value.strip(), "%Y%m%d").date()
    except ValueError:
        return None


def parse_list(raw: str) -> dict[str, ListEntry]:
    """목록 → 은행 id마다 한 줄. 다섯 밖의 은행은 읽지 않는다."""
    entries: dict[str, ListEntry] = {}
    for row in _rows(raw):
        nation = row.get("nationType")
        bank = bank_of(nation) if isinstance(nation, str) else None
        if bank is None:
            continue
        day, _ = _moment(row.get("localTradedAt"))
        rate = _rate(row.get("closePrice")) if _released(row) else None
        entries[bank] = ListEntry(day, rate, _korea_day(row.get("nextReleaseKoreaDate")))
    return entries
