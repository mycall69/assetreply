"""FastAPI 애플리케이션 부트스트랩과 오류 매핑 (T025).

contracts/rest-api.md의 공통 오류표를 도메인 예외에서 HTTP 상태로 옮긴다.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from src.api.errors import InvalidSpread, OutOfRange, UnknownCurrency
from src.db.session import init_engine, shutdown_engine
from src.ingestion.ecos.errors import (
    ItemMappingChanged,
    SourceAuthError,
    SourceRateLimited,
    SourceUnavailable,
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """커넥션 풀을 앱 수명과 함께 관리한다(헌법 v4.0.0 MUST)."""
    init_engine()
    yield
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
    from src.api.routes import coverage as coverage_routes
    from src.api.routes import jobs as job_routes
    from src.api.routes import rates as rates_routes
    from src.api.routes import series as series_routes
    from src.api.routes import spreads as spread_routes

    app.include_router(rates_routes.router)
    app.include_router(coverage_routes.router)
    app.include_router(spread_routes.router)
    app.include_router(series_routes.router)
    app.include_router(collect_routes.router)
    app.include_router(job_routes.router)

    return app


app = create_app()
