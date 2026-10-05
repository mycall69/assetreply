"""단지 (009 T022, FR-003, FR-032, data-model 2절, research R9-3).

두 자료(단지 목록 `kapt_code`, 실거래 `apt_seq`)의 같은 단지는 한 행이다. **행을 지우지 않고 id가
바뀌지 않는다** — 이력이 단지 id를 저장한다. 짝은 있는 행에 다른 쪽 식별자를 붙이는 것으로 하고, 두
행이 이미 따로 있을 때 짝이 드러나면 먼저 만든 행에 합친 뒤 다른 행에 `merged_into`를 남긴다. 단지
id를 받는 모든 곳은 `resolve`로 `merged_into`를 따라간다.

짝을 정하는 규칙은 `api/services/realestate_complex_match.py`(순수 함수), 행을 고치는 순서는
`worker/apt_list_runner.py`다.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterable

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import AptComplex
from src.ingestion.protocols import ComplexBasis

KAPT = "kapt"
TRADE = "trade"
#: 합쳐진 행을 따라가는 최대 단계 — 고리가 생겨도 끝난다.
_MAX_HOPS = 8


async def resolve(session: AsyncSession, complex_id: int) -> AptComplex | None:
    """단지 id → 지금의 행. 합쳐진 행이면 `merged_into`를 따라간다."""
    row = await session.get(AptComplex, complex_id)
    hops = 0
    while row is not None and row.merged_into is not None and hops < _MAX_HOPS:
        row = await session.get(AptComplex, row.merged_into)
        hops += 1
    return row


async def live_in_umd(session: AsyncSession, umd_code: str) -> list[AptComplex]:
    """그 동의 단지 — 합쳐진 행은 빼고."""
    return list((await session.execute(select(AptComplex).where(
        AptComplex.umd_code == umd_code, AptComplex.merged_into.is_(None))
        .execution_options(populate_existing=True))).scalars())


async def for_sync(session: AsyncSession, umd_code: str,
                   apt_seqs: Iterable[str]) -> list[AptComplex]:
    """짝짓기에 쓸 행 — 그 동의 단지와, 다른 동·옛 코드에 남은 같은 `apt_seq`의 행."""
    seqs = sorted(set(apt_seqs))
    condition = AptComplex.umd_code == umd_code
    if seqs:
        condition = or_(condition, AptComplex.apt_seq.in_(seqs))
    return list((await session.execute(select(AptComplex).where(
        condition, AptComplex.merged_into.is_(None)))).scalars())


async def pending_details(session: AsyncSession, umd_code: str) -> list[AptComplex]:
    """기본 정보를 아직 받지 않은 단지 목록의 단지(새 단지만 — 세대수는 바뀌지 않는다)."""
    return list((await session.execute(select(AptComplex).where(
        AptComplex.umd_code == umd_code, AptComplex.merged_into.is_(None),
        AptComplex.kapt_code.is_not(None), AptComplex.details_checked_at.is_(None))
        .order_by(AptComplex.id))).scalars())


def jibun_text(bonbun: int | None, bubun: int | None) -> str | None:
    if bonbun is None:
        return None
    return f"{bonbun}-{bubun}" if bubun else f"{bonbun}"


def apply_basis(row: AptComplex, basis: ComplexBasis | None, *, now: dt.datetime) -> None:
    """기본 정보로 세대수·입주년도(사용승인 연도)·지번을 채운다. 없는 코드면 확인한 시각만."""
    row.details_checked_at = now
    if basis is None:
        return
    row.households = basis.households
    if basis.move_in_year is not None:
        row.move_in_year, row.move_in_source = basis.move_in_year, KAPT
    if row.apt_seq is None:  # 짝지은 행은 실거래 지번을 쓴다(목록 응답의 `jibun`)
        row.jibun = jibun_text(basis.bonbun, basis.bubun) or row.jibun
