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
- (014 반복 2026-10-13b — FR-048) 가격을 넘긴 표는 행마다 **직전 기간 대표값 대비 등락**을
  싣는다. 비교 날짜는 쪽을 자르기 전의 전체 시세일에서 찾으므로 쪽의 마지막 행도 쪽 너머와
  견준다(추가 질의 없음). 계산은 잘라 낸 쪽의 행만이다. 같은 날 행은 같은 가격이라 같은 값이다
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal

from src.api.errors import InvalidQuery
from src.simulation.period_table import (
    PERIOD_UNITS,
    PeriodUnit,
    build_table,
    page,
    previous_representative,
)
from src.simulation.price_change import PriceChange, price_change
from src.simulation.reinvest import SplitOn

Json = dict[str, object]
#: 행의 가격 — (이름, 값). 행 키는 이름 + `Change`다(`open` → `openChange`). 값이 없으면 등락도
#: 없다.
Prices = Sequence[tuple[str, Decimal | None]]


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
    #: 가격 이름마다의 직전 기간 대표값 대비 등락(비교할 행이 없으면 `None`). 가격을 받지 않았으면
    #: 비어 있다.
    changes: tuple[tuple[str, PriceChange | None], ...] = ()


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
    prices: Callable[[V], Prices] | None = None,
    splits: Sequence[SplitOn] = (),
) -> TablePage[V]:
    """한 쪽의 행.

    `events`는 날짜 → 그날의 사건 행(보이는 차례, `(kind, view)`)이다. `end_of_day_last`가 참이면 그
    목록의 마지막이, 거짓이면 처음이 그날의 마지막
    사건 행이다. `day_state`는 기간 행의 값 — 그 날짜의 하루하루 상태를 행 모양으로 바꿔 준다.

    `prices`가 있으면 행마다 그 가격들의 등락을 싣는다(014 반복 2026-10-13b). `splits`는 주식의
    분할·병합 — 비교 가격을 맞춘다. 없으면 014 전과 같다.
    """
    entries = build_table(quote_days, events.keys(), unit, end, missing)
    chunk, more = page(entries, before, limit)
    previous = previous_representative(quote_days, unit) if prices is not None else None
    states: dict[dt.date, V] = {}

    def state_on(day: dt.date) -> V:
        """그날 상태를 보이는 행의 값 — 비교 날짜의 가격을 읽는다. 같은 날 행은 같은 가격이다."""
        if day not in states:
            day_events = events.get(day)
            states[day] = (day_events[-1 if end_of_day_last else 0][1] if day_events
                           else day_state(day))
        return states[day]

    def changes_of(day: dt.date, view: V) -> tuple[tuple[str, PriceChange | None], ...]:
        if prices is None or previous is None:
            return ()
        compared = previous(day)
        if compared is None:
            return tuple((name, None) for name, _ in prices(view))
        before_prices = dict(prices(state_on(compared)))
        return tuple(
            (name, price_change(value, before_prices.get(name), compared_to=compared, day=day,
                                splits=splits))
            for name, value in prices(view))

    rows: list[TableRow[V]] = []
    for entry in chunk:
        if entry.kind == "missing":
            rows.append(TableRow("missing", entry.date, date_to=entry.date_to))
        elif entry.kind == "period":
            # 기간 행의 날에는 사건이 없다 — 하루 상태다(비교에 쓴 값을 다시 만들지 않는다).
            view = state_on(entry.date)
            rows.append(TableRow("period", entry.date, view, entry.shifted_from, entry.is_ongoing,
                                 changes=changes_of(entry.date, view)))
        else:
            day_events = events[entry.date]
            marked = len(day_events) - 1 if end_of_day_last else 0
            for index, (kind, view) in enumerate(day_events):
                own = index == marked
                rows.append(TableRow(kind, entry.date, view,
                                     entry.shifted_from if own else None, entry.is_ongoing and own,
                                     changes=changes_of(entry.date, view)))
    return TablePage(rows=rows, has_more=more, oldest=chunk[-1].date if chunk else None)


def change_json(change: PriceChange | None) -> Json | None:
    """등락 한 칸(contracts A20) — 외환 `change`의 꼴에 `split`(맞춘 분할 비율 — 013 비교 블록
    `unitPrice.split`과 같은 꼴)을 더한다. 시세 출처 응답의 분할 필드 이름은 어댑터 밖에 쓰지 않는다
    (005 가드 `test_layer_boundaries`). 금액·비율은 문자열이다(원칙 VI). 가상자산 시가는 소수
    14자리라 지수 표기가 되지 않게 `f`로 쓴다."""
    if change is None:
        return None
    return {
        "comparedTo": change.compared_to.isoformat(),
        "absolute": format(change.absolute, "f"),
        "percent": None if change.percent is None else format(change.percent, "f"),
        "direction": change.direction,
        "split": None if change.split_ratio is None else {"ratio": change.split_ratio},
    }


def row_body[V](row: TableRow[V], body_of: Callable[[V], Json]) -> Json:
    """행 JSON — 행 모양은 표마다의 `body_of`가 만들고, 종류와 표시는 여기서 싣는다. 해당이 없으면
    키를 두지 않는다."""
    if row.view is None:
        assert row.date_to is not None
        return {"date": row.date.isoformat(), "dateTo": row.date_to.isoformat(), "kind": "missing"}
    body = body_of(row.view)
    body["kind"] = row.kind
    for name, change in row.changes:
        body[f"{name}Change"] = change_json(change)
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
