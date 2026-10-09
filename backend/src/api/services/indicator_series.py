"""지표 화면의 그래프 (014 T056) — FR-010~FR-016, FR-018, FR-019, SC-002, SC-004, research R14-12,
contracts A2.

- **과거 구간이 다 받아지지 않았으면 202**(받는 중·실패) — 받은 만큼만 그린 선을 완성된 그래프처럼
  보이지 않는다(FR-016)
- 단위(일·주·월·년)의 대표값은 순수 모듈 `simulation/indicator_periods`, 결측은
  `simulation/market_gaps`(같은 시장 묶음·14일)
- **오늘 잠정 꼬리**는 현재 시세 서비스의 값(카드와 같은 값)이다. 환율에는 붙이지 않는다 — 시장
  환율과 고시는 다른 계열이다
  (명확화 2)
- 점이 `DASHBOARD_SERIES_MAX_POINTS`(기본 3만)를 넘을 때만 LTTB로 줄인다 — 실제 점을 고른다(R14-12)
- 환율은 외환 메뉴(001)의 고시 이력을 읽는다. 모자라면 **외환 수집
  경로**(`collection_gate.ensure_background_job`)에 넘긴다 —
  대시보드가 ECOS를 부르지 않는다(FR-018)
- 수집 상태(마지막 성공·성공 뒤의 실패)를 싣는다(FR-019 — 원칙 V 커버리지 조회)
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Awaitable, Callable
from decimal import Decimal
from typing import Final, Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from src.api.services.collection_gate import CollectionDecision, CollectionTicket, decide_collection
from src.api.services.market_quotes import dec, indicator_json
from src.api.services.series_query import compute_gaps, missing_days
from src.config.settings import Settings
from src.db.models import Currency, MarketIndicatorCoverage
from src.repository import coverage as fx_coverage
from src.repository import fx_rate, market_daily
from src.simulation.downsample import Point, lttb
from src.simulation.indicator_periods import UNITS, PeriodPoint, Unit, build_points
from src.simulation.market_gaps import Sibling, missing_ranges
from src.simulation.market_indicators import Indicator, siblings
from src.simulation.market_quote import MarketQuote
from src.simulation.market_session import trading_date

Json = dict[str, object]
_DAY: Final = dt.timedelta(days=1)
_KST: Final = "krx"

EnsureJob = Callable[[AsyncSession, str], Awaitable[CollectionTicket]]


class QuoteLookup(Protocol):
    """현재 시세 — 잠정 꼬리의 근거(카드와 같은 값)."""

    async def quote(self, indicator_id: str) -> MarketQuote | None: ...


def unit_of(raw: str | None) -> Unit:
    """틀리거나 없는 단위는 `daily`다(화면 규칙과 같다 — 400을 내지 않는다)."""
    for unit in UNITS:
        if raw == unit:
            return unit  # type: ignore[return-value]
    return "daily"


def _iso(instant: dt.datetime | None) -> str | None:
    if instant is None:
        return None
    return instant.replace(tzinfo=None).isoformat() + "Z"


def failure_after_success(row: MarketIndicatorCoverage | None) -> Json | None:
    """마지막 성공보다 뒤의 실패. 없으면 `None`."""
    if row is None or row.last_failure_at is None:
        return None
    if row.last_success_at is not None and row.last_success_at >= row.last_failure_at:
        return None
    return {
        "kind": row.last_failure_kind,
        "message": row.last_failure_message,
        "at": _iso(row.last_failure_at),
    }


def progress_json(row: MarketIndicatorCoverage | None) -> Json:
    first = None if row is None else row.first_day
    covered_from = None if row is None else row.covered_from
    remaining = (
        (covered_from - first).days if first is not None and covered_from is not None else None
    )
    return {
        "firstDay": None if first is None else first.isoformat(),
        "coveredFrom": None if covered_from is None else covered_from.isoformat(),
        "coveredThrough": None
        if row is None or row.covered_through is None
        else row.covered_through.isoformat(),
        "remainingDays": remaining,
    }


def complete(row: MarketIndicatorCoverage | None) -> bool:
    """과거 구간이 첫 날까지 닿았는가."""
    return (
        row is not None
        and row.first_day is not None
        and row.covered_from is not None
        and row.covered_through is not None
        and row.covered_from <= row.first_day
    )


def progress_url(indicator_id: str) -> str:
    return f"/api/dashboard/indicators/{indicator_id}/progress"


def _points_json(points: list[PeriodPoint]) -> list[Json]:
    out: list[Json] = []
    for p in points:
        item: Json = {"date": p.date.isoformat(), "value": dec(p.value)}
        # 선택 칸은 참일 때만 붙인다(외환 `/series`의 `isProvisional`과 같은 관례 — 응답 크기)
        if p.shifted:
            item["shifted"] = True
        if p.ongoing:
            item["ongoing"] = True
        if p.provisional:
            item["provisional"] = True
        out.append(item)
    return out


def _reduce(points: list[PeriodPoint], max_points: int) -> tuple[list[PeriodPoint], bool]:
    if len(points) <= max_points:
        return points, False
    by_date = {p.date: p for p in points}
    chosen = lttb([Point(p.date, p.value) for p in points], target=max_points)
    return [by_date[c.date] for c in chosen], True


def _indicator_block(indicator: Indicator) -> Json:
    block = indicator_json(indicator)
    block.pop("order", None)
    return block


async def _fx_series(
    session: AsyncSession,
    indicator: Indicator,
    unit: Unit,
    *,
    settings: Settings,
    now: dt.datetime,
    ensure_job: EnsureJob,
) -> tuple[int, Json]:
    code = indicator.fx_currency or ""
    currency = await session.get(Currency, code)
    cov = await fx_coverage.get_coverage(session, code)
    end = trading_date(_KST, now)
    start = currency.first_available_date if currency is not None else None
    if start is None and cov is not None:
        start = cov.covered_from
    # 받은 이력이 없으면(첫 날도 커버리지도 없음) 곧바로 외환 수집 경로에 넘긴다.
    decision = CollectionDecision.BACKGROUND
    if start is not None:
        decision = decide_collection(
            missing_days=await missing_days(session, code, start, end),
            threshold_days=settings.collection_sync_threshold_days,
        )
    if start is None or decision is CollectionDecision.BACKGROUND:
        ticket = await ensure_job(session, code)
        return 202, {
            "status": "collecting",
            "indicator": {"id": indicator.id, "name": indicator.name},
            "progress": None,
            "failure": None,
            "progressUrl": ticket.progress_url,
            "jobId": ticket.job_id,
        }
    rows = await fx_rate.series(session, code, start, end)
    closes = [(r.quote_date, r.base_rate) for r in rows]
    provisional = {r.quote_date for r in rows if r.is_provisional}
    gaps = compute_gaps(
        start,
        end,
        {d for d, _ in closes},
        cov.covered_from if cov else None,
        cov.covered_through if cov else None,
    )
    points = build_points(closes, unit, today=end, provisional_dates=provisional)
    reduced, downsampled = _reduce(points, settings.dashboard_series_max_points)
    return 200, {
        "indicator": _indicator_block(indicator),
        "unit": unit,
        "history": {
            "source": "ecos",
            "firstDate": closes[0][0].isoformat() if closes else None,
            "lastDate": closes[-1][0].isoformat() if closes else None,
            "tailPending": False,
            "lastSuccessAt": _iso(cov.last_updated_at) if cov is not None else None,
            "lastFailure": None,
        },
        "points": _points_json(reduced),
        "gaps": [
            {"from": g.start.isoformat(), "to": g.end.isoformat(), "reason": "missing"}
            for g in gaps
            if g.reason == "not_collected"
        ],
        "downsampled": downsampled,
        "sourcePointCount": len(points),
    }


async def _sibling(session: AsyncSession, indicator: Indicator) -> Sibling:
    row = await market_daily.get_coverage(session, indicator.id)
    covered = (
        (row.covered_from, row.covered_through)
        if (row is not None and row.covered_from is not None and row.covered_through is not None)
        else None
    )
    dates = frozenset(d for d, _ in await market_daily.closes(session, indicator.id))
    return Sibling(dates, covered)


async def series_response(
    session: AsyncSession,
    indicator: Indicator,
    unit: Unit,
    *,
    quotes: QuoteLookup | None,
    settings: Settings,
    now: dt.datetime,
    ensure_job: EnsureJob,
) -> tuple[int, Json]:
    """contracts A2 — (상태 코드, 본문)."""
    if indicator.history == "fx":
        return await _fx_series(
            session, indicator, unit, settings=settings, now=now, ensure_job=ensure_job
        )
    row = await market_daily.get_coverage(session, indicator.id)
    if not complete(row):
        failure = failure_after_success(row)
        return 202, {
            "status": "failed" if failure is not None else "collecting",
            "indicator": {"id": indicator.id, "name": indicator.name},
            "progress": progress_json(row),
            "failure": failure,
            "progressUrl": progress_url(indicator.id),
        }
    assert row is not None and row.covered_from is not None and row.covered_through is not None
    closes = await market_daily.closes(session, indicator.id)
    sibling_rows = [await _sibling(session, s) for s in siblings(indicator)]
    gaps = missing_ranges(
        [d for d, _ in closes],
        covered=(row.covered_from, row.covered_through),
        siblings=sibling_rows,
    )
    today = trading_date(indicator.market, now)
    series: list[tuple[dt.date, Decimal]] = list(closes)
    provisional: set[dt.date] = set()
    quote = None if quotes is None else await quotes.quote(indicator.id)
    last = closes[-1][0] if closes else None
    if quote is not None and quote.provisional and (last is None or quote.session_date > last):
        series.append((quote.session_date, quote.value))
        provisional.add(quote.session_date)
    points = build_points(series, unit, today=today, provisional_dates=provisional)
    reduced, downsampled = _reduce(points, settings.dashboard_series_max_points)
    return 200, {
        "indicator": _indicator_block(indicator),
        "unit": unit,
        "history": {
            "source": "yahoo",
            "firstDate": None if row.first_day is None else row.first_day.isoformat(),
            "lastDate": None if last is None else last.isoformat(),
            "tailPending": row.covered_through < today - _DAY,
            "lastSuccessAt": _iso(row.last_success_at),
            "lastFailure": failure_after_success(row),
        },
        "points": _points_json(reduced),
        "gaps": [
            {"from": a.isoformat(), "to": b.isoformat(), "reason": "missing"} for a, b in gaps
        ],
        "downsampled": downsampled,
        "sourcePointCount": len(points),
    }
