"""행정구역과 목록 갱신 상태 (009 T022, FR-002, FR-015, data-model 1·8절).

- 행정구역은 갱신마다 전국을 upsert하고 본 시각(`seen_at`)을 남긴다. **갱신에서 사라진 코드는 지우지
  않고
  `retired_at`** — 과거 거래의 근거다. 풀다운과 실거래 요청에는 `retired_at`이 없는 코드만
  쓴다(출처는 과거 거래도 새 코드로만 준다, research R9-3)
- 목록 상태(`apt_list_state`)는 `regions`·`umd:<법정동>`·`sgg:<시·군·구>` 범위의 마지막 성공과
  시·군·구의 첫
  거래 달이다
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Sequence

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.dialect import upsert
from src.db.models import AptListState, AptRegion
from src.ingestion.protocols import Region

SOURCE = "stanregin"
REGIONS_SCOPE = "regions"


def umd_scope(umd_code: str) -> str:
    return f"umd:{umd_code}"


def sgg_scope(lawd_cd: str) -> str:
    return f"sgg:{lawd_cd}"


async def store_regions(session: AsyncSession, regions: Sequence[Region], *,
                        now: dt.datetime) -> list[str]:
    """전국을 upsert하고, 이번에 보지 못한 현존 코드를 `retired_at`으로 표시한다. 새로 사라진
    시·군·구의 `lawd_cd`를 돌려준다 — 그 코드의 거래를 집계에서 빼야 한다."""
    rows: list[dict[str, object]] = [
        {"code": r.code, "level": r.level, "parent_code": r.parent_code, "lawd_cd": r.lawd_cd,
         "name": r.name, "full_name": r.full_name, "source": SOURCE, "ingested_at": now,
         "seen_at": now, "retired_at": None}
        for r in regions]
    for start in range(0, len(rows), 1000):
        await upsert(session, AptRegion, rows[start:start + 1000])
    retiring = list((await session.execute(select(AptRegion).where(
        AptRegion.seen_at < now, AptRegion.retired_at.is_(None)))).scalars())
    await session.execute(update(AptRegion).where(
        AptRegion.seen_at < now, AptRegion.retired_at.is_(None)).values(retired_at=now))
    seen_lawd = {r.lawd_cd for r in regions if r.level == "sgg"}
    return sorted({r.lawd_cd for r in retiring
                   if r.level == "sgg" and r.lawd_cd and r.lawd_cd not in seen_lawd})


async def children(session: AsyncSession, parent: str | None) -> list[AptRegion]:
    """현존 코드만, 이름순. `parent`가 없으면 시·도."""
    query = select(AptRegion).where(AptRegion.retired_at.is_(None))
    if parent is None:
        query = query.where(AptRegion.level == "sido")
    else:
        query = query.where(AptRegion.parent_code == parent)
    rows = list((await session.execute(query)).scalars())
    return sorted(rows, key=lambda r: r.name)


async def current(session: AsyncSession, code: str) -> AptRegion | None:
    """현존 코드 하나. 사라졌거나 모르면 None."""
    region = await session.get(AptRegion, code)
    return region if region is not None and region.retired_at is None else None


async def sgg_of(session: AsyncSession, lawd_cd: str) -> AptRegion | None:
    """`lawd_cd`의 시·군·구 행(현존이든 아니든)."""
    return (await session.execute(select(AptRegion).where(
        AptRegion.level == "sgg", AptRegion.lawd_cd == lawd_cd).order_by(
        AptRegion.retired_at.is_not(None)).limit(1))).scalar_one_or_none()


async def get_state(session: AsyncSession, scope: str) -> AptListState | None:
    return (await session.execute(select(AptListState).where(AptListState.scope == scope)
                                  .execution_options(populate_existing=True))
            ).scalar_one_or_none()


async def mark_refreshed(session: AsyncSession, scope: str, *, now: dt.datetime) -> None:
    state = await get_state(session, scope)
    if state is None:
        session.add(AptListState(scope=scope, refreshed_at=now))
    else:
        state.refreshed_at = now
    await session.flush()


async def set_first_trade(session: AsyncSession, lawd_cd: str, ym: str) -> None:
    """시·군·구의 첫 거래 달. 더 이른 달을 찾으면 그 달로 바꾼다."""
    scope = sgg_scope(lawd_cd)
    state = await get_state(session, scope)
    if state is None:
        session.add(AptListState(scope=scope, first_trade_ym=ym))
    elif state.first_trade_ym is None or ym < state.first_trade_ym:
        state.first_trade_ym = ym
    await session.flush()


def is_stale(state: AptListState | None, *, now: dt.datetime, days: int) -> bool:
    """받은 적 없거나 `days`일이 지났다."""
    return (state is None or state.refreshed_at is None
            or now - state.refreshed_at >= dt.timedelta(days=days))
