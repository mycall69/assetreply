"""시뮬레이션 표 (T038, T039) — 005 contracts/rest-api.

금액·비율은 모두 **문자열**로 직렬화한다. JSON `number`는 IEEE 754라 `Decimal`
정밀도가 손실되며, 이는 헌법 원칙 VI를 API 경계에서 무력화한다 (001이 세운 규약).

**정상 상태에 값을 두지 않는다.** 월 행의 배당 칸은 키 자체를 생략한다 — 0을 넣으면
"배당이 0원"과 "배당이 없음"을 구별할 수 없다 (FR-026).
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.services.stock_collect import collecting_body
from src.api.services.stock_simulation import (
    ConvertedRow,
    SimulationResult,
    check_principal_currency,
    page,
    parse_principal,
    prepare,
    require_start_available,
    require_stock,
)
from src.db.session import get_session

router = APIRouter(prefix="/api/stocks", tags=["stocks"])

Json = dict[str, object]

def row_json(converted: ConvertedRow) -> Json:
    """표 한 행.

    `dividendPerShare`·`dividendYield`는 **배당락 행에만** 넣는다(FR-026). 정상 상태에
    값을 두면 화면이 존재 여부가 아니라 내용을 검사해야 한다.
    """
    row = converted.row
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
    # 010 FR-028 — 잔고를 평가한 원주가 종가. 계산이 만든 행에는 늘 있다.
    if row.close_price is not None:
        body["closePrice"] = str(row.close_price)
    if row.dividend_per_share is not None:
        body["dividendPerShare"] = str(row.dividend_per_share)
    if row.dividend_yield is not None:
        body["dividendYield"] = str(row.dividend_yield)
    # 006 FR-059 — 같은 규약이다. 해당이 없으면 키를 두지 않는다(세금 0과 세금 없음을 구별한다).
    if row.dividend_tax is not None:
        body["dividendTax"] = str(row.dividend_tax)
    if row.trade_fee is not None:
        body["tradeFee"] = str(row.trade_fee)
    # 006 FR-067 — 배당락 행의 배당금 총액(세전·세후, 종목 통화). 같은 규약이다.
    if row.dividend_total is not None:
        body["dividendTotal"] = str(row.dividend_total)
    if row.dividend_total_net is not None:
        body["dividendTotalNet"] = str(row.dividend_total_net)
    # 006 FR-066 — 해외 종목이면 잔고의 KRW 평가. `balance`는 종목 통화로 남는다.
    if converted.balance_krw is not None:
        body["balanceKrw"] = str(converted.balance_krw)
    # FR-041c — 그 행의 평가 환산에 쓴 환율과 **실제로 쓴 날짜**. 기준일과 다를 수 있다.
    if converted.fx_rate is not None and converted.fx_rate_date is not None:
        body["fxRate"] = str(converted.fx_rate)
        body["fxRateDate"] = converted.fx_rate_date.isoformat()
    return body


def summary_json(result: SimulationResult, principal: Decimal) -> Json:
    """성과 요약 (FR-031).

    `asOf`는 계산이 어느 날짜까지인지다. `isFinal`은 **항상 명시한다** — "확인했고
    아니다"와 "확인하지 않았다"가 구별되어야 한다 (FR-014b).

    006 FR-068 — `profit`·`returnRate`는 원금 통화와 관계없이 KRW다. 원금 통화가 KRW가 아니면
    `principalKrw`(첫 매수일 매매기준율로 평가한 원금)를 함께 싣는다 — 수익률의 분모다.
    """
    # **표의 마지막 행이 아니라 마지막 거래일의 상태다.** 표에서 가져오면 "어제
    # 기준"이라 적어 두고 그 달 첫 거래일의 수치를 보여주게 된다 — 최대 한 달이
    # 어긋나는데 숫자는 그럴듯하다.
    latest = result.latest.row if result.latest is not None else None
    body: Json = {
        "principal": str(principal),
        "profit": str(latest.profit if latest else Decimal("0")),
        "returnRate": str(latest.return_rate if latest else Decimal("0")),
        "asOf": result.as_of.isoformat() if result.as_of else "",
        "isFinal": result.is_final,
    }
    if result.principal_krw is not None:
        body["principalKrw"] = str(result.principal_krw)
    return body


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
) -> Json | JSONResponse:
    """시뮬레이션을 실행하고 표 한 페이지를 돌려준다."""
    check_principal_currency(principal_currency)
    amount = parse_principal(principal)

    # 끝은 기본적으로 어제다. 오늘 시세는 장중에 바뀌므로 재현성이 깨진다.
    finish = end or (dt.date.today() - dt.timedelta(days=1))

    # **받지 못한 구간이 있으면 계산하지 않는다**(FR-049). 받은 만큼만 계산한
    # 수익률은 값이 멀쩡해 보이지만 틀렸고, 사용자는 그것을 최종 결과로 읽는다.
    stock = await require_stock(session, market, symbol)
    # 006 FR-050 — 막힌 조합이면 수집도 계산도 하지 않는다. 수집보다 먼저 본다.
    check_principal_currency(principal_currency, stock.currency)
    # 상장 이전 판정이 **수집보다 먼저다.** 뒤로 미루면 상장 수십 년 전부터의
    # 구간이 미수집으로 보여 수집이 시작되고, 받을 수 없는 데이터를 기다리게 된다.
    await require_start_available(session, stock, start)
    # 006 — 주식 시세와 환율을 **함께** 본다. 둘 중 하나라도 비면 202다 (FR-045).
    collecting = await collecting_body(session, stock, start=start, end=finish)
    if collecting is not None:
        return JSONResponse(status_code=202, content=collecting)

    # **차트와 같은 함수를 같은 입력으로 부른다.** 각 라우트가 따로 조립하면 한쪽만
    # 설정이나 환율 적용을 빠뜨려도 오류 없이 다른 숫자가 나온다 (SC-032).
    prepared = await prepare(
        session, market=market, symbol=symbol, start=start, end=finish,
        principal=amount, principal_currency=principal_currency,
        reinvest=reinvest)
    stock, settings, result = prepared.stock, prepared.settings, prepared.result

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
            # 006 FR-055 — 그 종목에 **적용한** 세율(국내 또는 해외).
            "dividendTaxRate": str(prepared.dividend_tax_rate),
        },
        "summary": summary_json(result, amount),
        **({"exchange": {
            "rate": str(result.exchange.rate),
            "rateDate": result.exchange.rate_date.isoformat(),
            "kind": "cash_buy_discounted",
            "spreadDiscount": str(result.exchange.spread_discount),
        }} if result.exchange is not None else {}),
        "rows": [row_json(r) for r in rows],
        "hasMore": has_more,
        "oldestReturned": rows[-1].row.date.isoformat() if rows else None,
    }
