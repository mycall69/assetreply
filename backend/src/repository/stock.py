"""종목과 수집 구간 리포지토리 (T015) — 005 FR-043~046.

upsert는 `db/dialect.py`의 헬퍼만 호출한다. 방언 구문을 직접 쓰면 헌법 위반이다.

`stock_coverage`를 `fx_coverage`와 합치지 않는다 — 그쪽은 통화 단위이고 여기는 종목
단위라, 한 테이블에 섞으면 키 설계가 둘 다 어색해지고 FX 질의가 주식 행을 걸러내야
한다 (research R5-7).
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Collection

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.dialect import upsert
from src.db.models import Stock, StockCoverage

#: 커버리지 구간. `(시작, 끝)` 둘 다 포함이다.
Range = tuple[dt.date, dt.date]

_ONE_DAY = dt.timedelta(days=1)


async def find_stock(
    session: AsyncSession, market: str, symbol: str
) -> Stock | None:
    return (await session.execute(
        select(Stock).where(Stock.market == market, Stock.symbol == symbol)
    )).scalar_one_or_none()


async def find_us_stock(session: AsyncSession, symbol: str) -> Stock | None:
    """미국 종목을 **티커로** 찾는다. 거래소는 보지 않는다 (006 FR-030a).

    005는 시세 출처의 거래소 코드로 시장을 정했고(`PCX` → `AMEX`), 목록 출처는 같은 ETF를
    `NYSE`로 줄 수 있다. `(시장, 심볼)`로 찾으면 같은 종목이 둘이 된다. 시세 출처는 미국 종목을
    티커만으로 조회하므로 거래소가 달라도 시세는 같다.
    """
    return (await session.execute(
        select(Stock).where(Stock.symbol == symbol,
                            Stock.market.in_(("NYSE", "NASDAQ", "AMEX")))
        .order_by(Stock.id).limit(1))).scalar_one_or_none()


async def record_first_trade_date(session: AsyncSession, stock_id: int, day: dt.date) -> None:
    """시세 출처의 첫 거래일을 **비었을 때만** 쓴다 — 덮어쓰지 않는다 (014 FR-033, research R14-26).

    표시 전용이다. 시작일 하한(`first_available_date`)에는 쓰지 않는다 — 쓰면 메뉴의 시작일 거절이
    수집 전에 일어나 거절 날짜가 바뀐다.
    """
    await session.execute(
        update(Stock)
        .where(Stock.id == stock_id, Stock.first_trade_date.is_(None))
        .values(first_trade_date=day))


async def first_trade_dates(
    session: AsyncSession, symbols: Collection[str]
) -> dict[tuple[str, str], dt.date]:
    """시세 식별자별 저장된 첫 거래일 (014 FR-033). 검색 응답이 쓴다 — **출처를 부르지 않는다**.

    심볼로만 거른다 — 미국 종목은 시장 없이 티커로 맞춰야 한다(006 FR-030a). 고르기는
    부르는 쪽 몫이다.
    """
    if not symbols:
        return {}
    rows = await session.execute(
        select(Stock.market, Stock.symbol, Stock.first_trade_date)
        .where(Stock.symbol.in_(set(symbols)), Stock.first_trade_date.is_not(None)))
    return {(market, symbol): day for market, symbol, day in rows.tuples() if day is not None}


async def ensure_stock(
    session: AsyncSession,
    *,
    market: str,
    symbol: str,
    name: str,
    currency: str,
    first_available_date: dt.date | None = None,
) -> Stock:
    """종목을 확보한다. 사용자가 고른 것만 들어온다 (research R5-2).

    `first_available_date`는 수집 중 발견되므로, 알게 된 뒤에만 채운다. 모르는 값을
    오늘로 채우면 상장 이전 판정(FR-005)이 틀린다.
    """
    existing = await find_stock(session, market, symbol)
    if existing is not None:
        if first_available_date is not None and existing.first_available_date is None:
            existing.first_available_date = first_available_date
            await session.flush()
        return existing

    await upsert(session, Stock, [{
        "market": market, "symbol": symbol, "name": name, "currency": currency,
        "first_available_date": first_available_date,
    }])
    await session.flush()
    found = await find_stock(session, market, symbol)
    if found is None:  # pragma: no cover — upsert 직후라 있어야 한다
        raise RuntimeError(f"종목을 만들지 못했습니다: {market}:{symbol}")
    return found


async def get_coverage(session: AsyncSession, stock_id: int) -> Range | None:
    """종목의 수집 구간. 기록이 없으면 `None`이다."""
    row = (await session.execute(
        select(StockCoverage).where(StockCoverage.stock_id == stock_id)
    )).scalar_one_or_none()
    if row is None:
        return None
    return (row.covered_from, row.covered_through)


async def record_coverage(
    session: AsyncSession, stock_id: int, start: dt.date, end: dt.date
) -> None:
    """수집 구간을 넓힌다.

    **덮어쓰지 않고 합친다.** 덮어쓰면 앞서 받은 구간을 잊어 다음 실행에서 다시
    받게 되고, 재개(FR-045)가 성립하지 않는다.
    """
    current = await get_coverage(session, stock_id)
    if current is not None:
        start = min(start, current[0])
        end = max(end, current[1])
    await upsert(session, StockCoverage, [{
        "stock_id": stock_id, "covered_from": start, "covered_through": end,
    }], preserve=())


def missing_ranges(
    covered: Range | None, start: dt.date, end: dt.date
) -> list[Range]:
    """요청 구간에서 **아직 받지 않은 부분**만 돌려준다 (FR-044).

    이미 받은 구간을 다시 받으면 출처 호출을 낭비하고, 출처가 막혔을 때 이미 가진
    데이터로도 답하지 못하게 된다.

    커버리지는 연속 구간 하나다. 그래서 빠진 부분은 앞·뒤 최대 둘이다. 구멍이 여럿인
    상태를 만들지 않는 이유는 중단·재개가 항상 구간의 끝에서 일어나기 때문이다.
    """
    if start > end:
        return []
    if covered is None:
        return [(start, end)]

    covered_from, covered_through = covered
    if covered_through < start or covered_from > end:
        # 겹치지 않는다. 요청 구간 전부가 빠져 있다.
        return [(start, end)]

    gaps: list[Range] = []
    if start < covered_from:
        gaps.append((start, covered_from - _ONE_DAY))
    if end > covered_through:
        gaps.append((covered_through + _ONE_DAY, end))
    return gaps
