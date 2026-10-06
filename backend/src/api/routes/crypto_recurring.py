"""가상자산 적립식 경로 (011 T038) — contracts/rest-api §2. FR-002, FR-017~FR-021.

일시금 경로(`/api/crypto/simulation`)와 **따로 둔다**(research R11-10) — 일시금의 조회 문자열과 응답
모양은 기존 테스트가 정확히 고정한다. 검증·수집 판정 함수는 일시금과 같은 것을 같은 순서로 부른다 —
규칙이 갈라지지 않는다. 계산 끝도 일시금 라우트의 `calculation_end`(min(`end`, UTC 어제))다.

금액·비율·가격·수량은 모두 **문자열**이다(헌법 원칙 VI). 수량은 소수 8자리, 시가는 출처 원값
그대로다 (007과 같다). 해당이 없으면 키를 두지 않는다 — 0과 "없음"을 구별한다.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.errors import StartAfterEnd
from src.api.routes.crypto_simulation import calculation_end, coin_json, money, quantity
from src.api.services.crypto_collect import collecting_body
from src.api.services.crypto_recurring import (
    CryptoRecurringResult,
    CryptoRecurringView,
    PreparedCryptoRecurring,
    prepare_recurring,
    table,
)
from src.api.services.crypto_simulation import (
    check_principal_currency,
    require_coin,
    require_start_available,
    source_missing,
)
from src.api.services.recurring_series import build_crypto_series
from src.api.services.series_query import DEFAULT_MAX_POINTS
from src.api.services.stock_recurring import parse_amount, parse_frequency
from src.api.services.table_rows import parse_period, row_body
from src.config.settings import load_settings
from src.db.session import get_session
from src.repository import crypto_daily
from src.simulation.money import quantize_rate

router = APIRouter(prefix="/api/crypto", tags=["crypto"])

Json = dict[str, object]


async def _prepare_or_collect(session: AsyncSession, *, coin_id: int, start: dt.date,
                              amount_raw: str, principal_currency: str, frequency_raw: str,
                              end: dt.date | None, daily: bool = False,
                              ) -> PreparedCryptoRecurring | JSONResponse:
    """표와 차트가 **같은 판정·같은 계산**을 쓴다 — 한쪽만 막거나 한쪽만 설정을 빠뜨려도 오류 없이
    다른 숫자가 나온다(005 SC-032)."""
    amount = parse_amount(amount_raw)
    frequency = parse_frequency(frequency_raw)
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
    return await prepare_recurring(
        session, coin, start=start, end=finish, amount=amount,
        principal_currency=principal_currency, frequency=frequency, daily=daily)


def _rate(value: Decimal) -> str:
    """비율·가격·환율 문자열 — 자릿수 그대로(007 일시금 경로와 같다)."""
    return format(value, "f")


def summary_json(result: CryptoRecurringResult, *, pending_after_end: int) -> Json:
    """적립식 보드(FR-012·FR-020). 매수 수수료는 이미 총자산에서 빠져 있다 — 투자 수익은 기준일 매도
    비용만 뺀다. 세금을 모르면(과세 시행 뒤) 비운다 — 0으로 메우지 않는다."""
    latest = result.latest
    sale = result.sale_cost
    after = None if sale.total is None else latest.profit - sale.total
    basis = latest.row.basis_krw
    return {
        "contributed": money(latest.contributed),
        "contributedKrw": money(basis),
        "contributions": latest.row.contributions,
        "pendingAfterEnd": pending_after_end,
        "heldQuantity": quantity(latest.row.held_quantity),
        "pending": money(latest.row.pending),
        "totalKrw": money(latest.total_krw),
        "buyFeeTotal": money(result.buy_fee_total_krw),
        "saleCost": {
            "fee": money(sale.fee), "tax": None if sale.tax is None else money(sale.tax),
            "total": None if sale.total is None else money(sale.total), "taxKind": sale.tax_kind},
        "feeTotal": money(result.buy_fee_total_krw + sale.fee),
        "taxTotal": None if sale.tax is None else money(sale.tax),
        "profit": money(latest.profit),
        "returnRate": _rate(latest.return_rate),
        "profitAfterSale": None if after is None else money(after),
        "returnRateAfterSale": None if after is None or basis == 0
        else _rate(quantize_rate(after / basis)),
        "asOf": result.as_of.isoformat(),
        "isFinal": result.is_final,
    }


def row_json(v: CryptoRecurringView) -> Json:
    """표 한 행. 해당이 없으면 키를 두지 않는다."""
    row = v.row
    body: Json = {
        "date": row.date.isoformat(), "kind": row.kind,
        # 출처 원값 그대로 — 소수 14자리(007 research R7-3)
        "openPrice": _rate(row.open_price),
        "boughtQuantity": quantity(row.bought_quantity),
        "heldQuantity": quantity(row.held_quantity),
        "pending": money(row.pending),
        "contributed": money(v.contributed),
        "contributedKrw": money(row.basis_krw),
        "balance": money(row.balance),
        "profit": money(v.profit),
        "returnRate": _rate(v.return_rate),
    }
    if v.contribution is not None:
        body["contribution"] = money(v.contribution)
    if row.deferred:
        body["deferred"] = [d.isoformat() for d in row.deferred]
    if row.trade_fee is not None:
        body["tradeFee"] = money(row.trade_fee)
    # 012 FR-008 — 지금의 ◇(그 달 1일 결측)는 싣지 않는다. 일 단위는 결측 구간 행이 대신한다.
    if v.balance_krw is not None:
        body["balanceKrw"] = money(v.balance_krw)
    # 평가 환율과 **실제로 쓴 날짜**(006 FR-041c), 원화 원금 납입 행의 환전 환율과 고시일(FR-010)
    if v.fx_rate is not None and v.fx_rate_date is not None:
        body["fxRate"] = _rate(v.fx_rate)
        body["fxRateDate"] = v.fx_rate_date.isoformat()
    if v.exchange_rate is not None and v.exchange_rate_date is not None:
        body["exchangeRate"] = _rate(v.exchange_rate)
        body["exchangeRateDate"] = v.exchange_rate_date.isoformat()
    return body


@router.get("/recurring-simulation", response_model=None)
async def get_recurring_simulation(
    session: Annotated[AsyncSession, Depends(get_session)],
    coin_id: Annotated[int, Query(alias="coinId")],
    start: Annotated[dt.date, Query()],
    amount: Annotated[str, Query(description="한 번 납입액(원금 통화). 문자열")],
    principal_currency: Annotated[str, Query(alias="principalCurrency")],
    frequency: Annotated[str, Query(description="daily · weekly · monthly · yearly")],
    end: Annotated[dt.date | None, Query()] = None,
    before: Annotated[dt.date | None, Query(description="이 날짜 미만만 반환")] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 30,
    period: Annotated[str | None,
                      Query(description="daily · weekly · monthly — 기본 daily(012)")] = None,
) -> Json | JSONResponse:
    """적립식을 실행하고 표 한 쪽을 돌려준다."""
    unit = parse_period(period)
    prepared = await _prepare_or_collect(
        session, coin_id=coin_id, start=start, amount_raw=amount,
        principal_currency=principal_currency, frequency_raw=frequency, end=end)
    if isinstance(prepared, JSONResponse):
        return prepared
    result = prepared.result
    finish = calculation_end(end)
    # 012 FR-004b — 결측 구간 행은 시계열과 같은 입력(시작일부터, 같은 커버리지)으로 구한다.
    missing = (source_missing(start, finish, set(result.quote_dates),
                              await crypto_daily.get_coverage(session, int(prepared.coin.id)))
               if unit == "daily" else [])
    shown = table(result, unit=unit, end=finish, before=before, limit=limit, missing=missing)
    return {
        "coin": coin_json(prepared.coin),
        # 설정은 언제든 바뀐다. 결과만 남으면 어느 조건의 수치인지 알 수 없다(007 FR-033).
        "condition": {
            "mode": "recurring", "start": start.isoformat(),
            "amount": format(parse_amount(amount), "f"), "principalCurrency": principal_currency,
            "frequency": parse_frequency(frequency),
            "tradeFeeRate": _rate(prepared.settings.trade_fee_rate),
        },
        "summary": summary_json(result, pending_after_end=result.pending_after_end),
        "period": unit,
        "rows": [row_body(r, row_json) for r in shown.rows],
        "hasMore": shown.has_more,
        "oldestReturned": shown.oldest.isoformat() if shown.oldest else None,
    }


@router.get("/recurring-simulation/series", response_model=None)
async def get_recurring_series(
    session: Annotated[AsyncSession, Depends(get_session)],
    coin_id: Annotated[int, Query(alias="coinId")],
    start: Annotated[dt.date, Query()],
    amount: Annotated[str, Query()],
    principal_currency: Annotated[str, Query(alias="principalCurrency")],
    frequency: Annotated[str, Query()],
    end: Annotated[dt.date | None, Query()] = None,
    max_points: Annotated[int, Query(alias="maxPoints", ge=2)] = DEFAULT_MAX_POINTS,
) -> Json | JSONResponse:
    """표와 같은 조건으로 일봉마다의 시계열을 돌려준다."""
    prepared = await _prepare_or_collect(
        session, coin_id=coin_id, start=start, amount_raw=amount,
        principal_currency=principal_currency, frequency_raw=frequency, end=end, daily=True)
    if isinstance(prepared, JSONResponse):
        return prepared
    coin = prepared.coin
    series = build_crypto_series(
        prepared.result, start=start, end=calculation_end(end),
        covered=await crypto_daily.get_coverage(session, int(coin.id)), max_points=max_points)
    return {
        "from": series.start.isoformat(),
        "to": series.end.isoformat(),
        "principalCurrency": principal_currency,
        "basisCurrency": "KRW",
        # 가격은 그 일봉의 시가, 통화는 코인의 **시세 통화**다(010 — 원금이 KRW여도 환산하지
        # 않는다).
        "priceKind": "crypto_open",
        "priceCurrency": coin.quote_currency,
        "downsampled": series.downsampled,
        "algorithm": "lttb",
        "sourcePointCount": series.source_point_count,
        "points": [
            {"date": p.date.isoformat(), "balance": money(p.balance),
             "returnRate": _rate(p.return_rate), "principal": money(p.principal),
             "price": _rate(p.price)}
            for p in series.points],
        # `source_missing` — 받은 구간 안의 출처 결측. 끊어 그린다(007 FR-023)
        "gaps": [{"from": g.start.isoformat(), "to": g.end.isoformat(), "reason": g.reason}
                 for g in series.gaps],
    }
