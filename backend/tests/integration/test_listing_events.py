"""목록 갱신 사건 기록 (T101) — 006 FR-065, FR-060, SC-014, research R6-14.

**구현 뒤 보강한 테스트다**(analyze C1). FR-065는 구현(`listing_refresh._event`)이 먼저
있었고 그것을 검증하는 테스트가 없었다. 그래서 이 테스트는 처음부터 통과한다 —
plan Complexity Tracking D1과 같은 유형이다.

수집 전용 로그에 단위·쪽 수·종목 수·실패 종류를 남기고, **키·토큰·인증 헤더는 싣지 않는다.**
"""
from __future__ import annotations

import pytest

from src.api.services.listing_refresh import AuthBlocker, refresh_unit
from src.ingestion.kiwoom.errors import KiwoomAuthError, KiwoomRateLimited
from tests.integration.listing_support import (
    APP_KEY,
    APP_SECRET,
    KOSPI_ROWS,
    NOW,
    StubListingSource,
    kr_body,
    listing_settings,
    page,
    reset_listing_state,
)


@pytest.fixture(autouse=True)
def _listing_state():
    reset_listing_state()
    yield
    reset_listing_state()


def events(captured) -> list[dict[str, object]]:  # type: ignore[no-untyped-def]
    return [{k: v for k, v in r.__dict__.items() if k in (
        "event", "unit", "pages", "rows", "inserted", "missing", "kind")}
        for r in captured if getattr(r, "event", "").startswith("listing_refresh")]


async def run(session_factory, response):  # type: ignore[no-untyped-def]
    source = StubListingSource({"KOSPI": [response]})
    return await refresh_unit(session_factory, source, "KOSPI", settings=listing_settings(),
                              now=lambda: NOW, blocker=AuthBlocker())


async def test_성공하면_시작과_완료를_남긴다(session_factory, captured) -> None:
    await run(session_factory, [page(kr_body(KOSPI_ROWS))])
    assert events(captured) == [
        {"event": "listing_refresh_started", "unit": "KOSPI"},
        {"event": "listing_refresh_completed", "unit": "KOSPI", "pages": 1, "rows": 4,
         "inserted": 4, "missing": 0},
    ]


async def test_실패하면_실패_종류를_남긴다(session_factory, captured) -> None:
    await run(session_factory, KiwoomRateLimited("한도"))
    assert events(captured) == [
        {"event": "listing_refresh_started", "unit": "KOSPI"},
        {"event": "listing_refresh_failed", "unit": "KOSPI", "kind": "rate_limit"},
    ]


async def test_사건에_키와_토큰이_없다(session_factory, captured) -> None:
    """FR-060, SC-014 — 출처 문구가 요청 값을 되돌려 보내도 사건에는 남지 않는다."""
    await run(session_factory, KiwoomAuthError(
        f"거절됨 appkey={APP_KEY} secret={APP_SECRET} token=Ab12Cd34Ef56Gh78Ij90"))
    await run(session_factory, [page(kr_body(KOSPI_ROWS))])
    assert captured
    for record in captured:
        text = repr(record.__dict__) + record.getMessage()
        for secret in (APP_KEY, APP_SECRET, "Ab12Cd34Ef56Gh78Ij90", "Bearer"):
            assert secret not in text
