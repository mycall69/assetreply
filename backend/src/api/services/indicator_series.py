"""지표 화면의 그래프 (014 T056) — FR-010~FR-016, FR-018, FR-019, SC-002, SC-004, research R14-12,
contracts A2.

- **과거 구간이 다 받아지지 않았으면 202**(받는 중·실패) — 받은 만큼만 그린 선을 완성된 그래프처럼
  보이지 않는다(FR-016)
- (반복 2026-10-10b) 질의는 보는 기간 `range`다(`simulation/indicator_range`). 일봉
  기간(월~모두)은 그 기간의 **일봉 전부**이고 점을 묶지 않는다. 일·주(장중)는 경로가
  `indicator_intraday`에 넘긴다 — 여기 오지 않는다. 결측은 `simulation/market_gaps`(같은 시장
  묶음·14일)
- **오늘 잠정 꼬리**는 현재 시세 서비스의 값(카드와 같은 값)이다. 환율에는 붙이지 않는다 — 시장
  환율과 고시는 다른 계열이다
  (명확화 2)
- 점이 `DASHBOARD_SERIES_MAX_POINTS`(기본 3만)를 넘을 때만 LTTB로 줄인다 — 실제 점을 고른다(R14-12)
- 환율은 외환 메뉴(001)의 고시 이력을 읽는다. 모자라면 **외환 수집
  경로**(`collection_gate.ensure_background_job`)에 넘긴다 —
  대시보드가 ECOS를 부르지 않는다(FR-018)
- 수집 상태(마지막 성공·성공 뒤의 실패)를 싣는다(FR-019 — 원칙 V 커버리지 조회)
- **환율도 같은 진행 경로다**(반복 2026-10-10 — FR-018). 외환 진행 스트림은 사건 이름·모양이 달라
  화면이 읽지 못한다
- 그 통화의 마지막 외환 수집이 실패했고 지금 받는 중(점유·큐)이 아니면 실패를 보이고 **외환 수집을
  다시 요청하지 않는다** — 다시 물을 때마다 요청하면 인증 만료처럼 풀리지 않는 실패에 ECOS를 계속
  부른다
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from decimal import Decimal
from typing import Final, Protocol

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.services.collection_gate import CollectionDecision, CollectionTicket, decide_collection
from src.api.services.market_quotes import dec, indicator_json
from src.api.services.series_query import compute_gaps, missing_days
from src.config.settings import Settings
from src.db.models import Currency, FxCollectionLock, JobStatus, MarketIndicatorCoverage
from src.observability.events import mask_secrets
from src.repository import coverage as fx_coverage
from src.repository import fx_rate, market_daily
from src.repository import job as fx_job
from src.repository.collection_lock import SCOPE_COLLECTION
from src.simulation.downsample import Point, lttb
from src.simulation.indicator_periods import PeriodPoint, build_points
from src.simulation.indicator_range import RangeKey, range_start
from src.simulation.market_gaps import Sibling, missing_ranges
from src.simulation.market_indicators import Indicator, siblings
from src.simulation.market_quote import MarketQuote
from src.simulation.market_session import trading_date

Json = dict[str, object]
_DAY: Final = dt.timedelta(days=1)
_KST: Final = "krx"

EnsureJob = Callable[[AsyncSession, str], Awaitable[CollectionTicket]]

#: 실패로 보는 외환 수집 작업의 끝 상태 — 일부만 받고 실패한 것도 이력이 모자라면 실패다.
_FX_FAILED: Final = (JobStatus.FAILED, JobStatus.PARTIAL)


class QuoteLookup(Protocol):
    """현재 시세 — 잠정 꼬리의 근거(카드와 같은 값)."""

    async def quote(self, indicator_id: str) -> MarketQuote | None: ...


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


def _window(points: list[PeriodPoint], start: dt.date | None) -> list[PeriodPoint]:
    """보는 기간 안의 일봉 — `start`가 없으면(모두) 전부."""
    return points if start is None else [p for p in points if p.date >= start]


def _indicator_block(indicator: Indicator) -> Json:
    block = indicator_json(indicator)
    block.pop("order", None)
    return block


def _day(day: dt.date | None) -> str | None:
    return None if day is None else day.isoformat()


@dataclass(frozen=True, slots=True)
class FxState:
    """환율 그래프의 이력 상태 — 그래프 경로(202·200)와 진행 SSE가 같은 판정을 쓴다."""

    complete: bool
    #: contracts A4 `snapshot`과 같은 칸 — 외환 커버리지(남은 날 = 빠진 날 수)
    progress: Json
    #: 마지막 외환 수집이 실패했고 지금 받는 중이 아니면 `{kind, message, at}`
    failure: Json | None
    start: dt.date | None
    end: dt.date
    covered_from: dt.date | None
    covered_through: dt.date | None
    #: 외환 커버리지의 마지막 갱신 — 200의 `history.lastSuccessAt`
    last_updated_at: dt.datetime | None


async def _fx_running(session: AsyncSession, code: str) -> bool:
    """그 통화의 외환 수집 점유가 있는가(실행 중)."""
    held = await session.execute(
        select(FxCollectionLock.job_id).where(
            FxCollectionLock.scope == SCOPE_COLLECTION,
            FxCollectionLock.currency_code == code,
        )
    )
    return held.scalar_one_or_none() is not None


async def _fx_failure(session: AsyncSession, code: str) -> Json | None:
    """그 통화의 마지막 외환 수집 작업이 실패로 끝났으면 그 까닭."""
    jobs = await fx_job.list_jobs(session, currency_code=code, limit=1)
    if not jobs or jobs[0].status not in _FX_FAILED or not jobs[0].last_error:
        return None
    last = jobs[0]
    # 외환 작업의 종료 시각은 서버 지역 시각이다(001 관례) — UTC로 바꿔 낸다
    at = None if last.finished_at is None else last.finished_at.astimezone(dt.UTC)
    return {"kind": "fx_collection", "message": mask_secrets(last.last_error), "at": _iso(at)}


async def fx_state(
    session: AsyncSession,
    indicator: Indicator,
    *,
    settings: Settings,
    now: dt.datetime,
    fx_busy: str | None,
) -> FxState:
    """외환 고시 이력이 그래프에 충분한가, 받는 중인가, 실패했는가. `fx_busy`는 외환 시작 큐가 처리
    중인 통화."""
    code = indicator.fx_currency or ""
    currency = await session.get(Currency, code)
    cov = await fx_coverage.get_coverage(session, code)
    end = trading_date(_KST, now)
    start = currency.first_available_date if currency is not None else None
    if start is None and cov is not None:
        start = cov.covered_from
    missing = None if start is None else await missing_days(session, code, start, end)
    covered_from = None if cov is None else cov.covered_from
    covered_through = None if cov is None else cov.covered_through
    progress: Json = {
        "firstDay": _day(start),
        "coveredFrom": _day(covered_from),
        "coveredThrough": _day(covered_through),
        "remainingDays": missing,
    }
    # 받은 이력이 없으면(첫 날도 커버리지도 없음) 모자란 것이다
    complete = missing is not None and (
        decide_collection(
            missing_days=missing, threshold_days=settings.collection_sync_threshold_days
        )
        is not CollectionDecision.BACKGROUND
    )
    failure = None
    if not complete and fx_busy != code and not await _fx_running(session, code):
        failure = await _fx_failure(session, code)
    last_updated_at = None if cov is None else cov.last_updated_at
    return FxState(
        complete, progress, failure, start, end, covered_from, covered_through, last_updated_at
    )


async def fx_pending(
    session: AsyncSession, indicator: Indicator, state: FxState, ensure_job: EnsureJob
) -> Json:
    """환율 이력이 모자랄 때의 202 본문 — 그래프와 일자별 표(A7)가 같은 판정·같은 본문을 쓴다."""
    head: Json = {"indicator": {"id": indicator.id, "name": indicator.name}}
    if state.failure is not None:
        # 다시 요청하지 않는다 — [다시 시도](A3)만 외환 수집 경로에 넘긴다
        return {
            "status": "failed",
            **head,
            "progress": state.progress,
            "failure": state.failure,
            "progressUrl": progress_url(indicator.id),
        }
    ticket = await ensure_job(session, indicator.fx_currency or "")
    return {
        "status": "collecting",
        **head,
        "progress": state.progress,
        "failure": None,
        "progressUrl": progress_url(indicator.id),
        "jobId": ticket.job_id,
    }


def market_pending(indicator: Indicator, row: MarketIndicatorCoverage | None) -> Json:
    """과거 구간이 다 받아지지 않았을 때의 202 본문 — 그래프와 일자별 표(A7)가 같다."""
    failure = failure_after_success(row)
    return {
        "status": "failed" if failure is not None else "collecting",
        "indicator": {"id": indicator.id, "name": indicator.name},
        "progress": progress_json(row),
        "failure": failure,
        "progressUrl": progress_url(indicator.id),
    }


async def _fx_series(
    session: AsyncSession,
    indicator: Indicator,
    range_key: RangeKey,
    *,
    settings: Settings,
    now: dt.datetime,
    ensure_job: EnsureJob,
    fx_busy: str | None,
) -> tuple[int, Json]:
    code = indicator.fx_currency or ""
    state = await fx_state(session, indicator, settings=settings, now=now, fx_busy=fx_busy)
    if not state.complete or state.start is None:
        return 202, await fx_pending(session, indicator, state, ensure_job)
    start, end = state.start, state.end
    rows = await fx_rate.series(session, code, start, end)
    closes = [(r.quote_date, r.base_rate) for r in rows]
    provisional = {r.quote_date for r in rows if r.is_provisional}
    gaps = compute_gaps(
        start,
        end,
        {d for d, _ in closes},
        state.covered_from,
        state.covered_through,
    )
    window = range_start(end, range_key)
    points = _window(
        build_points(closes, "daily", today=end, provisional_dates=provisional), window
    )
    reduced, downsampled = _reduce(points, settings.dashboard_series_max_points)
    return 200, {
        "indicator": _indicator_block(indicator),
        "range": range_key,
        "history": {
            "source": "ecos",
            "firstDate": closes[0][0].isoformat() if closes else None,
            "lastDate": closes[-1][0].isoformat() if closes else None,
            "tailPending": False,
            "lastSuccessAt": _iso(state.last_updated_at),
            "lastFailure": None,
        },
        "points": _points_json(reduced),
        "gaps": [
            {"from": g.start.isoformat(), "to": g.end.isoformat(), "reason": "missing"}
            for g in gaps
            if g.reason == "not_collected" and (window is None or g.end >= window)
        ],
        "downsampled": downsampled,
        "sourcePointCount": len(points),
    }


async def market_gaps(
    session: AsyncSession,
    indicator: Indicator,
    row: MarketIndicatorCoverage,
    days: list[dt.date],
) -> list[tuple[dt.date, dt.date]]:
    """결측 구간(R14-5 — 같은 시장 묶음·14일). 그래프와 일자별 표가 같은 판정을 쓴다."""
    assert row.covered_from is not None and row.covered_through is not None
    sibling_rows = [await _sibling(session, s) for s in siblings(indicator)]
    return missing_ranges(
        days, covered=(row.covered_from, row.covered_through), siblings=sibling_rows
    )


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
    range_key: RangeKey,
    *,
    quotes: QuoteLookup | None,
    settings: Settings,
    now: dt.datetime,
    ensure_job: EnsureJob,
    fx_busy: str | None = None,
) -> tuple[int, Json]:
    """contracts A2 일봉 기간 — (상태 코드, 본문). `fx_busy`는 외환 시작 큐가 처리 중인 통화(환율만
    쓴다)."""
    if indicator.history == "fx":
        return await _fx_series(
            session,
            indicator,
            range_key,
            settings=settings,
            now=now,
            ensure_job=ensure_job,
            fx_busy=fx_busy,
        )
    row = await market_daily.get_coverage(session, indicator.id)
    if not complete(row):
        return 202, market_pending(indicator, row)
    assert row is not None and row.covered_from is not None and row.covered_through is not None
    closes = await market_daily.closes(session, indicator.id)
    gaps = await market_gaps(session, indicator, row, [d for d, _ in closes])
    today = trading_date(indicator.market, now)
    series: list[tuple[dt.date, Decimal]] = list(closes)
    provisional: set[dt.date] = set()
    quote = None if quotes is None else await quotes.quote(indicator.id)
    last = closes[-1][0] if closes else None
    if quote is not None and quote.provisional and (last is None or quote.session_date > last):
        series.append((quote.session_date, quote.value))
        provisional.add(quote.session_date)
    window = range_start(today, range_key)
    points = _window(
        build_points(series, "daily", today=today, provisional_dates=provisional), window
    )
    reduced, downsampled = _reduce(points, settings.dashboard_series_max_points)
    return 200, {
        "indicator": _indicator_block(indicator),
        "range": range_key,
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
            {"from": a.isoformat(), "to": b.isoformat(), "reason": "missing"}
            for a, b in gaps
            if window is None or b >= window
        ],
        "downsampled": downsampled,
        "sourcePointCount": len(points),
    }
