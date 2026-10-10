"""투자 비교 — 대상 하나의 비교 경로 (013 T026·T049·T091) — spec FR-005~FR-011a, FR-020, research
R13-1·R13-2·R13-18, contracts/rest-api.md 1.

경로마다 짝이 되는 **메뉴 경로와 같은 질의·같은 검증·같은 수집 판정·같은 계산을 같은 차례로**
부른다. 거절은 같은 예외를 그대로 올려 같은 처리기가 같은 본문을 낸다. 202는 메뉴의 수집 본문
그대로다.

200은 계산 한 번으로 메뉴의 요약(메뉴와 같은 함수)·메뉴의 시계열(같은 빌더)·정규화 블록
(`comparison` — 주 값·현재 가치·비용 몫·잠정·환율)을 함께 낸다. 표의 행은 만들지 않는다.

**이력을 쓰지 않는다**(FR-020). 비교는 화면이 대상마다 이 경로를 부르고 끝이다.

반복 2026-10-09 — 단가 등락(`comparison.unitPrice`, data-model 3.2)의 두 값을 그 계산이 이미 가진
값에서 고른다: 주식은 수정주가(메뉴 차트의 주가 선과 같은 `split_restated_close`), 가상자산은 일봉
시가, 예금은 발표 금리, 부동산은 그 달 시세. 차이·등락률은 순수 모듈(`simulation/unit_price`)이
낸다. 메뉴 값은 건드리지 않는다.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Mapping
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.errors import InvalidQuery, StartAfterEnd
from src.api.routes import crypto_recurring as crypto_recurring_routes
from src.api.routes import crypto_series as crypto_series_routes
from src.api.routes import crypto_simulation as crypto_routes
from src.api.routes import deposit_installment as installment_routes
from src.api.routes import deposit_series as deposit_series_routes
from src.api.routes import deposit_simulation as deposit_routes
from src.api.routes import realestate_series as realestate_series_routes
from src.api.routes import stock_recurring as stock_recurring_routes
from src.api.routes import stock_series as stock_series_routes
from src.api.routes import stock_simulation as stock_routes
from src.api.services import crypto_recurring as crypto_recurring_service
from src.api.services import crypto_series as crypto_series_service
from src.api.services import crypto_simulation as crypto_service
from src.api.services import deposit_installment as installment_service
from src.api.services import deposit_series as deposit_series_service
from src.api.services import deposit_simulation as deposit_service
from src.api.services import realestate_series as realestate_series_service
from src.api.services import realestate_simulation as realestate_service
from src.api.services import recurring_series
from src.api.services import stock_recurring as stock_recurring_service
from src.api.services import stock_series as stock_series_service
from src.api.services import stock_simulation as stock_service
from src.api.services.comparison_metrics import FxInfo, Json, comparison_block
from src.api.services.crypto_collect import collecting_body as crypto_collecting
from src.api.services.realestate_lists import get_realestate_now, get_realestate_settings
from src.api.services.stock_collect import collecting_body as stock_collecting
from src.api.services.stock_sale import DOMESTIC_MARKET
from src.api.services.stock_selection import (
    FirstTradeLookup,
    fill_first_trade_date,
    get_first_trade,
    listing_for,
)
from src.config.settings import Settings, load_settings
from src.db.models import Stock
from src.db.session import get_session
from src.repository import crypto_daily
from src.repository.stock import get_coverage
from src.simulation.apt_holding import HoldingResult
from src.simulation.comparison_costs import (
    crypto_costs,
    deposit_costs,
    krw_sum,
    realestate_costs,
    stock_costs,
)
from src.simulation.listing_date import ListingDate, coin_listing_date, stock_listing_date
from src.simulation.split_adjust import split_restated_close
from src.simulation.unit_price import PricePoint, UnitPrice, split_ratio, unit_price
from src.worker.apt_trade_runner import kst_date

router = APIRouter(prefix="/api/comparison", tags=["comparison"])

Session = Annotated[AsyncSession, Depends(get_session)]
#: 014 FR-033 — 상장일을 낼 때 모르는 첫 거래일을 받는 수단.
#: lifespan의 공유 클라이언트가 없으면 `None`이다.
FirstTrade = Annotated[FirstTradeLookup | None, Depends(get_first_trade)]
#: 비교 시계열의 처음 점 수 — 열 선 × 1000점(헌법 원칙 VII 다운샘플링, research R13-2).
DEFAULT_COMPARE_POINTS = 1000
MaxPoints = Annotated[int, Query(alias="maxPoints", ge=2)]


def _decimal(value: object) -> Decimal | None:
    return None if value is None else Decimal(str(value))


def _object(value: object) -> Json:
    assert isinstance(value, dict)
    return value


def _required(source: Json, key: str) -> Decimal:
    value = _decimal(source[key])
    assert value is not None
    return value


def _stock_lump_unit(result: stock_service.SimulationResult, currency: str) -> UnitPrice | None:
    """시작일 단가 = 첫 행(매수일) 종가의 수정주가 — 메뉴 시계열 첫 점의 `price`와 같은
    함수·입력."""
    if not result.rows or result.as_of is None:
        return None
    first = min(c.row.date for c in result.rows)
    opened = result.closes.get(first)
    closed = result.closes.get(result.as_of)
    return unit_price(
        "share", "split_restated_close", currency,
        PricePoint(first, None if opened is None
                   else split_restated_close(opened, first, result.splits)),
        PricePoint(result.as_of, closed, missing=None if closed is not None else "no_price"),
        split_ratio=split_ratio(result.splits, first))


def _stock_recurring_unit(result: stock_recurring_service.RecurringResult,
                          currency: str) -> UnitPrice | None:
    """시작일 단가 = 첫 납입 행 종가의 수정주가(적립식 시계열 첫 점과 같다)."""
    if not result.views or result.latest is None:
        return None
    first = min((v.row for v in result.views), key=lambda r: r.date)
    last = result.latest.row
    return unit_price(
        "share", "split_restated_close", currency,
        PricePoint(first.date, split_restated_close(first.close_price, first.date, result.splits)),
        PricePoint(last.date, last.close_price),
        split_ratio=split_ratio(result.splits, first.date))


def _crypto_lump_unit(result: crypto_service.CryptoResult, currency: str) -> UnitPrice | None:
    """매수한 일봉·기준일 일봉의 시가 — 매수·평가에 쓴 가격."""
    rows = [v.row for v in (result.daily or tuple(result.rows))]
    bought = next((r for r in rows if r.date == result.bought_on), None)
    if bought is None or result.latest is None:
        return None
    last = result.latest.row
    return unit_price("coin", "daily_open", currency, PricePoint(bought.date, bought.open_price),
                      PricePoint(last.date, last.open_price))


def _crypto_recurring_unit(result: crypto_recurring_service.CryptoRecurringResult,
                           currency: str) -> UnitPrice | None:
    """첫 납입 일봉·기준일 일봉의 시가."""
    views = result.daily or tuple(result.views)
    if not views:
        return None
    first = min((v.row for v in views), key=lambda r: r.date)
    last = result.latest.row
    return unit_price("coin", "daily_open", currency, PricePoint(first.date, first.open_price),
                      PricePoint(last.date, last.open_price))


def _rate_unit(rates: Mapping[dt.date, Decimal], latest: dt.date | None, start: dt.date,
               as_of: dt.date) -> UnitPrice:
    """가입 달·기준일 달의 발표 금리. 기준일 달이 미발표면 마지막 발표 달의 금리를 그 달과 함께
    잠정으로 낸다(008 규칙 — 계산이 쓴 그 금리). 발표 기간 안의 빈 달은 값 없음이다(메우지
    않는다)."""
    opened_month = start.replace(day=1)
    opened = rates.get(opened_month)
    month = as_of.replace(day=1)
    if latest is not None and month > latest:
        value = rates.get(latest)
        at = PricePoint(latest, value, provisional=True,
                        missing=None if value is not None else "no_price")
    else:
        value = rates.get(month)
        at = PricePoint(month, value, missing=None if value is not None else "no_price")
    return unit_price("rate", "published_rate", None, PricePoint(opened_month, opened), at)


def _realestate_unit(result: HoldingResult) -> UnitPrice:
    """매입가(매입 달 시세)·평가액(그 달 시세). 지금 시세가 없으면 값 없음이다(메우지 않는다)."""
    window = result.buy_price_window
    start = PricePoint(window.month if window is not None else result.buy_date.replace(day=1),
                       Decimal(result.buy_price),
                       provisional=window is not None and window.provisional,
                       estimated=window is not None and window.estimated)
    summary = result.summary
    if summary.value is None or summary.value_month is None:
        at = PricePoint(summary.as_of.replace(day=1), None, missing="no_trades")
    else:
        at = PricePoint(summary.value_month, Decimal(summary.value),
                        provisional=summary.provisional, estimated=summary.estimated)
    return unit_price("home", "market_price", "KRW", start, at)


async def _stock_listing(
    session: AsyncSession, stock: Stock, first_trade: FirstTradeLookup | None
) -> ListingDate | None:
    """상장일 — 키움 국내 상장일 → 시세 출처 첫 거래일 → 없음 (014 반복 2026-10-10f — FR-033).

    시작일 하한(`first_available_date`)은 쓰지 않는다 — 상장일이 아니다. 키움 상장일이 없고 첫
    거래일을 모르면 **여기서 한 번 받아 둔다** — 저장한 비교·이력 다시 실행은 등록을 거치지 않고,
    이미 받아 둔 종목은 새 수집 청크도 없어 그대로면 늘 "—"였다(사용자 보고 2026-10-10 —
    TQQQ·QLD·SOXL).
    """
    listing = await listing_for(session, stock.market, stock.symbol)
    listed_on = None if listing is None else listing.listed_on
    if listed_on is None:
        await fill_first_trade_date(session, stock, first_trade)
    return stock_listing_date(listed_on, stock.first_trade_date)


def _body(*, target: Json, condition: Json, exchange: Json | None, summary: Json, series: Json,
          comparison: Json) -> Json:
    return {"basisCurrency": "KRW", "target": target, "condition": condition,
            "exchange": exchange, "summary": summary, "series": series,
            "comparison": comparison}


@router.get("/stocks/simulation", response_model=None)
async def compare_stock(
    session: Session,
    first_trade: FirstTrade,
    market: Annotated[str, Query()],
    symbol: Annotated[str, Query()],
    start: Annotated[dt.date, Query()],
    principal: Annotated[str, Query(description="투자 원금. 문자열")],
    principal_currency: Annotated[str, Query(alias="principalCurrency")],
    reinvest: Annotated[bool, Query()] = True,
    end: Annotated[dt.date | None, Query()] = None,
    max_points: MaxPoints = DEFAULT_COMPARE_POINTS,
) -> Json | JSONResponse:
    """주식 일시금 — `routes/stock_simulation.get_simulation`과 같은 차례."""
    stock_service.check_principal_currency(principal_currency)
    amount = stock_service.parse_principal(principal)
    finish = end or (dt.date.today() - dt.timedelta(days=1))
    stock = await stock_service.require_stock(session, market, symbol)
    stock_service.check_principal_currency(principal_currency, stock.currency)
    await stock_service.require_start_available(session, stock, start)
    collecting = await stock_collecting(session, stock, start=start, end=finish)
    if collecting is not None:
        return JSONResponse(status_code=202, content=collecting)

    prepared = await stock_service.prepare(
        session, market=market, symbol=symbol, start=start, end=finish, principal=amount,
        principal_currency=principal_currency, reinvest=reinvest)
    stock, result = prepared.stock, prepared.result
    summary = stock_routes.summary_json(result, amount, market=stock.market,
                                        fee_rate=prepared.settings.trade_fee_rate,
                                        sale_tax=prepared.sale_tax)
    series = stock_series_service.build_series(
        result, start=start, end=finish, covered=await get_coverage(session, int(stock.id)),
        max_points=max_points)

    domestic = stock.market == DOMESTIC_MARKET
    sale = summary.get("saleCost")
    sale_body = _object(sale) if sale is not None else None
    costs = stock_costs(
        buy_fee=krw_sum(((c.row.trade_fee, c.fx_rate) for c in result.rows), domestic=domestic),
        dividend_tax=krw_sum(((c.row.dividend_tax, c.fx_rate) for c in result.rows),
                             domestic=domestic),
        sale_fee=None if sale_body is None else _decimal(sale_body["fee"]),
        sale_tax=None if sale_body is None else _decimal(sale_body["tax"]),
        tax_kind=None if sale_body is None else str(sale_body["taxKind"]))
    exchange = stock_routes.exchange_json(result)
    latest = result.latest
    fx = (FxInfo(stock.currency, latest.fx_rate, latest.fx_rate_date, exchange)
          if not domestic and latest is not None and latest.fx_rate is not None
          and latest.fx_rate_date is not None else None)
    return _body(
        target=stock_routes.stock_json(stock),
        condition=stock_routes.condition_json(prepared, start=start, principal=amount,
                                              principal_currency=principal_currency,
                                              reinvest=reinvest),
        exchange=exchange, summary=summary,
        series=stock_series_routes.series_json(series, principal_currency=principal_currency,
                                               price_currency=stock.currency),
        comparison=comparison_block("stock_lump", summary, costs,
                                    principal_currency=principal_currency, fx=fx,
                                    unit_price=_stock_lump_unit(result, stock.currency),
                                    listing=await _stock_listing(session, stock, first_trade)))


@router.get("/crypto/simulation", response_model=None)
async def compare_crypto(
    session: Session,
    coin_id: Annotated[int, Query(alias="coinId")],
    start: Annotated[dt.date, Query()],
    principal: Annotated[str, Query(description="투자 원금. 문자열")],
    principal_currency: Annotated[str, Query(alias="principalCurrency")],
    end: Annotated[dt.date | None, Query()] = None,
    max_points: MaxPoints = DEFAULT_COMPARE_POINTS,
) -> Json | JSONResponse:
    """가상자산 일시금 — `routes/crypto_simulation.get_simulation`과 같은 차례.

    요약과 시계열을 한 번에 내려고 `daily=True`로 계산한다(메뉴 표 경로는 `daily=False`). `daily`는
    일봉마다의 평가를 더할 뿐 요약을 바꾸지 않는다 — 통합 테스트가 요약 동일성으로 지킨다.
    """
    amount = stock_service.parse_principal(principal)
    finish = crypto_routes.calculation_end(end)
    if start > finish:
        raise StartAfterEnd(finish)
    coin = await crypto_service.require_coin(session, coin_id)
    crypto_service.check_principal_currency(principal_currency, coin.quote_currency)
    crypto_service.require_start_available(coin, start)
    collecting = await crypto_collecting(session, coin, start=start, end=finish,
                                         settings=load_settings())
    if collecting is not None:
        return JSONResponse(status_code=202, content=collecting)

    prepared = await crypto_service.prepare(session, coin, start=start, end=finish,
                                            principal=amount,
                                            principal_currency=principal_currency, daily=True)
    result = prepared.result
    summary = crypto_routes.summary_json(result, amount)
    series = crypto_series_service.build_series(
        result, start=start, end=finish,
        covered=await crypto_daily.get_coverage(session, int(coin.id)), max_points=max_points)

    domestic = coin.quote_currency == "KRW"
    costs = crypto_costs(buy_fee=krw_sum(((v.row.trade_fee, v.fx_rate) for v in result.rows),
                                         domestic=domestic))
    exchange = crypto_routes.exchange_json(result)
    latest = result.latest
    fx = (FxInfo(coin.quote_currency, latest.fx_rate, latest.fx_rate_date, exchange)
          if not domestic and latest is not None and latest.fx_rate is not None
          and latest.fx_rate_date is not None else None)
    return _body(
        target=crypto_routes.coin_json(coin),
        condition=crypto_routes.condition_json(prepared, start=start, principal=amount,
                                               principal_currency=principal_currency),
        exchange=exchange, summary=summary,
        series=crypto_series_routes.series_json(series, principal_currency=principal_currency,
                                                price_currency=coin.quote_currency),
        comparison=comparison_block("crypto_lump", summary, costs,
                                    principal_currency=principal_currency, fx=fx,
                                    unit_price=_crypto_lump_unit(result, coin.quote_currency),
                                    listing=coin_listing_date(coin.first_available_date)))


@router.get("/deposit/simulation", response_model=None)
async def compare_deposit(
    session: Session,
    institution: Annotated[str, Query()],
    start: Annotated[str, Query(description="YYYY-MM-DD")],
    principal: Annotated[str, Query(description="원 단위 정수 문자열")],
    principal_currency: Annotated[str | None, Query(alias="principalCurrency")] = None,
    end: Annotated[str | None, Query(description="기본 오늘(한국 시간)")] = None,
    max_points: MaxPoints = DEFAULT_COMPARE_POINTS,
) -> Json | JSONResponse:
    """정기예금 — `routes/deposit_simulation.get_simulation`과 같은 차례."""
    request = deposit_service.read_request(institution, start, principal, principal_currency,
                                           end)
    result = await deposit_service.simulate_or_collect(session, request)
    if not isinstance(result, deposit_service.Prepared):
        return JSONResponse(status_code=202, content=result)
    outcome = result.outcome
    summary = deposit_routes.summary_json(outcome, result.recheck_failed)
    series = deposit_series_service.build_series(
        outcome, start=request.start, rates=result.rates, latest_month=result.latest_month,
        max_points=max_points)
    costs = deposit_costs(matured_taxes=[t.tax for t in outcome.terms],
                          open_tax=outcome.summary.accrued_tax)
    return _body(
        target=deposit_routes.institution_json(request),
        condition=deposit_routes.condition_json(request, result), exchange=None,
        summary=summary, series=deposit_series_routes.series_json(series),
        comparison=comparison_block("deposit", summary, costs, unit_price=_rate_unit(
            result.rates, result.latest_month, request.start, outcome.summary.as_of)))


@router.get("/realestate/simulation", response_model=None)
async def compare_realestate(
    session: Session,
    settings: Annotated[Settings, Depends(get_realestate_settings)],
    now: Annotated[dt.datetime, Depends(get_realestate_now)],
    complex_id: Annotated[str, Query(alias="complexId")],
    area: Annotated[str, Query()],
    buy_date: Annotated[str, Query(alias="buyDate")],
    buy_price: Annotated[str | None, Query(alias="buyPrice")] = None,
    principal_currency: Annotated[str | None, Query(alias="principalCurrency")] = None,
    max_points: MaxPoints = DEFAULT_COMPARE_POINTS,
) -> Json | JSONResponse:
    """부동산 매입 후 보유 — `routes/realestate_simulation.get_simulation`과 같은 차례.

    매입가는 받지 않는다 — 비교의 매입가는 대상마다 그 달 시세다(spec FR-008).
    """
    if buy_price is not None:
        raise InvalidQuery("비교는 매입가를 받지 않습니다 — 대상마다 매입 달 시세입니다.")
    query = realestate_service.parse_query(complex_id, area, buy_date, None, principal_currency,
                                           today=kst_date(now))
    prepared = await realestate_service.prepare(session, query, settings=settings, now=now)
    if not isinstance(prepared, realestate_service.Prepared):
        return JSONResponse(status_code=202, content=prepared)
    body = await realestate_service.render_prepared(session, prepared, query)
    summary = _object(body["summary"])
    acquisition = _object(body["acquisition"])
    sale = summary.get("saleCost")
    sale_body = _object(sale) if sale is not None else None

    def amount(source: Json, key: str) -> Decimal:
        value = _decimal(source[key])
        assert value is not None
        return value

    costs = realestate_costs(
        acquisition_tax=amount(acquisition, "acquisitionTax"),
        education_tax=amount(acquisition, "educationTax"),
        rural_tax=amount(acquisition, "ruralTax"),
        brokerage_buy=amount(acquisition, "brokerageFee"),
        property_tax=amount(summary, "propertyTaxTotal"),
        comprehensive_tax=amount(summary, "comprehensiveTaxTotal"),
        sale_brokerage=None if sale_body is None else _decimal(sale_body["brokerage"]),
        income_tax=None if sale_body is None else _decimal(sale_body["incomeTax"]),
        local_tax=None if sale_body is None else _decimal(sale_body["localTax"]),
        sale_kind=None if sale_body is None else str(sale_body["kind"]))
    series = realestate_series_service.build_series(prepared.result, max_points=max_points)
    return _body(
        target={"complex": body["complex"], "area": body["area"]},
        condition=_object(body["condition"]), exchange=None, summary=summary,
        series=realestate_series_routes.series_json(
            series, provisional_from=prepared.provisional_from),
        comparison=comparison_block("realestate", summary, costs,
                                    unit_price=_realestate_unit(prepared.result)))


@router.get("/stocks/recurring-simulation", response_model=None)
async def compare_stock_recurring(
    session: Session,
    first_trade: FirstTrade,
    market: Annotated[str, Query()],
    symbol: Annotated[str, Query()],
    start: Annotated[dt.date, Query()],
    amount: Annotated[str, Query(description="한 번 납입액(원금 통화). 문자열")],
    principal_currency: Annotated[str, Query(alias="principalCurrency")],
    frequency: Annotated[str, Query(description="daily · weekly · monthly · yearly")],
    reinvest: Annotated[bool, Query()] = True,
    end: Annotated[dt.date | None, Query()] = None,
    max_points: MaxPoints = DEFAULT_COMPARE_POINTS,
) -> Json | JSONResponse:
    """주식 적립식 — `routes/stock_recurring`과 같은 판정·계산(`prepare_or_collect`)."""
    prepared = await stock_recurring_routes.prepare_or_collect(
        session, market=market, symbol=symbol, start=start, amount_raw=amount,
        principal_currency=principal_currency, frequency_raw=frequency, reinvest=reinvest, end=end)
    if isinstance(prepared, JSONResponse):
        return prepared
    stock, result = prepared.stock, prepared.result
    finish = end or (dt.date.today() - dt.timedelta(days=1))
    summary = stock_recurring_service.summary_json(
        result, amount=stock_recurring_service.parse_amount(amount), stock=stock)
    series = recurring_series.build_stock_series(
        result, start=start, end=finish, covered=await get_coverage(session, int(stock.id)),
        max_points=max_points)
    sale = _object(summary["saleCost"])
    costs = stock_costs(
        buy_fee=_required(summary, "buyFeeTotal"),
        dividend_tax=_required(summary, "dividendTaxTotal"),
        sale_fee=_decimal(sale["fee"]), sale_tax=_decimal(sale["tax"]),
        tax_kind=str(sale["taxKind"]))
    latest = result.latest
    fx = (FxInfo(stock.currency, latest.fx_rate, latest.fx_rate_date)
          if stock.market != DOMESTIC_MARKET and latest is not None and latest.fx_rate is not None
          and latest.fx_rate_date is not None else None)
    return _body(
        target=stock_routes.stock_json(stock),
        condition=stock_recurring_routes.condition_json(
            prepared, start=start, amount_raw=amount, principal_currency=principal_currency,
            frequency_raw=frequency, reinvest=reinvest),
        exchange=None, summary=summary,
        series=stock_recurring_routes.series_json(series, principal_currency=principal_currency,
                                                  price_currency=stock.currency),
        comparison=comparison_block("stock_recurring", summary, costs,
                                    principal_currency=principal_currency, fx=fx,
                                    unit_price=_stock_recurring_unit(result, stock.currency),
                                    listing=await _stock_listing(session, stock, first_trade)))


@router.get("/crypto/recurring-simulation", response_model=None)
async def compare_crypto_recurring(
    session: Session,
    coin_id: Annotated[int, Query(alias="coinId")],
    start: Annotated[dt.date, Query()],
    amount: Annotated[str, Query(description="한 번 납입액(원금 통화). 문자열")],
    principal_currency: Annotated[str, Query(alias="principalCurrency")],
    frequency: Annotated[str, Query(description="daily · weekly · monthly · yearly")],
    end: Annotated[dt.date | None, Query()] = None,
    max_points: MaxPoints = DEFAULT_COMPARE_POINTS,
) -> Json | JSONResponse:
    """가상자산 적립식 — `routes/crypto_recurring`과 같은 판정·계산. 요약과 시계열을 한 번에 내려고
    `daily=True`로 계산한다(일시금과 같은 전제 — 통합 테스트가 요약 동일성으로 지킨다)."""
    prepared = await crypto_recurring_routes.prepare_or_collect(
        session, coin_id=coin_id, start=start, amount_raw=amount,
        principal_currency=principal_currency, frequency_raw=frequency, end=end, daily=True)
    if isinstance(prepared, JSONResponse):
        return prepared
    coin, result = prepared.coin, prepared.result
    summary = crypto_recurring_routes.summary_json(result,
                                                   pending_after_end=result.pending_after_end)
    series = recurring_series.build_crypto_series(
        result, start=start, end=crypto_routes.calculation_end(end),
        covered=await crypto_daily.get_coverage(session, int(coin.id)), max_points=max_points)
    sale = _object(summary["saleCost"])
    costs = crypto_costs(buy_fee=_required(summary, "buyFeeTotal"), sale_fee=_decimal(sale["fee"]),
                         sale_tax=_decimal(sale["tax"]), tax_kind=str(sale["taxKind"]))
    latest = result.latest
    fx = (FxInfo(coin.quote_currency, latest.fx_rate, latest.fx_rate_date)
          if coin.quote_currency != "KRW" and latest.fx_rate is not None
          and latest.fx_rate_date is not None else None)
    return _body(
        target=crypto_routes.coin_json(coin),
        condition=crypto_recurring_routes.condition_json(
            prepared, start=start, amount_raw=amount, principal_currency=principal_currency,
            frequency_raw=frequency),
        exchange=None, summary=summary,
        series=crypto_recurring_routes.series_json(series, principal_currency=principal_currency,
                                                   price_currency=coin.quote_currency),
        comparison=comparison_block("crypto_recurring", summary, costs,
                                    principal_currency=principal_currency, fx=fx,
                                    unit_price=_crypto_recurring_unit(result, coin.quote_currency),
                                    listing=coin_listing_date(coin.first_available_date)))


@router.get("/deposit/installment-simulation", response_model=None)
async def compare_installment(
    session: Session,
    institution: Annotated[str, Query()],
    start: Annotated[str, Query(description="YYYY-MM-DD — 첫 적금 가입일")],
    amount: Annotated[str, Query(description="월 납입액. 원 단위 정수 문자열")],
    end: Annotated[str | None, Query(description="기본 오늘(한국 시간)")] = None,
    max_points: MaxPoints = DEFAULT_COMPARE_POINTS,
) -> Json | JSONResponse:
    """정기 적금 — `routes/deposit_installment.get_installment_simulation`과 같은 차례."""
    request = installment_service.read_request(institution, start, amount, end)
    result = await installment_service.simulate_or_collect(session, request)
    if not isinstance(result, installment_service.PreparedInstallment):
        return JSONResponse(status_code=202, content=result)
    outcome = result.outcome
    summary = installment_routes.summary_json(outcome, result.recheck_failed)
    series = recurring_series.build_installment_series(
        outcome, start=request.start, installment_rates=result.installment_rates,
        installment_latest=result.installment_latest, deposit_rates=result.deposit_rates,
        deposit_latest=result.deposit_latest, max_points=max_points)
    costs = deposit_costs(matured_taxes=[outcome.summary.tax_total],
                          open_tax=outcome.summary.open_tax)
    return _body(
        target=installment_routes.institution_json(request),
        condition=installment_routes.condition_json(request, result), exchange=None,
        summary=summary, series=installment_routes.series_json(series),
        comparison=comparison_block("installment", summary, costs, unit_price=_rate_unit(
            result.installment_rates, result.installment_latest, request.start,
            outcome.summary.as_of)))
