"""일자별 표의 행 조립 (012 T029·T030) — FR-003~FR-005, FR-004b, FR-009, research R12-5·R12-7,
contracts/rest-api.md 1.

`simulation/period_table`이 고른 날짜(사건 묶음·기간 행·결측 구간)를 각 표의 행으로 바꾼다.
주식·가상자산 × 일시금·적립식 네 표가 같은 함수를 쓴다 —
표마다 따로 조립하면 한 표만 표시를 빠뜨리거나 쪽에서 같은 날의 행을 갈라도 오류가 나지 않는다.

- 사건 행은 서비스가 준 그대로다. 대표일의 표시(`shifted_from`·`is_ongoing`)는 **그날의 마지막 사건
  행**(그날 사건을 모두 처리한 뒤의 상태를 보이는
  행)이 진다 — 일시금은 같은 날의 행이 처리 차례로 놓여 마지막 행이, 적립식은 늦은 사건이 위라 첫
  행이 그 행이다
- 기간 행의 값은 하루하루 상태다. 변환(원화 평가)은 **잘라 낸 쪽의 행만** 한다 — 20년 일 단위(약
  5,000행)를 모두 바꾸지 않는다(R12-7)
- 결측 구간 행은 값이 없다 — 날짜 둘만 싣는다(원칙 V)
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass

from src.api.errors import InvalidQuery
from src.simulation.period_table import PERIOD_UNITS, PeriodUnit, build_table, page

Json = dict[str, object]


def parse_period(raw: str | None) -> PeriodUnit:
    """기간 단위를 읽는다. 없으면 일이다. **밖의 값을 기본값으로 바꾸지 않는다** — 일 단위로
    떨어뜨리면 사용자가 고른 것과 다른 표가 사유 없이 나온다."""
    if raw is None:
        return "daily"
    if raw == "weekly":
        return "weekly"
    if raw == "monthly":
        return "monthly"
    if raw == "daily":
        return "daily"
    raise InvalidQuery(f"기간 단위는 {' · '.join(PERIOD_UNITS)} 중 하나여야 합니다: {raw}")


@dataclass(frozen=True, slots=True)
class TableRow[V]:
    """표 한 행. `view`가 없으면 결측 구간 행이다(`date`~`date_to`)."""

    kind: str
    date: dt.date
    view: V | None = None
    shifted_from: dt.date | None = None
    is_ongoing: bool = False
    date_to: dt.date | None = None


@dataclass(frozen=True, slots=True)
class TablePage[V]:
    rows: list[TableRow[V]]
    has_more: bool
    #: 마지막 행의 커서 날짜(결측 구간 행은 그 구간의 처음). 쪽이 비면 없다.
    oldest: dt.date | None


def table_page[V](
    *,
    unit: PeriodUnit,
    end: dt.date,
    before: dt.date | None,
    limit: int,
    quote_days: Sequence[dt.date],
    events: Mapping[dt.date, Sequence[tuple[str, V]]],
    end_of_day_last: bool,
    day_state: Callable[[dt.date], V],
    missing: Sequence[tuple[dt.date, dt.date]] = (),
) -> TablePage[V]:
    """한 쪽의 행.

    `events`는 날짜 → 그날의 사건 행(보이는 차례, `(kind, view)`)이다. `end_of_day_last`가 참이면 그
    목록의 마지막이, 거짓이면 처음이 그날의 마지막
    사건 행이다. `day_state`는 기간 행의 값 — 그 날짜의 하루하루 상태를 행 모양으로 바꿔 준다.
    """
    entries = build_table(quote_days, events.keys(), unit, end, missing)
    chunk, more = page(entries, before, limit)
    rows: list[TableRow[V]] = []
    for entry in chunk:
        if entry.kind == "missing":
            rows.append(TableRow("missing", entry.date, date_to=entry.date_to))
        elif entry.kind == "period":
            rows.append(TableRow("period", entry.date, day_state(entry.date),
                                 entry.shifted_from, entry.is_ongoing))
        else:
            day_events = events[entry.date]
            marked = len(day_events) - 1 if end_of_day_last else 0
            for index, (kind, view) in enumerate(day_events):
                own = index == marked
                rows.append(TableRow(kind, entry.date, view,
                                     entry.shifted_from if own else None, entry.is_ongoing and own))
    return TablePage(rows=rows, has_more=more, oldest=chunk[-1].date if chunk else None)


def row_body[V](row: TableRow[V], body_of: Callable[[V], Json]) -> Json:
    """행 JSON — 행 모양은 표마다의 `body_of`가 만들고, 종류와 표시는 여기서 싣는다. 해당이 없으면
    키를 두지 않는다."""
    if row.view is None:
        assert row.date_to is not None
        return {"date": row.date.isoformat(), "dateTo": row.date_to.isoformat(), "kind": "missing"}
    body = body_of(row.view)
    body["kind"] = row.kind
    if row.shifted_from is not None:
        body["shiftedFrom"] = row.shifted_from.isoformat()
    if row.is_ongoing:
        body["isOngoing"] = True
    return body


def group_events[V](items: Sequence[tuple[dt.date, str, V]]) -> dict[dt.date, list[tuple[str, V]]]:
    """(날짜, 종류, 행)을 날짜마다 모은다 — 들어온 차례(보이는 차례)를 지킨다."""
    out: dict[dt.date, list[tuple[str, V]]] = {}
    for day, kind, view in items:
        out.setdefault(day, []).append((kind, view))
    return out
