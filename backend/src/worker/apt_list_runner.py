"""목록 줄 — 행정구역·단지 기본 정보, 그리고 단지 짝짓기 (009 T024, FR-002, FR-003, FR-015, research
R9-3).

- **행정구역**: 전국을 쪽마다 받아 모두 받은 뒤 한 번에 저장한다(일부만 저장하면 받지 못한 코드가
  "사라진
  코드"로 보인다). 이번에 보지 못한 현존 코드는 `retired_at`, 사라진 시·군·구의 거래는 집계에서 뺀다
- **기본 정보**: 그 동의 새 단지만 1회씩 — 세대수·사용승인 연도·지번. 단지마다 커밋한다(한도에
  닿아도 받은
  단지는 남는다). 다 받으면 지번으로 드러난 짝을 맞춘다
- **짝짓기(`sync_umd`)**: 단지 목록과 실거래의 같은 단지를 한 행으로. 한쪽 행만 있으면 그 행에 다른
  쪽
  식별자를 붙이고, 둘 다 없으면 한 행을 만들고, **두 행이 이미 따로 있으면 먼저 만든 행에
  합친다**(다른 행은 `merged_into` — 지우지 않는다). 실거래의 같은 `apt_seq`가 새 시·군·구 코드로
  왔으면 행의 코드를 바꾼다
"""

from __future__ import annotations

import datetime as dt
import math
from collections.abc import Mapping, Sequence
from typing import Protocol

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.api.services.realestate_complex_match import (
    ComplexIds,
    KaptSide,
    TradeSide,
    match_complexes,
    plan_merges,
)
from src.db.models import AptComplex
from src.ingestion.datagokr.client import ROWS, Fetched
from src.ingestion.datagokr.errors import DataGoKrFormatError
from src.ingestion.datagokr.kapt_parse import ComplexListPage
from src.ingestion.datagokr.region_parse import RegionPage, RegionRow, build_regions
from src.ingestion.protocols import ComplexBasis, ComplexListing
from src.repository import apt_complex, apt_job, apt_region, apt_trade
from src.repository.apt_trade import LatestTrade


class RegionSource(Protocol):
    async def fetch_regions(self, page: int) -> Fetched[RegionPage]: ...


class BasisSource(Protocol):
    async def fetch_complex_basis(self, kapt_code: str) -> Fetched[ComplexBasis | None]: ...


class ComplexListSource(Protocol):
    async def fetch_complex_list(self, bjd_code: str) -> Fetched[ComplexListPage]: ...


async def _keep_raw(session: AsyncSession, fetched: Fetched[object], *,
                    now: dt.datetime) -> None:
    await apt_trade.store_raw(session, endpoint=fetched.endpoint,
                              request_ref=fetched.request_ref, status=fetched.raw_status,
                              result_code=fetched.result_code, body=fetched.raw_body, now=now)


# ── 행정구역 ──────────────────────────────────────────────────────


async def collect_regions(factory: async_sessionmaker[AsyncSession], source: RegionSource,
                          job_id: int, *, now: dt.datetime) -> int:
    """전국 법정동코드. 저장한 행 수를 돌려준다. 실패하면 아무것도 바꾸지 않고 오류를 그대로
    낸다."""
    pages: list[Fetched[RegionPage]] = []
    total_pages, page = 1, 1
    while page <= total_pages:
        fetched = await source.fetch_regions(page)
        if page == 1:
            total_pages = max(1, math.ceil(fetched.result.total_count / ROWS))
        pages.append(fetched)
        async with factory() as session:
            await apt_job.set_progress(session, job_id, done=page, total=total_pages)
            await session.commit()
        page += 1
    rows: list[RegionRow] = [row for fetched in pages for row in fetched.result.rows]
    expected = pages[0].result.total_count
    if len(rows) != expected:
        raise DataGoKrFormatError(f"법정동코드 응답이 잘렸습니다 — {expected}행 중 {len(rows)}행")
    regions = build_regions(rows)
    async with factory() as session:
        for fetched in pages:
            await _keep_raw(session, fetched, now=now)
        retired = await apt_region.store_regions(session, regions, now=now)
        for lawd_cd in retired:
            await apt_trade.retire_lawd(session, lawd_cd, now=now)
        await apt_region.mark_refreshed(session, apt_region.REGIONS_SCOPE, now=now)
        await session.commit()
    return len(regions)


