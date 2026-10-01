"""시뮬레이션 표 (T038, T039) — 005 contracts/rest-api.

금액·비율은 모두 **문자열**로 직렬화한다. JSON `number`는 IEEE 754라 `Decimal`
정밀도가 손실되며, 이는 헌법 원칙 VI를 API 경계에서 무력화한다 (001이 세운 규약).

**정상 상태에 값을 두지 않는다.** 월 행의 배당 칸은 키 자체를 생략한다 — 0을 넣으면
"배당이 0원"과 "배당이 없음"을 구별할 수 없다 (FR-026).
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal, InvalidOperation
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.errors import InvalidQuery
from src.api.services.stock_simulation import (
    SimulationResult,
    page,
    run_simulation,
)
from src.db.session import get_session
from src.ingestion.yahoo.errors import StockSymbolNotFound
from src.repository.stock import find_stock
from src.repository.stock_setting import get_settings
from src.simulation.reinvest import Row

router = APIRouter(prefix="/api/stocks", tags=["stocks"])

Json = dict[str, object]

#: 원금으로 고를 수 있는 통화 (FR-003).
PRINCIPAL_CURRENCIES = ("KRW", "USD", "JPY", "EUR")


def parse_principal(raw: str) -> Decimal:
    """원금을 `Decimal`로 읽는다.

    문자열로 받는 이유는 응답과 같다 — 경계에서 정밀도를 잃지 않는다. 숫자가 아니면
    **조용히 0으로 떨어뜨리지 않는다.** 0이면 수익률이 0으로 나오는데 오류가 없다.
    """
    try:
        amount = Decimal(raw)
    except (InvalidOperation, ValueError) as exc:
        raise InvalidQuery(f"원금이 숫자가 아닙니다: {raw}") from exc
    if amount <= 0:
        raise InvalidQuery("원금은 0보다 커야 합니다.")
    return amount


def row_json(row: Row) -> Json:
    """표 한 행.

    `dividendPerShare`·`dividendYield`는 **배당락 행에만** 넣는다(FR-026). 정상 상태에
    값을 두면 화면이 존재 여부가 아니라 내용을 검사해야 한다.
    """
    body: Json = {
        "date": row.date.isoformat(),
        "kind": row.kind,
        "openPrice": str(row.open_price),
        "boughtShares": row.bought_shares,
        "heldShares": row.held_shares,
        "cash": str(row.cash),
        "principal": str(row.principal),
        "balance": str(row.balance),
        "profit": str(row.profit),
        "returnRate": str(row.return_rate),
    }
    if row.dividend_per_share is not None:
        body["dividendPerShare"] = str(row.dividend_per_share)
    if row.dividend_yield is not None:
        body["dividendYield"] = str(row.dividend_yield)
    return body


def summary_json(result: SimulationResult, principal: Decimal) -> Json:
    """성과 요약 (FR-031).

    `asOf`는 계산이 어느 날짜까지인지다. `isFinal`은 **항상 명시한다** — "확인했고
    아니다"와 "확인하지 않았다"가 구별되어야 한다 (FR-014b).
    """
    latest = result.rows[0] if result.rows else None
    return {
        "principal": str(principal),
        "profit": str(latest.profit if latest else Decimal("0")),
        "returnRate": str(latest.return_rate if latest else Decimal("0")),
        "asOf": result.as_of.isoformat() if result.as_of else "",
        "isFinal": result.is_final,
    }


@router.get("/simulation", response_model=None)
async def get_simulation(
    session: Annotated[AsyncSession, Depends(get_session)],
    market: Annotated[str, Query()],
    symbol: Annotated[str, Query()],
    start: Annotated[dt.date, Query()],
    principal: Annotated[str, Query(description="투자 원금. 문자열")],
    principal_currency: Annotated[str, Query(alias="principalCurrency")],
    reinvest: Annotated[bool, Query()] = True,
    end: Annotated[dt.date | None, Query()] = None,
    before: Annotated[dt.date | None, Query(description="이 날짜 미만만 반환")] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 30,
) -> Json:
    """시뮬레이션을 실행하고 표 한 페이지를 돌려준다."""
    if principal_currency not in PRINCIPAL_CURRENCIES:
        raise InvalidQuery(
            f"원금 통화는 {' · '.join(PRINCIPAL_CURRENCIES)} 중 하나여야 합니다: "
            f"{principal_currency}")
    amount = parse_principal(principal)

    stock = await find_stock(session, market, symbol)
    if stock is None:
        raise StockSymbolNotFound(f"알 수 없는 종목입니다: {market}:{symbol}")

    # 끝은 기본적으로 어제다. 오늘 시세는 장중에 바뀌므로 재현성이 깨진다.
    finish = end or (dt.date.today() - dt.timedelta(days=1))

    settings = await get_settings(session)
    result = await run_simulation(
        session, int(stock.id),
        start=start, end=finish, principal=amount,
        currency=stock.currency, reinvest=reinvest,
        fee_rate=settings.trade_fee_rate, tax_rate=settings.dividend_tax_rate,
        listed_on=stock.first_available_date)

    rows, has_more = page(result.rows, before, limit)

    return {
        "stock": {
            "market": stock.market, "symbol": stock.symbol,
            "name": stock.name, "currency": stock.currency,
        },
        # FR-018 — 설정은 언제든 바뀐다. 결과만 남으면 어느 조건의 수치인지 알 수 없다.
        "condition": {
            "start": start.isoformat(),
            "principal": str(amount),
            "principalCurrency": principal_currency,
            "reinvest": reinvest,
            "tradeFeeRate": str(settings.trade_fee_rate),
            "dividendTaxRate": str(settings.dividend_tax_rate),
        },
        "summary": summary_json(result, amount),
        "rows": [row_json(r) for r in rows],
        "hasMore": has_more,
        "oldestReturned": rows[-1].date.isoformat() if rows else None,
    }
