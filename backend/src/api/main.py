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
    InvalidSpread,
    OutOfRange,
    UnknownCurrency,
)
from src.db.session import init_engine, shutdown_engine
from src.ingestion.ecos.errors import (
    ItemMappingChanged,
    SourceAuthError,
    SourceRateLimited,
    SourceUnavailable,
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
    from src.observability.logging_config import configure_logging
    from src.worker.queue import get_queue
    from src.worker.reconcile import reconcile_loop, reconcile_on_startup
    from src.worker.runner import worker_loop

    init_engine()
    settings = load_settings()
    # 수집 로그를 웹서버 표준출력과 분리된 파일로 보낸다 (research R3-10).
    # 여기서 부르지 않으면 로거에 핸들러가 없어 사건이 어디에도 남지 않는다.
    configure_logging(settings.collection_log_file())
    factory = get_session_factory()

    # 죽었다 살아난 직후가 가장 흔한 경우다. 기동 시 한 번 정리해 점유를 푼다.
    await reconcile_on_startup(factory)

    tasks = [
        asyncio.create_task(worker_loop(
            factory, EcosClient(settings), get_queue(), settings=settings)),
        asyncio.create_task(reconcile_loop(
            factory, interval_seconds=settings.reconcile_interval_seconds)),
    ]
    try:
        yield
    finally:
        for task in tasks:
            task.cancel()
        for task in tasks:
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await task
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

    return app


app = create_app()