# ── 단지 기본 정보 ────────────────────────────────────────────────


async def collect_details(factory: async_sessionmaker[AsyncSession], source: BasisSource,
                          job_id: int, umd_code: str, *, now: dt.datetime) -> int:
    """그 동의 새 단지의 기본 정보. 받은 단지 수를 돌려준다. 단지마다 커밋한다."""
    async with factory() as session:
        pending = [(row.id, str(row.kapt_code))
                   for row in await apt_complex.pending_details(session, umd_code)]
        await apt_job.set_progress(session, job_id, done=0, total=len(pending))
        await session.commit()
    for done, (row_id, kapt_code) in enumerate(pending, start=1):
        fetched = await source.fetch_complex_basis(kapt_code)
        async with factory() as session:
            row = await session.get(AptComplex, row_id)
            if row is not None:
                apt_complex.apply_basis(row, fetched.result, now=now)
            await _keep_raw(session, fetched, now=now)
            await apt_job.set_progress(session, job_id, done=done)
            await session.commit()
    async with factory() as session:
        await sync_umd(session, umd_code, latest=await latest_for_umd(session, umd_code))
        await session.commit()
    return len(pending)


# ── 짝짓기 ────────────────────────────────────────────────────────


async def latest_for_umd(session: AsyncSession, umd_code: str) -> list[LatestTrade]:
    """목록 쪽(단지 목록·기본 정보)이 짝지을 실거래 단지. **그 시·군·구 실거래를 받는 중이면 없다**
    — 그때까지 받은 거래만으로 짝지으면 그 실행의 건축년도를 몰라 재건축 판정을 건너뛴다(T027 실측 —
    개포동). 그 실행의 마지막 맞추기(`sync_lawd`)가 건축년도를 다 알고 짝짓는다."""
    lawd_cd = umd_code[:5]
    if await apt_job.running_job_id(session, "trade", lawd_cd) is not None:
        return []
    return await apt_trade.latest_by_complex(session, lawd_cd, umd_code=umd_code)


def _kapt_wins(keep: AptComplex, drop: AptComplex) -> AptComplex:
    return keep if keep.kapt_code is not None else drop


async def _merge(session: AsyncSession, keep: AptComplex, drop: AptComplex) -> None:
    """두 행을 하나로 — 식별자를 남길 행으로 옮기고 다른 행은 `merged_into`(지우지 않는다)."""
    kapt_row = _kapt_wins(keep, drop)
    trade_row = keep if keep.apt_seq is not None else drop
    kapt_code, apt_seq = kapt_row.kapt_code, trade_row.apt_seq
    name, jibun = kapt_row.name, trade_row.jibun
    households, checked = kapt_row.households, kapt_row.details_checked_at
    move_in: tuple[int | None, str | None]
    if kapt_row.move_in_source == apt_complex.KAPT:
        move_in = (kapt_row.move_in_year, kapt_row.move_in_source)
    else:
        move_in = (trade_row.move_in_year, trade_row.move_in_source)
    drop.kapt_code = drop.apt_seq = None
    drop.merged_into = keep.id
    await session.flush()  # 유니크 식별자를 먼저 비운다
    keep.kapt_code, keep.apt_seq, keep.name, keep.jibun = kapt_code, apt_seq, name, jibun
    keep.households, keep.details_checked_at = households, checked
    keep.move_in_year, keep.move_in_source = move_in


def _apply_trade(row: AptComplex, trade: LatestTrade) -> None:
    """실거래로 아는 것을 행에 — 코드(개편 뒤 새 코드), 지번, 단지 목록 이름이 없으면 최근 이름,
    사용승인 연도가 없으면 건축년도."""
    row.umd_code, row.lawd_cd = trade.umd_code, trade.umd_code[:5]
    row.jibun = trade.jibun
    if row.kapt_code is None:
        row.name = trade.apt_name
    if row.move_in_source != apt_complex.KAPT and trade.build_year is not None:
        row.move_in_year, row.move_in_source = trade.build_year, apt_complex.TRADE


def _stored_year(row: AptComplex | None) -> int | None:
    """실거래 단지 행에 남긴 건축년도 — 그 실행이 그 단지의 거래를 받지 않았을 때 재건축 판정에
    쓴다."""
    if row is None or row.kapt_code is not None or row.move_in_source != apt_complex.TRADE:
        return None
    return row.move_in_year


