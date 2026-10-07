"""가상자산 시뮬레이션 표 (T032) — 007 contracts/rest-api `GET /api/crypto/simulation`.

금액·비율·가격·수량은 모두 **문자열**이다 — JSON `number`는 IEEE 754다(헌법 원칙 VI, 001부터의
규약). 지수 표기 없이 쓴다. 수량은 소수 8자리(FR-026), 시가는 출처 원값 그대로(14자리) — 표시
자릿수는 화면이 정한다(FR-040).

**정상 상태에 값을 두지 않는다.** 매수가 없는 행에는 `tradeFee` 키가 없다 — 0을 넣으면 "수수료 0"과
"매수 없음"을 구별할 수 없다(006과 같은 규약). **받지 못한 구간이 있으면 계산하지 않는다**(202,
FR-013).
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.errors import StartAfterEnd
from src.api.services.crypto_collect import collecting_body
from src.api.services.crypto_simulation import (
    CryptoResult,
    CryptoRowView,
    check_principal_currency,
    prepare,
    require_coin,
    require_start_available,
    source_missing,
    table,
    utc_yesterday,
)
from src.api.services.stock_simulation import parse_principal
from src.api.services.table_rows import parse_period, row_body
from src.config.settings import load_settings
from src.db.models import CryptoCoin
from src.db.session import get_session
from src.repository import crypto_daily

router = APIRouter(prefix="/api/crypto", tags=["crypto"])

Json = dict[str, object]


def money(value: Decimal) -> str:
    """금액 문자열 — 지수 표기 없이, 계산이 남긴 뒷자리 0 없이."""
    return format(value.normalize(), "f")


def quantity(value: Decimal) -> str:
    """수량 문자열 — 소수 8자리 고정(FR-026)."""
    return format(value, ".8f")


def row_json(view: CryptoRowView) -> Json:
    row = view.row
    body: Json = {
        "date": row.date.isoformat(),
        "kind": "month_first",
        # 출처 원값 그대로 — 소수 14자리(research R7-3)
        "openPrice": format(row.open_price, "f"),
        "boughtQuantity": quantity(row.bought_quantity),
        "heldQuantity": quantity(row.held_quantity),
        "cash": money(row.cash),
        "principal": format(view.principal, "f"),
        "balance": money(row.balance),
        "profit": format(view.profit, "f"),
        "returnRate": format(view.return_rate, "f"),
    }
    if row.trade_fee is not None:
        body["tradeFee"] = money(row.trade_fee)
    # 012 FR-008 — 지금의 ◇(그 달 1일 결측)는 싣지 않는다. 월 단위는 옮겨진 기준일 표시가, 일 단위는
    # 결측 구간 행이 대신한다.
    if view.balance_krw is not None:
        body["balanceKrw"] = format(view.balance_krw, "f")
    # 그 행의 평가에 쓴 환율과 **실제로 쓴 날짜**(006 FR-041c) — 잠정 환율만 있으면 이전
    # 확정일이다(analyze C1)
    if view.fx_rate is not None and view.fx_rate_date is not None:
        body["fxRate"] = format(view.fx_rate, "f")
        body["fxRateDate"] = view.fx_rate_date.isoformat()
    return body


def summary_json(result: CryptoResult, principal: Decimal) -> Json:
    """요약은 **마지막 일봉의 평가**다 — 표의 마지막 행이 아니다(005와 같은 이유)."""
    latest = result.latest
    body: Json = {
        "principal": format(principal, "f"),
        "profit": format(latest.profit, "f") if latest else "0",
        "returnRate": format(latest.return_rate, "f") if latest else "0",
        "asOf": result.as_of.isoformat(),
        "isFinal": result.is_final,
        "boughtOn": result.bought_on.isoformat(),
    }
    if result.principal_krw is not None:
        body["principalKrw"] = format(result.principal_krw, "f")
    # 012 FR-018(US5) — 보드의 현재 잔고: 기준일의 원화 총자산(잔고 + 예수금). 투자 수익을 만든 같은
    # 평가값이다(주식과 같다).
    basis = result.principal_krw if result.principal_krw is not None else principal
    body["totalKrw"] = format((latest.profit if latest else Decimal("0")) + basis, "f")
    return body


def coin_json(coin: CryptoCoin) -> Json:
    return {"coinId": int(coin.id), "symbol": coin.symbol, "name": coin.name_en,
            "nameKo": coin.name_ko, "currency": coin.quote_currency}


def calculation_end(end: dt.date | None) -> dt.date:
    """계산 끝 — 요청한 끝과 UTC 어제 중 이른 날. 마감 전 일봉은 저장하지 않으므로 그 뒤를 요구할 수
    없다(FR-022)."""
    yesterday = utc_yesterday()
    return yesterday if end is None else min(end, yesterday)


@router.get("/simulation", response_model=None)
async def get_simulation(
    session: Annotated[AsyncSession, Depends(get_session)],
    coin_id: Annotated[int, Query(alias="coinId")],
    start: Annotated[dt.date, Query()],
    principal: Annotated[str, Query(description="투자 원금. 문자열")],
    principal_currency: Annotated[str, Query(alias="principalCurrency")],
    end: Annotated[dt.date | None, Query()] = None,
    before: Annotated[dt.date | None, Query(description="이 날짜 미만만 반환")] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 30,
    period: Annotated[str | None,
                      Query(description="daily · weekly · monthly — 기본 daily(012)")] = None,
) -> Json | JSONResponse:
    """시뮬레이션을 실행하고 표 한 페이지를 돌려준다."""
    amount = parse_principal(principal)
    unit = parse_period(period)
    finish = calculation_end(end)
    if start > finish:
        raise StartAfterEnd(finish)
    coin = await require_coin(session, coin_id)
    # 막힌 조합이면 수집도 계산도 하지 않는다. 시작 가능 날짜 판정도 **수집보다 먼저다**.
    check_principal_currency(principal_currency, coin.quote_currency)
    require_start_available(coin, start)
    collecting = await collecting_body(
        session, coin, start=start, end=finish, settings=load_settings())
    if collecting is not None:
        return JSONResponse(status_code=202, content=collecting)

    prepared = await prepare(session, coin, start=start, end=finish, principal=amount,
                             principal_currency=principal_currency)
    result = prepared.result
    # 012 FR-004b — 일 단위의 결측 구간 행은 시계열과 같은 입력(시작 월 1일부터, 같은 커버리지)으로
    # 구한다.
    missing = (source_missing(start.replace(day=1), finish, set(result.quote_dates),
                              await crypto_daily.get_coverage(session, int(coin.id)))
               if unit == "daily" else [])
    shown = table(result, unit=unit, end=finish, before=before, limit=limit, missing=missing)
    body: Json = {
        "coin": coin_json(coin),
        # 설정은 언제든 바뀐다. 결과만 남으면 어느 조건의 수치인지 알 수 없다(FR-033).
        "condition": {
            "start": start.isoformat(), "principal": format(amount, "f"),
            "principalCurrency": principal_currency,
            "tradeFeeRate": format(prepared.settings.trade_fee_rate, "f"),
        },
        "summary": summary_json(result, amount),
        "period": unit,
        "rows": [row_body(r, row_json) for r in shown.rows],
        "hasMore": shown.has_more,
        "oldestReturned": shown.oldest.isoformat() if shown.oldest else None,
    }
    if result.exchange is not None:
        body["exchange"] = {
            "rate": format(result.exchange.rate, "f"),
            "rateDate": result.exchange.rate_date.isoformat(),
            "kind": "cash_buy_discounted",
            "spreadDiscount": format(result.exchange.spread_discount, "f"),
        }
    return body
