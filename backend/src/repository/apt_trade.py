"""거래·원본·커버리지 (009 T022, FR-008~FR-010, FR-019, data-model 3~5절, research R9-4·R9-5).

- **거래는 사건이다** — 키는 (시·군·구, 계약일, 단지, 동, 층, 면적, 금액, 응답 안 순번)이고(R9-4),
  같은 계약
  월을 다시 받으면 바뀔 수 있는 필드(거래 유형·해제·사라짐)만 고친다. `ingested_at`은 처음 받은 시각
  그대로다
- 다시 받은 응답에서 사라진 행은 지우지 않고 `missing_since`(`absent`) — 원본에 근거가 남고 집계에서
  뺀다. 다시
  나타나면 표시를 지운다. 시·군·구 코드가 사라지면 그 코드의 행은 `region_retired`다
- 원본은 같은 요청의 마지막 원본과 본문 해시가 같으면 새 행을 만들지 않는다(data-model 4절)
- 커버리지의 `checked_on`은 **성공했을 때만** 바뀐다 — 실패한 달은 이 모듈을 부르지 않는다
"""

from __future__ import annotations

import datetime as dt
import hashlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.dialect import upsert
from src.db.models import AptRawResponse, AptTrade, AptTradeCoverage
from src.ingestion.protocols import AptTrade as SourceTrade

SOURCE = "molit:aptdev"
ABSENT = "absent"
REGION_RETIRED = "region_retired"
#: 다시 받기에서 바뀌지 않는 열 — upsert가 덮지 않는다.
_KEEP = ("lawd_cd", "deal_ym", "deal_date", "apt_seq", "umd_code", "jibun", "apt_name", "apt_dong",
         "floor", "excl_area", "amount", "occurrence", "source", "ingested_at")

Key = tuple[dt.date, str, str, int, Decimal, Decimal, int]


@dataclass(frozen=True, slots=True)
class MonthChange:
    """다시 받기에서 바뀐 수(사건 `apt_trade_revised`)."""

    added: int
    cancelled: int
    missing: int

    @property
    def any(self) -> bool:
        return bool(self.added or self.cancelled or self.missing)


@dataclass(frozen=True, slots=True)
class CoverageMark:
    state: str
    checked_on: dt.date
    trade_rows: int


def _key(trade: SourceTrade | AptTrade) -> Key:
    return (trade.deal_date, trade.apt_seq, trade.apt_dong, int(trade.floor),
            Decimal(trade.excl_area), Decimal(trade.amount), int(trade.occurrence))


async def store_raw(session: AsyncSession, *, endpoint: str, request_ref: str, status: int,
                    result_code: str | None, body: str, now: dt.datetime) -> bool:
    """원본을 남긴다. 같은 요청의 마지막 원본과 본문이 같으면 남기지 않고 False."""
    digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
    last = (await session.execute(
        select(AptRawResponse.body_sha256)
        .where(AptRawResponse.endpoint == endpoint, AptRawResponse.request_ref == request_ref)
        .order_by(AptRawResponse.received_at.desc(), AptRawResponse.id.desc()).limit(1))
    ).scalar_one_or_none()
    if last == digest:
        return False
    session.add(AptRawResponse(endpoint=endpoint, request_ref=request_ref, status_code=status,
                               result_code=result_code, body=body, body_sha256=digest,
                               received_at=now))
    await session.flush()
    return True


async def store_month(session: AsyncSession, lawd_cd: str, ym: str,
                      trades: Sequence[SourceTrade], *, now: dt.datetime,
                      revisit: bool) -> MonthChange:
    """한 계약 월의 거래를 맞춘다 — 새 거래는 더하고, 바뀐 필드는 고치고, 사라진 행은 표시한다.

    `revisit`은 전에 받은 달을 다시 받았는가다 — 처음 받은 달의 거래는 "더함"으로 세지 않는다.
    """
    existing = {_key(row): row for row in (await session.execute(select(AptTrade).where(
        AptTrade.lawd_cd == lawd_cd, AptTrade.deal_ym == ym))).scalars()}
    fresh: list[dict[str, object]] = []
    cancelled = 0
    seen: set[Key] = set()
    for trade in trades:
        key = _key(trade)
        seen.add(key)
        row = existing.get(key)
        if row is None:
            fresh.append({
                "lawd_cd": trade.lawd_cd, "deal_ym": trade.deal_ym, "deal_date": trade.deal_date,
                "apt_seq": trade.apt_seq, "umd_code": trade.umd_code, "jibun": trade.jibun,
                "apt_name": trade.apt_name, "apt_dong": trade.apt_dong, "floor": trade.floor,
                "excl_area": trade.excl_area, "amount": Decimal(trade.amount),
                "occurrence": trade.occurrence, "dealing_type": trade.dealing_type,
                "cancelled": trade.cancelled, "cancelled_on": trade.cancelled_on,
                "missing_since": None, "missing_reason": None, "source": SOURCE,
                "ingested_at": now})
            continue
        if trade.cancelled and not row.cancelled:
            cancelled += 1
        if (row.cancelled, row.cancelled_on, row.dealing_type, row.missing_since) != (
                trade.cancelled, trade.cancelled_on, trade.dealing_type, None):
            row.cancelled, row.cancelled_on = trade.cancelled, trade.cancelled_on
            row.dealing_type = trade.dealing_type
            row.missing_since = row.missing_reason = None
    for start in range(0, len(fresh), 500):
        await upsert(session, AptTrade, fresh[start:start + 500], preserve=_KEEP)
    missing = 0
    for key, row in existing.items():
        if key not in seen and row.missing_since is None:
            row.missing_since, row.missing_reason = now, ABSENT
            missing += 1
    await session.flush()
    return MonthChange(added=len(fresh) if revisit else 0, cancelled=cancelled, missing=missing)


