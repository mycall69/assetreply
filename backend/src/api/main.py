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
    InvalidQuery,
    InvalidSetting,
    InvalidSpread,
    OutOfRange,
    UnknownCurrency,
    UnknownListing,
    UnknownStock,
)
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
    from src.ingestion.ecos.client import EcosClient
    from src.ingestion.kiwoom.client import KiwoomClient
    from src.ingestion.yahoo.client import YahooStockClient
    from src.observability.logging_config import configure_logging
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

    tasks = [
        asyncio.create_task(worker_loop(
            factory, EcosClient(settings), get_queue(), settings=settings)),
        asyncio.create_task(reconcile_loop(
            factory, interval_seconds=settings.reconcile_interval_seconds)),
        asyncio.create_task(stock_worker_loop(
            factory, stock_client, get_stock_queue())),
        asyncio.create_task(listing_worker_loop(
            factory, listing_client, get_listing_queue(), settings=settings)),
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

    @app.exception_handler(BeforeListing)
    async def _before_listing(_: Request, exc: BeforeListing) -> JSONResponse:
        # **조용히 첫 거래일로 옮기지 않는다** — 옮기면 사용자는 자신이 고른 날짜부터
        # 계산됐다고 믿는다 (FR-005).
        return _json(400, "before_listing", str(exc))

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
    from src.api.routes import daily as daily_routes
    from src.api.routes import jobs as job_routes
    from src.api.routes import latest as latest_routes
    from src.api.routes import rates as rates_routes
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

    return app


app = create_app()
