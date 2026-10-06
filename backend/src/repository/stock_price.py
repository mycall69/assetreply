"""시세·배당·분할 리포지토리 (T016) — 005 FR-010b, FR-012, FR-046.

구간 조회는 001의 `repository/fx_rate.series`와 같은 모양이다.

**분할 이벤트는 제공처가 준 그대로 저장하고 다시 읽을 수 있어야 한다.** 제공처를
믿기로 한 이상(FR-010a), 틀렸을 때 되짚을 수단이 이 기록뿐이다 (FR-010b, SC-017).
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.dialect import upsert
from src.db.models import (
    Stock,
    StockDividend,
    StockPrice,
    StockRawResponse,
    StockSplit,
)
from src.ingestion.yahoo.parse import ChartData

#: 저장 시 남기는 출처 이름. 어느 어댑터가 넣었는지 행에서 알 수 있어야 한다.
SOURCE = "yahoo:chart"


async def store_chart(
    session: AsyncSession, stock_id: int, data: ChartData
) -> int:
    """정규화된 시세·배당·분할을 저장한다. 저장한 일봉 행 수를 돌려준다.

    upsert라 같은 구간을 다시 받아도 행이 늘지 않는다 — 중단 후 이어받기가 안전한
    근거다 (헌법 시계열 불변식).
    """
    if data.prices:
        await upsert(session, StockPrice, [{
            "stock_id": stock_id,
            "quote_date": p.quote_date,
            "open_raw": p.open_raw,
            "close_raw": p.close_raw,
            "close_adjusted": p.close_adjusted,
            "source": SOURCE,
        } for p in data.prices])

    if data.dividends:
        # **세전 금액을 저장한다.** 세율은 설정이라 바뀌며, 세후를 저장하면 세율을
        # 바꿨을 때 과거 행이 낡아 FR-017의 재산출이 불가능해진다.
        await upsert(session, StockDividend, [{
            "stock_id": stock_id,
            "ex_date": d.ex_date,
            "amount_per_share": d.amount_per_share,
            "source": SOURCE,
        } for d in data.dividends])

    if data.splits:
        await upsert(session, StockSplit, [{
            "stock_id": stock_id,
            "effective_date": s.effective_date,
            "numerator": s.numerator,
            "denominator": s.denominator,
            "source": SOURCE,
        } for s in data.splits])

    return len(data.prices)


async def store_raw(
    session: AsyncSession,
    *,
    stock_id: int | None,
    kind: str,
    body: str,
    status_code: int,
    requested_from: dt.date | None = None,
    requested_to: dt.date | None = None,
) -> None:
    """원본 응답을 보관한다 (헌법 시계열 불변식 — 원본과 정규화의 분리 저장).

    같은 날짜의 값이 나중에 달라졌을 때 무엇이 언제 들어온 것인지 알 수 없으면
    되짚을 수단이 없다 (FR-046).
    """
    session.add(StockRawResponse(
        stock_id=stock_id, kind=kind, body=body, status_code=status_code,
        requested_from=requested_from, requested_to=requested_to))
    await session.flush()


async def prices(
    session: AsyncSession, stock_id: int, start: dt.date, end: dt.date
) -> list[StockPrice]:
    """구간의 일봉을 날짜 오름차순으로.

    고시가 없는 날은 행 자체가 없으므로 날짜가 연속하지 않는다. 그것이 정상이다 —
    없는 값을 만들어 채우지 않는다 (헌법 원칙 V).
    """
    return list((await session.execute(
        select(StockPrice)
        .where(StockPrice.stock_id == stock_id,
               StockPrice.quote_date >= start,
               StockPrice.quote_date <= end)
        .order_by(StockPrice.quote_date)
    )).scalars())


async def dividends(
    session: AsyncSession, stock_id: int, start: dt.date, end: dt.date
) -> list[StockDividend]:
    """구간의 배당 이벤트를 배당락일 오름차순으로. **세전 금액이다.**"""
    return list((await session.execute(
        select(StockDividend)
        .where(StockDividend.stock_id == stock_id,
               StockDividend.ex_date >= start,
               StockDividend.ex_date <= end)
        .order_by(StockDividend.ex_date)
    )).scalars())


async def splits(
    session: AsyncSession, stock_id: int, start: dt.date, end: dt.date
) -> list[StockSplit]:
    """구간의 분할·병합 이벤트를 적용일 오름차순으로 (FR-010b, SC-017)."""
    return list((await session.execute(
        select(StockSplit)
        .where(StockSplit.stock_id == stock_id,
               StockSplit.effective_date >= start,
               StockSplit.effective_date <= end)
        .order_by(StockSplit.effective_date)
    )).scalars())


async def last_quote_date(
    session: AsyncSession, stock_id: int
) -> dt.date | None:
    """가장 최근 고시일. 시세 단절 판정의 근거다 (FR-014a)."""
    return (await session.execute(
        select(StockPrice.quote_date)
        .where(StockPrice.stock_id == stock_id)
        .order_by(StockPrice.quote_date.desc())
        .limit(1)
    )).scalar_one_or_none()


async def market_last_quote_date(
    session: AsyncSession, stock_id: int, end: dt.date
) -> dt.date | None:
    """그 종목과 **같은 시장**의 종목들(그 종목 포함)이 가진 일봉 가운데 `end` 이하의 가장 늦은
    날짜.

    시세 단절과 휴장을 가르는 근거다(버그 stock-holiday-stale-warning) — 그 시장의 다른 종목이 그
    뒤에 거래했으면 이 종목만 끊긴 것이다.
    """
    market = select(Stock.market).where(Stock.id == stock_id).scalar_subquery()
    return (await session.execute(
        select(func.max(StockPrice.quote_date))
        .join(Stock, Stock.id == StockPrice.stock_id)
        .where(Stock.market == market, StockPrice.quote_date <= end)
    )).scalar_one_or_none()


async def first_quote_date(
    session: AsyncSession, stock_id: int
) -> dt.date | None:
    """가장 이른 고시일. 상장 이전 판정에 쓴다 (FR-005)."""
    return (await session.execute(
        select(StockPrice.quote_date)
        .where(StockPrice.stock_id == stock_id)
        .order_by(StockPrice.quote_date)
        .limit(1)
    )).scalar_one_or_none()