def _new_row(umd_code: str, name: str) -> AptComplex:
    return AptComplex(umd_code=umd_code, lawd_cd=umd_code[:5], name=name)


async def sync_umd(session: AsyncSession, umd_code: str, *,
                   listings: Sequence[ComplexListing] | None = None,
                   latest: Sequence[LatestTrade] = ()) -> None:
    """그 동의 단지 행을 두 자료에 맞춘다. `listings`는 방금 받은 단지 목록(없으면 행에 있는 것만),
    `latest`는 그 동 실거래 단지의 가장 최근 거래다."""
    trades = [t for t in latest if t.umd_code == umd_code]
    rows = await apt_complex.for_sync(session, umd_code, (t.apt_seq for t in trades))
    by_seq = {r.apt_seq: r for r in rows if r.apt_seq is not None}
    by_kapt = {r.kapt_code: r for r in rows if r.kapt_code is not None}
    for trade in trades:
        if (row := by_seq.get(trade.apt_seq)) is not None:
            _apply_trade(row, trade)
    names: dict[str, str] = {}
    for listing in listings or ():
        names[listing.kapt_code] = listing.name
        if (row := by_kapt.get(listing.kapt_code)) is not None:
            row.name = listing.name
    await session.flush()

    kapt_sides = [KaptSide(r.kapt_code, r.name, r.umd_code, r.jibun if r.apt_seq is None else None,
                           r.move_in_year if r.move_in_source == apt_complex.KAPT else None)
                  for r in rows if r.kapt_code is not None and r.umd_code == umd_code]
    kapt_sides += [KaptSide(code, name, umd_code, None) for code, name in names.items()
                   if code not in by_kapt]
    trade_sides = [TradeSide(t.apt_seq, t.apt_name, t.umd_code, t.jibun,
                             t.build_year if t.build_year is not None else _stored_year(
                                 by_seq.get(t.apt_seq)))
                   for t in trades]
    fixed = [(r.kapt_code, r.apt_seq) for r in rows
             if r.kapt_code is not None and r.apt_seq is not None]
    matching = match_complexes(kapt_sides, trade_sides, fixed=fixed)
    latest_of = {t.apt_seq: t for t in trades}
    fixed_set = set(fixed)

    merges = dict((drop, keep) for keep, drop in plan_merges(
        [ComplexIds(r.id, r.kapt_code, r.apt_seq) for r in rows], matching.pairs))
    for kapt_code, apt_seq in matching.pairs:
        if (kapt_code, apt_seq) in fixed_set:
            continue
        kapt_row, trade_row = by_kapt.get(kapt_code), by_seq.get(apt_seq)
        if kapt_row is not None and trade_row is not None:
            keep, drop = ((kapt_row, trade_row) if merges.get(trade_row.id) == kapt_row.id
                          else (trade_row, kapt_row))
            await _merge(session, keep, drop)
        elif kapt_row is not None:
            kapt_row.apt_seq = apt_seq
            _apply_trade(kapt_row, latest_of[apt_seq])
        elif trade_row is not None:
            trade_row.kapt_code, trade_row.name = kapt_code, names[kapt_code]
        else:
            row = _new_row(umd_code, names[kapt_code])
            row.kapt_code, row.apt_seq = kapt_code, apt_seq
            _apply_trade(row, latest_of[apt_seq])
            row.name = names[kapt_code]
            session.add(row)
        await session.flush()
    for kapt_code in matching.kapt_only:
        if kapt_code not in by_kapt:
            row = _new_row(umd_code, names[kapt_code])
            row.kapt_code = kapt_code
            session.add(row)
    for apt_seq in matching.trade_only:
        if apt_seq not in by_seq:
            row = _new_row(umd_code, latest_of[apt_seq].apt_name)
            row.apt_seq = apt_seq
            _apply_trade(row, latest_of[apt_seq])
            session.add(row)
    await session.flush()


async def sync_lawd(session: AsyncSession, lawd_cd: str, *,
                    build_years: Mapping[str, int] | None = None) -> None:
    """그 시·군·구의 모든 동을 실거래에 맞춘다(실거래 수집 뒤)."""
    latest = await apt_trade.latest_by_complex(session, lawd_cd, build_years)
    by_umd: dict[str, list[LatestTrade]] = {}
    for trade in latest:
        by_umd.setdefault(trade.umd_code, []).append(trade)
    for umd_code, trades in sorted(by_umd.items()):
        await sync_umd(session, umd_code, latest=trades)
