"""실거래 줄 — 시·군·구 하나의 실거래 (009 T024, FR-008~FR-012, FR-019, research R9-4·R9-5).

**받을 달(`plan_months`)**: 첫 달(모르면 탐색 시작 `APT_TRADE_PROBE_START`)부터 이번 달까지 중

- 받은 적 없는 달
- 잠정 달(최근 12개월 — `APT_TRADE_PROVISIONAL_MONTHS`) 중 최근
  3개월(`APT_TRADE_DAILY_RECHECK_MONTHS`)은 오늘(한국
  시간) 확인하지 않은 달, 4~12개월 전 달은 이번 달 확인하지 않은 달
- 잠정으로 받았는데 잠정 기간을 벗어난 달(한 번 더 받고 확정이 된다)

확정 달은 다시 받지 않는다 — 그 뒤의 해제(약 1.2%)는 반영하지 않는 한계다(spec Assumptions).

**첫 달은 발견한다**(헌법 — 기준 시작일은 상수가 아니다): 탐색 시작 달부터 차례로 받으며 거래 없는
달도 커버리지에 남긴다(다음 실행이 이어 탐색한다). 처음 거래가 있는 달이 그 시·군·구의 첫 달이다.

**달마다 커밋한다** — 쪽을 모두 받은 뒤 순번을 매기고(쪽을 건너 이어진다), 원본·거래·커버리지를 한
트랜잭션에 남긴다. 하루 한도에 닿거나 실패하면 그 달은 남기지 않고(앞 달은 남는다) 오류를 그대로
낸다.
"""

from __future__ import annotations

import datetime as dt
import logging
import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Protocol

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.config.settings import Settings
from src.ingestion.datagokr.client import ROWS, Fetched
from src.ingestion.datagokr.trade_parse import TradePage, TradeRow, number_trades
from src.observability.logging_config import collection_logger
from src.repository import apt_job, apt_region, apt_trade
from src.repository.apt_trade import CoverageMark
from src.simulation.apt_price import add_months, month_start, provisional_from
from src.worker.apt_list_runner import sync_lawd

_log = logging.getLogger(__name__)

PROVISIONAL = "provisional"
CONFIRMED = "confirmed"
_KST = dt.timedelta(hours=9)


class TradeSource(Protocol):
    async def fetch_trades(self, lawd_cd: str, ym: str, page: int) -> Fetched[TradePage]: ...


class ProbeStartMissing(Exception):
    """첫 달을 모르는데 탐색 시작 달(`APT_TRADE_PROBE_START`)이 설정되지 않았다."""


def kst_date(now_utc: dt.datetime) -> dt.date:
    return (now_utc + _KST).date()


def ym_of(month: dt.date) -> str:
    return f"{month:%Y%m}"


def month_of(ym: str) -> dt.date:
    return dt.date(int(ym[:4]), int(ym[4:]), 1)


def _start(first_trade_ym: str | None, settings: Settings) -> dt.date:
    if first_trade_ym is not None:
        return month_of(first_trade_ym)
    if settings.apt_trade_probe_start is None:
        raise ProbeStartMissing("APT_TRADE_PROBE_START가 설정되지 않아 첫 달을 찾을 수 없습니다")
    return month_start(settings.apt_trade_probe_start)


def _months(first: dt.date, last: dt.date) -> list[dt.date]:
    out, month = [], first
    while month <= last:
        out.append(month)
        month = add_months(month, 1)
    return out


def plan_months(coverage: Mapping[str, CoverageMark], first_trade_ym: str | None, *,
                today: dt.date, settings: Settings) -> list[str]:
    """이번 실행에 받을 달(`YYYYMM`, 오름차순)."""
    current = month_start(today)
    provisional = provisional_from(today, settings.apt_trade_provisional_months)
    daily = provisional_from(today, settings.apt_trade_daily_recheck_months)
    plan: list[str] = []
    for month in _months(_start(first_trade_ym, settings), current):
        mark = coverage.get(ym_of(month))
        if mark is None:
            plan.append(ym_of(month))
        elif mark.state == PROVISIONAL:
            if month < provisional:
                plan.append(ym_of(month))  # 잠정 기간을 벗어났다 — 한 번 더 받고 확정
            elif month >= daily:
                if mark.checked_on != today:
                    plan.append(ym_of(month))
            elif month_start(mark.checked_on) != current:
                plan.append(ym_of(month))
    return plan


