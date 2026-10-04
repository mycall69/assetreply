"""예금 금리·원본·커버리지 리포지토리 (T018) — 008 FR-009, FR-010, FR-012, FR-020, data-model 1~3절.

금리는 `(투자처, 달)` 복합 기본 키다. **이미 있는 달은 다시 받아도 바꾸지 않는다**(research R8-4) —
겹쳐 받은 달의 값이 달라졌으면 그 목록을 돌려주고 수집 줄이 사건(`deposit_rate_revised`)으로 남긴다.
덮어쓰면 어제 본 결과가 오늘 몰래 바뀐다. 발표된 달만 저장한다 — 잠정 금리는 저장하지
않는다(FR-024).

원본은 정규화와 따로, **응답 본문만** 남긴다 — 요청 URL에는 인증키가 있다(FR-014).

커버리지는 받은 구간 `[first_month, latest_month]`과 마지막으로 확인한 날(한국 시간)이다. 그 안의 빈
달은 **결측**, 그 뒤의 달은 **미발표**다. `checked_on`은 확인이 성공했을 때만 갱신한다(FR-010) —
실패한 날 갱신하면 다음 날까지 다시 확인하지 않는다.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Final

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.dialect import upsert
from src.db.models import DepositCoverage, DepositRate, DepositRawResponse
from src.ingestion.protocols import MonthlyRate

#: 저장할 때 남기는 출처 이름.
SOURCE: Final = "ecos"


@dataclass(frozen=True, slots=True)
class Revision:
    """겹쳐 받은 달의 값이 저장된 값과 다르다 — 바꾸지 않았다."""

    month: dt.date
    old: Decimal
    new: Decimal


def rate_text(rate: Decimal) -> str:
    """저장 자릿수(소수 4자리)의 끝 0을 지워 출처 문자열(`"3.2"`, `"2.84"`)로 되돌린다. 지수 표기를
    내지 않는다."""
    return format(rate.normalize(), "f")


async def store_raw(
    session: AsyncSession, *, institution: str | None, endpoint: str, source_ref: str,
    requested_from: dt.date | None, requested_to: dt.date | None, status_code: int,
    result_code: str | None, body: str, received_at: dt.datetime,
) -> None:
    """원본 본문을 그대로 남긴다. 항목 목록은 통계표 하나가 여러 투자처를 덮어 투자처가 비어
    있다."""
    session.add(DepositRawResponse(
        institution=institution, endpoint=endpoint, source_ref=source_ref,
        requested_from=requested_from, requested_to=requested_to, status_code=status_code,
        result_code=result_code, body=body, received_at=received_at))
    await session.flush()


async def get_rates(session: AsyncSession, institution: str) -> dict[dt.date, Decimal]:
    """그 투자처의 금리 전부(달 오름차순). 결측 달은 키가 없다 — 채우지 않는다(헌법 원칙 V)."""
    rows = await session.execute(
        select(DepositRate.month, DepositRate.rate)
        .where(DepositRate.institution == institution).order_by(DepositRate.month))
    return {month: rate for month, rate in rows.all()}


async def store_rates(
    session: AsyncSession, institution: str, rates: Sequence[MonthlyRate], *,
    ingested_at: dt.datetime,
) -> list[Revision]:
    """없는 달만 넣는다. 있는 달의 값이 다르면 바꾸지 않고 그 목록을 돌려준다(research R8-4)."""
    existing = await get_rates(session, institution)
    revisions = [Revision(r.month, existing[r.month], r.rate) for r in rates
                 if r.month in existing and existing[r.month] != r.rate]
    fresh: list[dict[str, object]] = [
        {"institution": institution, "month": r.month, "rate": r.rate, "source": SOURCE,
         "ingested_at": ingested_at} for r in rates if r.month not in existing]
    await upsert(session, DepositRate, fresh)
    return revisions


async def get_coverage(session: AsyncSession, institution: str) -> DepositCoverage | None:
    return await session.get(DepositCoverage, institution, populate_existing=True)


async def all_coverage(session: AsyncSession) -> dict[str, DepositCoverage]:
    rows = (await session.execute(select(DepositCoverage))).scalars()
    return {row.institution: row for row in rows}


async def record_coverage(
    session: AsyncSession, institution: str, *, first_month: dt.date, latest_month: dt.date,
    checked_on: dt.date,
) -> None:
    """받은 구간과 확인한 날을 기록한다. **구간은 넓히기만 한다** — 좁히면 앞서 받은 달을 잊는다."""
    current = await get_coverage(session, institution)
    if current is not None:
        first_month = min(first_month, current.first_month)
        latest_month = max(latest_month, current.latest_month)
    await upsert(session, DepositCoverage, [
        {"institution": institution, "first_month": first_month, "latest_month": latest_month,
         "checked_on": checked_on}], preserve=())
