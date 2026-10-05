"""FastAPI 애플리케이션 부트스트랩과 오류 매핑 (T025).

contracts/rest-api.md의 공통 오류표를 도메인 예외에서 HTTP 상태로 옮긴다.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from src.api.errors import (
    CollectionInProgress,
    CurrencyNotAllowed,
    CurrencyPairNotAllowed,
    InvalidQuery,
    InvalidSetting,
    InvalidSpread,
    NoRateData,
    OutOfRange,
    RegionRetired,
    StartAfterEnd,
    UnknownCoin,
    UnknownComplex,
    UnknownCurrency,
    UnknownInstitution,
    UnknownListing,
    UnknownRegion,
    UnknownStock,
)
from src.api.services.stock_collect import FxNotAvailableBefore
from src.api.services.stock_fx import FxUnavailable
from src.api.services.stock_simulation import BeforeListing, NoPriceData
from src.db.session import init_engine, shutdown_engine
from src.ingestion.ecos.errors import (
    ItemMappingChanged,
    SourceAuthError,
    SourceRateLimited,
    SourceUnavailable,
)
from src.ingestion.yahoo.errors import (
    StockSourceAuthError,
    StockSourceRateLimited,
    StockSourceUnavailable,
    StockSymbolNotFound,
)
from src.simulation.apt_holding import BeforeStartable, NoPriceAtPurchase, NoTradesInArea
from src.simulation.apt_tax_rules import RuleNotCovered
from src.simulation.deposit_rollover import BeforeFirstMonth, RateMissing


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """커넥션 풀과 **수집 워커**를 앱 수명과 함께 관리한다 (003 T024).

    워커를 여기 띄우는 것이 003의 핵심이다. 001·002는 수집 엔진을 만들어 두고 그것을
    호출하는 주체를 만들지 않아, 수집을 시작해도 작업이 진행 중으로 박힌 채 멈췄다.

    **종료 순서가 중요하다.** 워커를 먼저 취소해 완료를 기다린 뒤 엔진을 닫는다.
    반대로 하면 세션이 닫힌 뒤 워커가 DB를 만져 예외가 난다.
    """
    import asyncio
    import contextlib

    from src.config.settings import load_settings
    from src.db.session import get_session_factory
    from src.ingestion.datagokr.client import DataGoKrClient
    from src.ingestion.datagokr.gate import DataGoKrGate
    from src.ingestion.ecos.client import EcosClient
    from src.ingestion.ecos.deposit_client import EcosDepositClient
    from src.ingestion.investing.client import InvestingClient
    from src.ingestion.kiwoom.client import KiwoomClient
    from src.ingestion.yahoo.client import YahooStockClient
    from src.observability.logging_config import configure_logging
    from src.repository.apt_usage import ApiUsageCounter
    from src.worker import apt_worker
    from src.worker.apt_queue import get_apt_list_queue, get_apt_trade_queue
    from src.worker.apt_worker import apt_worker_loop
    from src.worker.apt_worker import startup as apt_startup
    from src.worker.crypto_list_queue import get_crypto_list_queue
    from src.worker.crypto_list_worker import crypto_list_worker_loop
    from src.worker.crypto_list_worker import startup as crypto_list_startup
    from src.worker.crypto_queue import get_crypto_queue
    from src.worker.crypto_worker import crypto_worker_loop
    from src.worker.crypto_worker import startup as crypto_startup
    from src.worker.deposit_queue import get_deposit_queue
    from src.worker.deposit_worker import deposit_worker_loop
    from src.worker.deposit_worker import startup as deposit_startup
    from src.worker.listing_queue import get_listing_queue
    from src.worker.listing_worker import listing_worker_loop
    from src.worker.listing_worker import startup as listing_startup
    from src.worker.queue import get_queue
    from src.worker.reconcile import reconcile_loop, reconcile_on_startup
    from src.worker.runner import worker_loop
    from src.worker.stock_queue import get_stock_queue
    from src.worker.stock_worker import stock_worker_loop

    init_engine()
    settings = load_settings()
    # 수집 로그를 웹서버 표준출력과 분리된 파일로 보낸다 (research R3-10).
    # 여기서 부르지 않으면 로거에 핸들러가 없어 사건이 어디에도 남지 않는다.
    configure_logging(settings.collection_log_file())
    factory = get_session_factory()

    # 죽었다 살아난 직후가 가장 흔한 경우다. 기동 시 한 번 정리해 점유를 푼다.
    await reconcile_on_startup(factory)
    # 006 — 목록 갱신 점유도 같다. 프로세스가 하나라 남은 점유는 죽은 프로세스의 것이다.
    await listing_startup(factory)
    # 007 — 코인 목록 갱신 점유와 가상자산 수집 점유도 같다.
    await crypto_list_startup(factory)
    await crypto_startup(factory)
    # 008 — 예금 금리 수집 점유도 같다.
    await deposit_startup(factory)
    # 009 — 부동산 수집 점유(실거래·행정구역·기본 정보)도 같다.
    await apt_startup(factory)

    # 005 — 주식 수집 워커. **FX와 분리한다**: 출처가 달라 호출 한도도 따로이고,
    # 한 루프에 섞으면 환율 수집이 주식 수집을 막으면서 그 이유가 화면에 드러나지
    # 않는다 (research R5-7). 002·003이 얻은 교훈이 여기에도 그대로 적용된다 —
    # 엔진만 만들고 호출하는 주체를 두지 않으면 작업이 "진행 중"으로 박힌 채 멈춘다.
    stock_client = YahooStockClient(settings)
    # 006 — 검색용 목록 갱신 워커. 등록하지 않으면 갱신 요청이 큐에 쌓이기만 하고
    # 실행되지 않는다(003·005가 겪은 일). 클라이언트는 수명 내내 하나 — 토큰을 메모리에
    # 두고 만료 10분 전에 갱신한다.
    listing_client = KiwoomClient(settings)
    await listing_client.__aenter__()
    # 007 — 가상자산 출처 클라이언트. **목록 갱신 줄과 시세 수집 줄이 이 하나를 함께 쓴다** — 출처
    # 입장에서는 한 클라이언트이고, 요청 사이 최소 간격을 두 줄이 함께 지킨다(research R7-11).
    crypto_client = InvestingClient(settings)
    await crypto_client.__aenter__()
    # 008 — 예금 금리 출처 클라이언트. 환율과 같은 ECOS·같은 인증키다. 동시 요청 수와 한도 초과
    # 백오프는 관문(`EcosGate`)이 환율 줄과 함께 지킨다(research R8-6).
    deposit_client = EcosDepositClient(settings)
    await deposit_client.__aenter__()
    # 009 — 공공데이터포털 클라이언트 하나. 네 자료가 같은 키·같은 게이트웨이라 관문 하나가 동시
    # 요청 수와 자료별 하루 호출 수(DB에 센다 — 다시 띄워도 이어 센다)를 지킨다. 요청 경로(단지
    # 목록)도 같은 것을 쓴다.
    apt_gate = DataGoKrGate(settings.data_api_max_concurrent, ApiUsageCounter(factory), {
        "trade": settings.data_api_daily_limit_trade,
        "region": settings.data_api_daily_limit_region,
        "kapt": settings.data_api_daily_limit_kapt})
    apt_client = DataGoKrClient(settings, apt_gate)
    await apt_client.__aenter__()
    apt_worker.set_shared_source(apt_client)

    tasks = [
        asyncio.create_task(worker_loop(
            factory, EcosClient(settings), get_queue(), settings=settings)),
        asyncio.create_task(reconcile_loop(
            factory, interval_seconds=settings.reconcile_interval_seconds)),
        asyncio.create_task(stock_worker_loop(
            factory, stock_client, get_stock_queue())),
        asyncio.create_task(listing_worker_loop(
            factory, listing_client, get_listing_queue(), settings=settings)),
        # 007 — 코인 목록 갱신 줄. 시세 수집과 다른 줄이다 — 목록(약 2분)이 시세 수집을 막지 않는다.
        asyncio.create_task(crypto_list_worker_loop(
            factory, crypto_client, get_crypto_list_queue(), settings=settings)),
        # 007 — 가상자산 시세 수집 줄. **주식 수집과 다른 줄이다** — 출처가 달라 한쪽이 막혀도 다른
        # 쪽이 기다리지 않는다(SC-012). 목록 갱신 줄과 같은 클라이언트(간격 제한기)를 쓴다.
        asyncio.create_task(crypto_worker_loop(
            factory, crypto_client, get_crypto_queue(), settings=settings)),
        # 008 — 예금 금리 수집 줄. **환율 수집과 다른 줄이다** — 같은 출처라도 한쪽 작업이 다른 쪽을
        # 기다리지 않는다(SC-012). 호출 한도는 관문이 함께 지킨다.
        asyncio.create_task(deposit_worker_loop(
            factory, deposit_client, get_deposit_queue(), settings=settings)),
        # 009 — 부동산 수집 태스크. **다른 자산군과 다른 출처라 따로다**(SC-012). 안에서 실거래 줄과
        # 목록 줄로 나뉜다 — 시·군·구 전체 이력(약 280회)이 행정구역 갱신을 막지 않는다.
        asyncio.create_task(apt_worker_loop(
            factory, apt_client, get_apt_trade_queue(), get_apt_list_queue(), settings=settings)),
    ]
    try:
        yield
    finally:
        for task in tasks:
            task.cancel()
        for task in tasks:
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await task
        await listing_client.__aexit__(None, None, None)
        await crypto_client.__aexit__(None, None, None)
        await deposit_client.__aexit__(None, None, None)
        apt_worker.set_shared_source(None)
        await apt_client.__aexit__(None, None, None)
        await shutdown_engine()


def create_app() -> FastAPI:
    app = FastAPI(title="AssetReplay — 외환", lifespan=lifespan)

    def _json(status: int, code: str, message: str) -> JSONResponse:
        return JSONResponse(status_code=status, content={"status": code, "message": message})

    @app.exception_handler(OutOfRange)
    async def _out_of_range(_: Request, exc: OutOfRange) -> JSONResponse:
        return _json(400, "out_of_range", str(exc) or "조회 가능한 범위를 벗어났습니다.")

    @app.exception_handler(UnknownCurrency)
    async def _unknown_currency(_: Request, exc: UnknownCurrency) -> JSONResponse:
        return _json(404, "unknown_currency", str(exc) or "지원하지 않는 통화입니다.")

    @app.exception_handler(InvalidQuery)
    async def _invalid_query(_: Request, exc: InvalidQuery) -> JSONResponse:
        return _json(400, "invalid_query", str(exc) or "질의 매개변수가 올바르지 않습니다.")

    @app.exception_handler(CurrencyPairNotAllowed)
    async def _currency_pair(_: Request, exc: CurrencyPairNotAllowed) -> JSONResponse:
        # 006 FR-050 — 고를 수 있는 통화를 함께 싣는다. 화면이 다시 고르게 한다.
        return JSONResponse(status_code=400, content={
            "status": "currency_pair_not_allowed", "message": str(exc),
            "allowed": exc.allowed})

    @app.exception_handler(CollectionInProgress)
    async def _in_progress(_: Request, exc: CollectionInProgress) -> JSONResponse:
        return _json(409, "collection_in_progress",
                     str(exc) or "다른 통화의 수집이 진행 중입니다.")

    @app.exception_handler(InvalidSpread)
    async def _invalid_spread(_: Request, exc: InvalidSpread) -> JSONResponse:
        return _json(422, "invalid_spread", str(exc) or "스프레드는 0 이상 1 미만이어야 합니다.")

    @app.exception_handler(SourceUnavailable)
    async def _source_unavailable(_: Request, exc: SourceUnavailable) -> JSONResponse:
        return _json(502, "source_unavailable", "데이터 출처의 응답이 유효하지 않습니다.")

    @app.exception_handler(InvalidSetting)
    async def _invalid_setting(_: Request, exc: InvalidSetting) -> JSONResponse:
        return _json(422, "invalid_setting", str(exc))

    @app.exception_handler(FxUnavailable)
    async def _fx_unavailable(_: Request, exc: FxUnavailable) -> JSONResponse:
        # 환산할 수 없다는 사실이 드러나야 한다. 값을 만들어내지 않는다 (원칙 V).
        return _json(409, 'fx_unavailable', str(exc))

    @app.exception_handler(FxNotAvailableBefore)
    async def _fx_not_available(_: Request, exc: FxNotAvailableBefore) -> JSONResponse:
        # 006 FR-043a — 수집하지 않는다. 두 사유를 섞지 않고 그 날짜를 함께 싣는다.
        return JSONResponse(status_code=409, content={
            "status": "fx_not_available_before", "reason": exc.reason,
            "message": str(exc), "currency": exc.currency,
            "availableFrom": exc.available_from.isoformat()})

    @app.exception_handler(BeforeListing)
    async def _before_listing(_: Request, exc: BeforeListing) -> JSONResponse:
        # **조용히 첫 거래일로 옮기지 않는다** — 옮기면 사용자는 자신이 고른 날짜부터
        # 계산됐다고 믿는다 (FR-005). 006 — 시작 가능 날짜와 근거를 싣는다. 화면이 그
        # 날짜로 옮기는 수단을 그린다(contracts 2절).
        return JSONResponse(status_code=400, content={
            "status": "before_listing", "message": str(exc),
            "startableFrom": exc.startable_from.isoformat(), "basis": exc.basis})

    @app.exception_handler(NoPriceData)
    async def _no_price_data(_: Request, exc: NoPriceData) -> JSONResponse:
        # **빈 표를 보여주지 않는다** — 사용자는 성과가 0이라고 읽는다 (FR-004).
        return _json(404, "no_price_data", str(exc))

    @app.exception_handler(StockSymbolNotFound)
    async def _price_symbol_unknown(_: Request, exc: StockSymbolNotFound) -> JSONResponse:
        # 006 FR-032 — "그 종목에 시세가 없다"(`no_price_data`)나 "우리 DB에 없다"
        # (`unknown_stock`)와 섞지 않는다. 섞으면 식별자 변환 결함이 "데이터 없는
        # 종목"으로 위장돼 고쳐지지 않는다.
        return _json(404, "price_symbol_unknown",
                     str(exc) or "시세 출처에서 그 종목을 찾지 못했습니다.")

    @app.exception_handler(UnknownStock)
    async def _unknown_stock(_: Request, exc: UnknownStock) -> JSONResponse:
        # 검색에서 다시 고르면 풀린다 — 할 일을 함께 싣는다 (006 FR-030b).
        return JSONResponse(status_code=404, content={
            "status": "unknown_stock", "message": str(exc), "action": "reselect"})

    @app.exception_handler(UnknownCoin)
    async def _unknown_coin(_: Request, exc: UnknownCoin) -> JSONResponse:
        # 007 — 검색에서 다시 고르면 풀린다. 할 일을 함께 싣는다(006 unknown_stock과 같다).
        return JSONResponse(status_code=404, content={
            "status": "unknown_coin", "message": str(exc), "action": "reselect"})

    @app.exception_handler(StartAfterEnd)
    async def _start_after_end(_: Request, exc: StartAfterEnd) -> JSONResponse:
        # 007 FR-009 — 계산할 일봉이 없다. 계산 끝(UTC 어제)을 함께 싣는다.
        return JSONResponse(status_code=400, content={
            "status": "start_after_end", "message": str(exc),
            "lastDay": exc.last_day.isoformat()})

    @app.exception_handler(UnknownInstitution)
    async def _unknown_institution(_: Request, exc: UnknownInstitution) -> JSONResponse:
        # 008 FR-003 — 고를 수 있는 투자처를 함께 싣는다.
        return JSONResponse(status_code=400, content={
            "status": "unknown_institution", "message": str(exc), "allowed": exc.allowed})

    @app.exception_handler(UnknownRegion)
    async def _unknown_region(_: Request, exc: UnknownRegion) -> JSONResponse:
        # 009 FR-002 — 사라진 코드도 "거래 없음"이 아니라 거절로 알린다.
        return JSONResponse(status_code=400, content={
            "status": "unknown_region", "message": str(exc)})

    @app.exception_handler(UnknownComplex)
    async def _unknown_complex(_: Request, exc: UnknownComplex) -> JSONResponse:
        return JSONResponse(status_code=400, content={
            "status": "unknown_complex", "message": str(exc)})

    @app.exception_handler(BeforeStartable)
    async def _before_startable(_: Request, exc: BeforeStartable) -> JSONResponse:
        # 009 FR-005 — 시작 가능 날짜와 그 근거(첫 거래 달·세법 표 시작). 조용히 옮기지 않는다.
        return JSONResponse(status_code=409, content={
            "status": "before_first_trade", "message": str(exc),
            "startableFrom": exc.startable_from.isoformat(), "basis": exc.basis})

    @app.exception_handler(NoPriceAtPurchase)
    async def _no_price_at_purchase(_: Request, exc: NoPriceAtPurchase) -> JSONResponse:
        # 009 FR-006 — 매입 달 시세가 없고 매입가도 없다. 매입가를 넣으면 계산할 수 있다.
        return JSONResponse(status_code=409, content={
            "status": "no_price_at_purchase", "message": str(exc),
            "month": f"{exc.month:%Y-%m}"})

    @app.exception_handler(NoTradesInArea)
    async def _no_trades_in_area(_: Request, exc: NoTradesInArea) -> JSONResponse:
        return JSONResponse(status_code=409, content={
            "status": "no_trades_in_area", "message": str(exc)})

    @app.exception_handler(RuleNotCovered)
    async def _rule_not_covered(_: Request, exc: RuleNotCovered) -> JSONResponse:
        # 009 FR-023 — 세법 표가 그 날짜를 덮지 않는다. 가까운 해로 대신하지 않는다.
        return JSONResponse(status_code=409, content={
            "status": "tax_rule_not_covered", "message": str(exc), "tax": exc.tax,
            "date": exc.on.isoformat()})

    @app.exception_handler(RegionRetired)
    async def _region_retired(_: Request, exc: RegionRetired) -> JSONResponse:
        # 009 FR-002 — 개편으로 사라진 시·군·구. 지역에서 다시 골라 실행하라고 안내한다.
        return JSONResponse(status_code=409, content={
            "status": "region_retired", "message": str(exc), "lawdCd": exc.lawd_cd})

    @app.exception_handler(CurrencyNotAllowed)
    async def _currency_not_allowed(_: Request, exc: CurrencyNotAllowed) -> JSONResponse:
        # 008 FR-004 — 예금 원금은 원화만이다. 조용히 원화로 읽지 않는다.
        return JSONResponse(status_code=400, content={
            "status": "currency_not_allowed", "message": str(exc), "allowed": exc.allowed})

    @app.exception_handler(BeforeFirstMonth)
    async def _before_first_month(_: Request, exc: BeforeFirstMonth) -> JSONResponse:
        # 008 FR-006 — **조용히 첫 달로 옮기지 않는다.** 시작 가능 날짜를 싣고 화면이 옮기기 수단을
        # 그린다.
        first = exc.first_month
        return JSONResponse(status_code=409, content={
            "status": "before_first_month",
            "message": f"이 투자처의 금리는 {first:%Y-%m}부터 있습니다. "
                       f"시작일을 {first.isoformat()} 이후로 고르세요.",
            "startableFrom": first.isoformat()})

    @app.exception_handler(RateMissing)
    async def _rate_missing(_: Request, exc: RateMissing) -> JSONResponse:
        # 008 FR-007·FR-019 — 가입 달의 금리가 비었다. 보간하지 않는다(헌법 원칙 V).
        return JSONResponse(status_code=409, content={
            "status": "rate_missing",
            "message": f"{exc.month:%Y-%m} 금리 통계가 비어 있어 가입할 수 없습니다.",
            "month": f"{exc.month:%Y-%m}"})

    @app.exception_handler(NoRateData)
    async def _no_rate_data(_: Request, exc: NoRateData) -> JSONResponse:
        # 빈 표를 보여주지 않는다 — 사용자는 수익이 0이라고 읽는다.
        return _json(404, "no_rate_data", str(exc))

    @app.exception_handler(UnknownListing)
    async def _unknown_listing(_: Request, exc: UnknownListing) -> JSONResponse:
        return _json(404, "unknown_listing", str(exc))

    @app.exception_handler(StockSourceUnavailable)
    async def _stock_unavailable(
        _: Request, exc: StockSourceUnavailable
    ) -> JSONResponse:
        return _json(502, "source_unavailable", "시세 출처가 응답하지 않습니다.")

    @app.exception_handler(StockSourceRateLimited)
    async def _stock_rate_limited(
        _: Request, exc: StockSourceRateLimited
    ) -> JSONResponse:
        return _json(503, "source_rate_limited",
                     "시세 출처의 호출 한도를 소진했습니다. 잠시 뒤 다시 시도하세요.")

    @app.exception_handler(StockSourceAuthError)
    async def _stock_auth(_: Request, exc: StockSourceAuthError) -> JSONResponse:
        return _json(502, "source_unavailable", "시세 출처가 요청을 거절했습니다.")

    @app.exception_handler(SourceRateLimited)
    async def _rate_limited(_: Request, exc: SourceRateLimited) -> JSONResponse:
        return _json(503, "source_rate_limited",
                     "데이터 출처의 호출 한도를 소진했습니다. 이미 저장된 데이터는 유효합니다.")

    @app.exception_handler(SourceAuthError)
    async def _auth_error(_: Request, exc: SourceAuthError) -> JSONResponse:
        return _json(502, "source_unavailable", "데이터 출처 인증에 실패했습니다.")

    @app.exception_handler(ItemMappingChanged)
    async def _mapping_changed(_: Request, exc: ItemMappingChanged) -> JSONResponse:
        return _json(502, "source_unavailable", "데이터 출처의 통화 식별 체계가 변경되었습니다.")

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    # 라우터는 예외 핸들러 등록 이후에 붙인다 (순환 임포트 회피)
    from src.api.routes import collect as collect_routes
    from src.api.routes import collection as collection_routes
    from src.api.routes import coverage as coverage_routes
    from src.api.routes import crypto_list_progress as crypto_list_progress_routes
    from src.api.routes import crypto_progress as crypto_progress_routes
    from src.api.routes import crypto_search as crypto_search_routes
    from src.api.routes import crypto_series as crypto_series_routes
    from src.api.routes import crypto_settings as crypto_settings_routes
    from src.api.routes import crypto_simulation as crypto_simulation_routes
    from src.api.routes import daily as daily_routes
    from src.api.routes import deposit_institutions as deposit_institutions_routes
    from src.api.routes import deposit_progress as deposit_progress_routes
    from src.api.routes import deposit_series as deposit_series_routes
    from src.api.routes import deposit_settings as deposit_settings_routes
    from src.api.routes import deposit_simulation as deposit_simulation_routes
    from src.api.routes import jobs as job_routes
    from src.api.routes import latest as latest_routes
    from src.api.routes import rates as rates_routes
    from src.api.routes import realestate_complexes as realestate_complexes_routes
    from src.api.routes import realestate_progress as realestate_progress_routes
    from src.api.routes import realestate_regions as realestate_regions_routes
    from src.api.routes import realestate_simulation as realestate_simulation_routes
    from src.api.routes import series as series_routes
    from src.api.routes import spreads as spread_routes
    from src.api.routes import stock_progress as stock_progress_routes
    from src.api.routes import stock_search as stock_search_routes
    from src.api.routes import stock_selection as stock_selection_routes
    from src.api.routes import stock_series as stock_series_routes
    from src.api.routes import stock_settings as stock_settings_routes
    from src.api.routes import stock_simulation as stock_simulation_routes
    from src.api.routes import today as today_routes

    app.include_router(rates_routes.router)
    app.include_router(coverage_routes.router)
    app.include_router(latest_routes.router)
    app.include_router(daily_routes.router)
    app.include_router(today_routes.router)
    app.include_router(spread_routes.router)
    app.include_router(series_routes.router)
    app.include_router(collect_routes.router)
    app.include_router(collection_routes.router)
    app.include_router(job_routes.router)
    # 005 — 주식 투자 시뮬레이션
    app.include_router(stock_search_routes.router)
    # 006 — 고른 종목 등록 (FR-030b)
    app.include_router(stock_selection_routes.router)
    app.include_router(stock_progress_routes.router)
    app.include_router(stock_simulation_routes.router)
    app.include_router(stock_series_routes.router)
    app.include_router(stock_settings_routes.router)
    # 007 — 가상자산 투자 시뮬레이션
    app.include_router(crypto_search_routes.router)
    app.include_router(crypto_list_progress_routes.router)
    app.include_router(crypto_simulation_routes.router)
    app.include_router(crypto_series_routes.router)
    app.include_router(crypto_progress_routes.router)
    app.include_router(crypto_settings_routes.router)
    # 008 — 예금 투자 시뮬레이션
    app.include_router(deposit_institutions_routes.router)
    app.include_router(deposit_simulation_routes.router)
    app.include_router(deposit_series_routes.router)
    app.include_router(deposit_progress_routes.router)
    app.include_router(deposit_settings_routes.router)
    app.include_router(realestate_regions_routes.router)
    app.include_router(realestate_complexes_routes.router)
    app.include_router(realestate_progress_routes.router)
    app.include_router(realestate_simulation_routes.router)

    return app


app = create_app()
