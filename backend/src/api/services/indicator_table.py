"""지표 모달의 일자별 표 (014 반복 2026-10-10b T117) — FR-013, FR-014, FR-016, FR-018, FR-029,
SC-012, contracts A7, data-model §5a.

- 행 꼴·쪽 넘기기는 **주식 일자별 표(012)와 같다** — 날짜 고르기는 `simulation/period_table`, 행
  JSON은 `table_rows.row_body`(`kind`·`shiftedFrom`·`isOngoing`), 값은 순수 모듈
  `simulation/indicator_table`
- 과거 구간이 다 받아지지 않았으면 그래프와 **같은 판정·같은 202**다
  (`indicator_series.market_pending`·`fx_pending`) — 받은 만큼만 보인 표를 완성된 이력처럼 보이지
  않는다(FR-016)
- 오늘(현지) 잠정 행은 현재 시세(카드와 같은 값)이고 시가·고가·저가가 없다 — 출처의 현재 시세가
  시가를 주지 않는다(R14-19). 환율에는 붙이지 않는다(그래프와 같다 — 시장 환율과 고시는 다른 계열)
- 환율은 외환 고시 이력이고 시가·고가·저가가 늘 없다(`seriesNote: "fx_fixing"`)
- 결측 구간 행은 일 단위에만 있다(012와 같다). 값이 없다 — 날짜 둘만(원칙 V)
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from src.api.services.indicator_series import (
    EnsureJob,
    QuoteLookup,
    complete,
    fx_pending,
    fx_state,
    market_gaps,
    market_pending,
)
from src.api.services.market_quotes import dec
from src.api.services.series_query import compute_gaps
from src.api.services.table_rows import TableRow, row_body, table_page
from src.config.settings import Settings
from src.repository import fx_rate, market_daily
from src.simulation.indicator_table import TableBar, TableValue, table_values
from src.simulation.market_indicators import Indicator
from src.simulation.market_session import trading_date
from src.simulation.period_table import PeriodUnit

Json = dict[str, object]


def _text(value: Decimal | None) -> str | None:
    return None if value is None else dec(value)


def _value_body(day: dt.date, value: TableValue) -> Json:
    return {
        "date": day.isoformat(),
        "open": _text(value.open),
        "high": _text(value.high),
        "low": _text(value.low),
        "close": dec(value.close),
        "change": _text(value.change),
        "changeRate": _text(value.change_rate),
        "provisional": value.provisional,
    }


def _body(
    indicator: Indicator,
    unit: PeriodUnit,
    *,
    bars: list[TableBar],
    provisional: set[dt.date],
    missing: list[tuple[dt.date, dt.date]],
    end: dt.date,
    before: dt.date | None,
    limit: int,
    note: str | None,
) -> Json:
    values = table_values(bars, unit, provisional=provisional)
    shown = table_page(
        unit=unit,
        end=end,
        before=before,
        limit=limit,
        quote_days=[b.date for b in bars],
        events={},
        end_of_day_last=True,
        day_state=lambda day: (day, values[day]),
        missing=missing if unit == "daily" else (),
    )
    rows: list[TableRow[tuple[dt.date, TableValue]]] = shown.rows
    return {
        "indicator": {"id": indicator.id, "name": indicator.name, "unit": indicator.unit},
        "period": unit,
        "rows": [row_body(r, lambda v: _value_body(*v)) for r in rows],
        "hasMore": shown.has_more,
        "oldestReturned": None if shown.oldest is None else shown.oldest.isoformat(),
        "seriesNote": note,
    }


async def _fx_table(
    session: AsyncSession,
    indicator: Indicator,
    unit: PeriodUnit,
    *,
    before: dt.date | None,
    limit: int,
    settings: Settings,
    now: dt.datetime,
    ensure_job: EnsureJob,
    fx_busy: str | None,
) -> tuple[int, Json]:
    state = await fx_state(session, indicator, settings=settings, now=now, fx_busy=fx_busy)
    if not state.complete or state.start is None:
        return 202, await fx_pending(session, indicator, state, ensure_job)
    code = indicator.fx_currency or ""
    rows = await fx_rate.series(session, code, state.start, state.end)
    bars = [TableBar(r.quote_date, None, None, None, r.base_rate) for r in rows]
    gaps = compute_gaps(
        state.start,
        state.end,
        {b.date for b in bars},
        state.covered_from,
        state.covered_through,
    )
    # 받은 고시 사이의 미수집만 결측 행이다 — 마지막 고시 뒤의 꼬리(오늘 등 아직 받지 않은 날)는
    # 출처 결측이 아니다(T123 실측 — 오늘이 "출처에 값 없음"으로 보였다)
    first = bars[0].date if bars else None
    last = bars[-1].date if bars else None
    inner = [
        (g.start, g.end)
        for g in gaps
        if g.reason == "not_collected"
        and first is not None
        and last is not None
        and first < g.start
        and g.end < last
    ]
    return 200, _body(
        indicator,
        unit,
        bars=bars,
        provisional={r.quote_date for r in rows if r.is_provisional},
        missing=inner,
        end=state.end,
        before=before,
        limit=limit,
        note="fx_fixing",
    )


async def table_response(
    session: AsyncSession,
    indicator: Indicator,
    unit: PeriodUnit,
    *,
    before: dt.date | None,
    limit: int,
    quotes: QuoteLookup | None,
    settings: Settings,
    now: dt.datetime,
    ensure_job: EnsureJob,
    fx_busy: str | None = None,
) -> tuple[int, Json]:
    """contracts A7 — (상태 코드, 본문)."""
    if indicator.history == "fx":
        return await _fx_table(
            session,
            indicator,
            unit,
            before=before,
            limit=limit,
            settings=settings,
            now=now,
            ensure_job=ensure_job,
            fx_busy=fx_busy,
        )
    row = await market_daily.get_coverage(session, indicator.id)
    if not complete(row):
        return 202, market_pending(indicator, row)
    assert row is not None
    stored = await market_daily.bars(session, indicator.id)
    bars = [TableBar(b.date, b.open, b.high, b.low, b.close) for b in stored]
    missing = await market_gaps(session, indicator, row, [b.date for b in bars])
    today = trading_date(indicator.market, now)
    provisional: set[dt.date] = set()
    quote = None if quotes is None else await quotes.quote(indicator.id)
    last = bars[-1].date if bars else None
    if quote is not None and quote.provisional and (last is None or quote.session_date > last):
        bars.append(TableBar(quote.session_date, None, None, None, quote.value))
        provisional.add(quote.session_date)
    return 200, _body(
        indicator,
        unit,
        bars=bars,
        provisional=provisional,
        missing=missing,
        end=today,
        before=before,
        limit=limit,
        note=None,
    )
