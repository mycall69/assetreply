"""가상자산 일봉·원본·커버리지 리포지토리 (T030) — 007 FR-010~FR-012a, FR-022, data-model 5~7절.

일봉은 `(코인, UTC 날짜)` 복합 기본 키 + upsert다 — 같은 구간을 다시 받아도 행이 늘지 않아 중단 뒤
이어받기가 안전하다 (헌법 원칙 V). 원본은 정규화와 따로, 응답 본문 그대로(마감 전 일봉 포함) 남긴다.
결측은 행이 없는 것으로 표현한다 — 채우지 않는다.

커버리지는 **요청한 구간**이다 — 일봉이 없던 구간도 다시 받으러 가지 않는다(005와 같다). 빠진 구간
판정은 005의 `missing_ranges`를 쓴다.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Sequence
from typing import Final

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.dialect import upsert
from src.db.models import CryptoCoin, CryptoCoverage, CryptoDaily, CryptoRawResponse
from src.ingestion.investing.parse import DailyBar
from src.repository.stock import Range

#: 저장할 때 남기는 출처 이름. 어느 어댑터가 넣었는지 행에서 알 수 있어야 한다.
SOURCE: Final = "investing:historical"
#: 한 질의에 싣는 행 수. 730일 청크가 한 질의에 들어간다.
_CHUNK = 1000


async def store_bars(session: AsyncSession, coin_id: int, bars: Sequence[DailyBar]) -> int:
    """일봉을 넣거나 고친다. 넣은 행 수를 돌려준다. **최초 수집 시각은 보존한다**(upsert 기본값)."""
    rows: list[dict[str, object]] = [{
        "coin_id": coin_id, "day": b.day, "open": b.open, "high": b.high, "low": b.low,
        "close": b.close, "volume": b.volume, "source": SOURCE} for b in bars]
    for start in range(0, len(rows), _CHUNK):
        await upsert(session, CryptoDaily, rows[start:start + _CHUNK])
    return len(rows)


async def store_raw(
    session: AsyncSession, coin_id: int, *, requested_from: dt.date, requested_to: dt.date,
    status_code: int, body: str, received_at: dt.datetime,
) -> None:
    """원본 응답을 그대로 남긴다. 헤더는 받지 않는다 — 사용자 에이전트가 남는다(FR-019)."""
    session.add(CryptoRawResponse(
        coin_id=coin_id, requested_from=requested_from, requested_to=requested_to,
        status_code=status_code, body=body, received_at=received_at))
    await session.flush()


async def bars(
    session: AsyncSession, coin_id: int, start: dt.date, end: dt.date
) -> list[CryptoDaily]:
    """구간의 일봉을 날짜 오름차순으로. 결측일은 행이 없어 날짜가 연속하지 않을 수 있다 — 그것이
    정상이다."""
    return list((await session.execute(
        select(CryptoDaily)
        .where(CryptoDaily.coin_id == coin_id, CryptoDaily.day >= start, CryptoDaily.day <= end)
        .order_by(CryptoDaily.day))).scalars())


async def first_bar_day(
    session: AsyncSession, coin_id: int, start: dt.date | None = None, end: dt.date | None = None
) -> dt.date | None:
    """(구간 안의) 첫 일봉 날짜. 없으면 `None`."""
    stmt = select(func.min(CryptoDaily.day)).where(CryptoDaily.coin_id == coin_id)
    if start is not None:
        stmt = stmt.where(CryptoDaily.day >= start)
    if end is not None:
        stmt = stmt.where(CryptoDaily.day <= end)
    return (await session.execute(stmt)).scalar_one()


async def get_coverage(session: AsyncSession, coin_id: int) -> Range | None:
    row = await session.get(CryptoCoverage, coin_id, populate_existing=True)
    return None if row is None else (row.covered_from, row.covered_through)


async def record_coverage(
    session: AsyncSession, coin_id: int, start: dt.date, end: dt.date
) -> None:
    """수집 구간을 넓힌다. **덮어쓰지 않고 합친다** — 덮어쓰면 앞서 받은 구간을 잊어 다시
    받는다(005와 같다)."""
    current = await get_coverage(session, coin_id)
    if current is not None:
        start, end = min(start, current[0]), max(end, current[1])
    await upsert(session, CryptoCoverage, [
        {"coin_id": coin_id, "covered_from": start, "covered_through": end}], preserve=())


async def record_first_available(session: AsyncSession, coin_id: int, day: dt.date) -> None:
    """출처의 첫 일봉을 기록한다(research R7-10). 이미 더 이른 날이 기록되어 있으면 두지 않는다."""
    coin = await session.get(CryptoCoin, coin_id)
    if coin is not None and (coin.first_available_date is None or day < coin.first_available_date):
        coin.first_available_date = day
        await session.flush()
