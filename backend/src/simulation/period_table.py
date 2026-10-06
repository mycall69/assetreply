"""기간 표 — 일·주·월 단위의 대표일·표시·사건 행·결측 구간 행과 쪽 (012 T027) — FR-004, FR-004a,
FR-004b, FR-005, FR-009,
research R12-2·R12-3·R12-5~R12-7, data-model 3.

**날짜만 고른다.** 값은 계산 모듈의 하루하루 상태 그대로이고, 여기서는 어느 날의 상태를 어느 행으로
보일지만 정한다 — 값을 만들거나 옮기지 않는다
(헌법 원칙 V). 행의 종류와 무관한 일반 함수다. 주식·가상자산 × 일시금·적립식 네 표가 같은 규칙을
쓴다(서비스가 자기 행 모양으로 바꾼다).

외환의 `api/services/period_rows.py`를 쓰지 않는 이유(research R12-2):
- 그 모듈은 `FxRate`·저장소를 불러와 계산 계층이 API 계층을 부르게 된다
- 그 `shifted_from`은 주말 고시가 없다고 전제한다 — 주말 일봉이 있는 가상자산에는 틀리다(명확화 2)
- 그 `is_ongoing`의 기준은 오늘이다 — 이 표의 기준은 계산 끝이다(FR-004a)

규칙:
- 주는 월~일, 월은 1일~말일이다. 기준일은 그 주의 금요일·그 달의 말일이다
- 주 대표일 = 그 주 ∩ 계산 기간에서 **금요일 이하의 마지막 시세일**, 없으면 그 주 ∩ 계산 기간의
  마지막 시세일(토·일 — 가상자산). 월 대표일 = 그 달
  ∩ 계산 기간의 마지막 시세일. 주식에는 주말 일봉이 없어 외환 규칙(그 구간의 마지막 고시일)과 같은
  날이다
- 대표일 ≠ 기준일이면 `shifted_from` = 기준일. 구간 끝 > 계산 끝이면 진행 중. 일 단위는 둘 다 없다
- 사건이 있는 날은 단위와 관계없이 사건 묶음 하나다. 대표일에 사건이 있으면 그날의 기간 행은 없고
  표시는 사건 묶음이 진다 — 서비스가 그날의 마지막
  사건 행(그날 상태를 보이는 행)에 붙인다
- 결측 구간(가상자산 출처 결측)은 일 단위에만 들어간다
"""

from __future__ import annotations

import calendar
import datetime as dt
from collections.abc import Collection, Sequence
from dataclasses import dataclass
from typing import Final, Literal, get_args

PeriodUnit = Literal["daily", "weekly", "monthly"]

#: 질의 검증용. 알 수 없는 값을 조용히 `daily`로 떨어뜨리지 않는다.
PERIOD_UNITS: Final[tuple[str, ...]] = get_args(PeriodUnit)

EntryKind = Literal["events", "period", "missing"]

_FRIDAY: Final = 4  # `dt.date.weekday()`는 월요일이 0이다
_DAYS_PER_WEEK: Final = 7


@dataclass(frozen=True, slots=True)
class TableEntry:
    """표의 한 날짜 — 그날의 사건 묶음(`events`), 기간 행(`period`), 결측 구간(`missing`) 가운데
    하나.

    `date`는 행의 날짜이자 쪽의 커서다. 결측 구간은 그 구간의 처음이고 `date_to`가 끝이다. 같은 날의
    사건 행을 묶음 하나로 두므로 쪽이 그날의 행을
    가를 수 없다(R12-7).
    """

    kind: EntryKind
    date: dt.date
    #: 옮겨졌으면 원래 기준일(금요일·말일). 없으면 옮겨지지 않았다.
    shifted_from: dt.date | None = None
    #: 구간이 아직 끝나지 않았다(구간 끝 > 계산 끝).
    is_ongoing: bool = False
    date_to: dt.date | None = None