def is_collected(coverage: Mapping[str, CoverageMark], first_trade_ym: str | None, *,
                 today: dt.date, settings: Settings) -> bool:
    """받아 둔 시·군·구 — 첫 달(모르면 탐색 시작 달)부터 잠정 기간 앞 달까지 모든 달을 받았다."""
    try:
        start = _start(first_trade_ym, settings)
    except ProbeStartMissing:
        return False
    if first_trade_ym is None and not any(m.trade_rows for m in coverage.values()):
        # 아직 첫 거래를 찾지 못했다 — 이번 달까지 모두 받아야 "거래 없는 시·군·구"다
        last = month_start(today)
    else:
        last = add_months(provisional_from(today, settings.apt_trade_provisional_months), -1)
    return all(ym_of(month) in coverage for month in _months(start, last))


@dataclass(slots=True)
class TradeRun:
    """한 실행의 결과 — 받은 달과 그 사이 본 건축년도(단지 행의 입주년도 대체값)."""

    months: list[str] = field(default_factory=list)
    build_years: dict[str, int] = field(default_factory=dict)


async def _fetch_month(source: TradeSource, lawd_cd: str,
                       ym: str) -> list[Fetched[TradePage]]:
    first = await source.fetch_trades(lawd_cd, ym, 1)
    pages = [first]
    for page in range(2, max(1, math.ceil(first.result.total_count / ROWS)) + 1):
        pages.append(await source.fetch_trades(lawd_cd, ym, page))
    return pages


def _note_build_years(run: TradeRun, rows: list[TradeRow]) -> None:
    for row in rows:
        if row.build_year is not None:
            run.build_years[row.apt_seq] = row.build_year


async def collect_trades(factory: async_sessionmaker[AsyncSession], source: TradeSource,
                         lawd_cd: str, job_id: int, *, settings: Settings,
                         now: dt.datetime, run: TradeRun) -> None:
    """받을 달을 차례로 받는다. 실패하면 받은 달까지 남기고 오류를 그대로 낸다(`run`에 받은 달이
    남는다)."""
    today = kst_date(now)
    async with factory() as session:
        state = await apt_region.get_state(session, apt_region.sgg_scope(lawd_cd))
        first_ym = state.first_trade_ym if state is not None else None
        coverage = await apt_trade.coverage(session, lawd_cd)
        plan = plan_months(coverage, first_ym, today=today, settings=settings)
        await apt_job.set_progress(session, job_id, done=0, total=len(plan))
        await session.commit()
    provisional = ym_of(provisional_from(today, settings.apt_trade_provisional_months))
    for done, ym in enumerate(plan, start=1):
        pages = await _fetch_month(source, lawd_cd, ym)
        rows = [row for fetched in pages for row in fetched.result.rows]
        trades = number_trades(rows)
        _note_build_years(run, rows)
        async with factory() as session:
            for fetched in pages:
                await apt_trade.store_raw(
                    session, endpoint=fetched.endpoint, request_ref=fetched.request_ref,
                    status=fetched.raw_status, result_code=fetched.result_code,
                    body=fetched.raw_body, now=now)
            revisit = ym in coverage
            change = await apt_trade.store_month(session, lawd_cd, ym, trades, now=now,
                                                 revisit=revisit)
            await apt_trade.record_month(
                session, lawd_cd, ym, state=PROVISIONAL if ym >= provisional else CONFIRMED,
                rows=len(trades), checked_on=today)
            if trades:
                await apt_region.set_first_trade(session, lawd_cd, ym)
            await apt_job.set_progress(session, job_id, done=done)
            await session.commit()
        run.months.append(ym)
        if revisit and change.any:
            collection_logger().info("apt_trade_revised", extra={
                "event": "apt_trade_revised", "lawd_cd": lawd_cd, "month": f"{ym[:4]}-{ym[4:]}",
                "added": change.added, "cancelled": change.cancelled, "missing": change.missing})


async def sync_complexes(factory: async_sessionmaker[AsyncSession], lawd_cd: str,
                         run: TradeRun) -> None:
    """받은 실거래로 단지 행을 맞춘다 — 실패한 실행도 받은 데까지는 단지가 보이게 한다."""
    if not run.months:
        return
    async with factory() as session:
        await sync_lawd(session, lawd_cd, build_years=run.build_years)
        await session.commit()