async def record_month(session: AsyncSession, lawd_cd: str, ym: str, *, state: str, rows: int,
                       checked_on: dt.date) -> None:
    await upsert(session, AptTradeCoverage, [{
        "lawd_cd": lawd_cd, "deal_ym": ym, "state": state, "trade_rows": rows,
        "checked_on": checked_on}], preserve=())


async def coverage(session: AsyncSession, lawd_cd: str) -> dict[str, CoverageMark]:
    rows = (await session.execute(select(AptTradeCoverage).where(
        AptTradeCoverage.lawd_cd == lawd_cd).execution_options(populate_existing=True))).scalars()
    return {r.deal_ym: CoverageMark(r.state, r.checked_on, r.trade_rows) for r in rows}


async def retire_lawd(session: AsyncSession, lawd_cd: str, *, now: dt.datetime) -> int:
    """사라진 시·군·구 코드의 거래를 집계에서 뺀다 — 새 코드의 수집이 전체 이력을 다시 받는다(같은
    거래를 두 코드로 두 번 세지 않는다)."""
    result = await session.execute(update(AptTrade).where(
        AptTrade.lawd_cd == lawd_cd, AptTrade.missing_since.is_(None)).values(
        missing_since=now, missing_reason=REGION_RETIRED))
    return int(getattr(result, "rowcount", 0) or 0)


@dataclass(frozen=True, slots=True)
class LatestTrade:
    """단지의 가장 최근 거래 — 단지 행의 이름·지번·법정동을 맞춘다(짝짓기 입력)."""

    apt_seq: str
    apt_name: str
    umd_code: str
    jibun: str
    deal_date: dt.date
    build_year: int | None


async def latest_by_complex(session: AsyncSession, lawd_cd: str,
                            build_years: Mapping[str, int] | None = None, *,
                            umd_code: str | None = None) -> list[LatestTrade]:
    """그 시·군·구(또는 그 동)의 단지(`apt_seq`)마다 가장 최근 거래. 사라진 코드의 거래는 뺀다."""
    query = (select(AptTrade.apt_seq, AptTrade.apt_name, AptTrade.umd_code, AptTrade.jibun,
                    AptTrade.deal_date)
             .where(AptTrade.lawd_cd == lawd_cd,
                    (AptTrade.missing_reason.is_(None))
                    | (AptTrade.missing_reason != REGION_RETIRED)))
    if umd_code is not None:
        query = query.where(AptTrade.umd_code == umd_code)
    rows = (await session.execute(query.order_by(AptTrade.deal_date, AptTrade.id))).all()
    latest: dict[str, LatestTrade] = {}
    years = build_years or {}
    for seq, name, umd, jibun, day in rows:
        latest[seq] = LatestTrade(seq, name, umd, jibun, day, years.get(seq))
    return list(latest.values())


@dataclass(frozen=True, slots=True)
class AreaTrade:
    deal_date: dt.date
    excl_area: Decimal
    amount: int
    cancelled: bool


async def complex_trades(session: AsyncSession, apt_seq: str, *,
                         include_cancelled: bool = False) -> list[AreaTrade]:
    """단지의 거래(계약일 순). 사라진 행은 늘 빼고, 해제는 기본으로 뺀다(FR-008)."""
    query = select(AptTrade.deal_date, AptTrade.excl_area, AptTrade.amount,
                   AptTrade.cancelled).where(AptTrade.apt_seq == apt_seq,
                                             AptTrade.missing_since.is_(None))
    if not include_cancelled:
        query = query.where(AptTrade.cancelled.is_(False))
    rows = (await session.execute(query.order_by(AptTrade.deal_date))).all()
    return [AreaTrade(day, Decimal(area), int(amount), bool(cancel))
            for day, area, amount, cancel in rows]