def period_bounds(day: dt.date, unit: PeriodUnit) -> tuple[dt.date, dt.date]:
    """`day`가 속한 구간의 처음과 끝. 일 단위는 그날 하루다."""
    if unit == "daily":
        return day, day
    if unit == "weekly":
        start = day - dt.timedelta(days=day.weekday())
        return start, start + dt.timedelta(days=_DAYS_PER_WEEK - 1)
    last = calendar.monthrange(day.year, day.month)[1]
    return day.replace(day=1), day.replace(day=last)


def anchor_of(day: dt.date, unit: PeriodUnit) -> dt.date:
    """`day`가 속한 구간의 기준일 — 주는 그 주의 금요일, 월은 그 달의 말일, 일은 그날."""
    start, end = period_bounds(day, unit)
    if unit == "weekly":
        return start + dt.timedelta(days=_FRIDAY)
    return end


def is_ongoing(period_to: dt.date, end: dt.date, unit: PeriodUnit) -> bool:
    """구간이 아직 끝나지 않았는가 — 구간의 끝이 계산 끝 뒤다(FR-004a).

    **일 단위는 늘 거짓이다.** 하루는 그 날짜로 끝난다(004와 같다). 시세가 끊긴 종목의 마지막 구간은
    계산 끝 앞에서 끝났으면 끝난 구간이다 — 끊김은
    표 위 경고가 알린다.
    """
    return unit != "daily" and period_to > end


def _representative(group: Sequence[dt.date], unit: PeriodUnit) -> dt.date:
    """구간의 대표일. `group`은 그 구간 ∩ 계산 기간의 시세일(오름차순)이다."""
    if unit == "weekly":
        friday = anchor_of(group[0], unit)
        upto = [day for day in group if day <= friday]
        return upto[-1] if upto else group[-1]
    return group[-1]


def build_table(
    quote_days: Sequence[dt.date],
    event_days: Collection[dt.date],
    unit: PeriodUnit,
    end: dt.date,
    missing: Sequence[tuple[dt.date, dt.date]] = (),
) -> list[TableEntry]:
    """표의 날짜들을 최신순으로.

    `quote_days`는 계산 기간(첫 평가일 ~ 기준일) 안의 시세일이고 `event_days`는 사건이 있는
    날이다(시세일의 부분집합). `end`는 계산 끝 — 진행 중 판정의
    기준이다. `missing`은 가상자산 일 단위의 결측 구간(처음, 끝)이고 다른 단위에서는 쓰지 않는다.
    """
    days = sorted(set(quote_days))
    events = set(event_days)
    entries: list[TableEntry] = []

    if unit == "daily":
        for day in days:
            entries.append(TableEntry("events" if day in events else "period", day))
        entries += [TableEntry("missing", start, date_to=stop) for start, stop in missing]
    else:
        groups: dict[tuple[dt.date, dt.date], list[dt.date]] = {}
        for day in days:
            groups.setdefault(period_bounds(day, unit), []).append(day)
        marked: dict[dt.date, TableEntry] = {}
        for (_, period_to), group in groups.items():
            rep = _representative(group, unit)
            anchor = anchor_of(rep, unit)
            marked[rep] = TableEntry(
                "events" if rep in events else "period", rep,
                shifted_from=None if rep == anchor else anchor,
                is_ongoing=is_ongoing(period_to, end, unit))
        entries += marked.values()
        entries += [TableEntry("events", day) for day in sorted(events) if day not in marked]

    entries.sort(key=lambda e: e.date, reverse=True)
    return entries


def page(entries: Sequence[TableEntry], before: dt.date | None,
         limit: int) -> tuple[list[TableEntry], bool]:
    """커서 쪽(005 FR-029와 같다 — 오프셋을 쓰지 않는다). `date < before`인 항목을 최신순으로
    `limit`개.

    항목이 날짜 하나라 같은 날의 사건 행이 두 쪽으로 갈리지 않는다 — 다음 쪽은 `before = 마지막
    날짜`라, 그날의 남은 행을 가르면 건너뛴다. 사건이 여럿인
    날이 있으면 행 수는 `limit`보다 조금 많을 수 있다.
    """
    candidates = [e for e in entries if before is None or e.date < before]
    return candidates[:limit], len(candidates) > limit
