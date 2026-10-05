"""부동산 시계열의 투자 수익 (010 T019) — FR-009, SC-003, contracts/rest-api `GET
/api/realestate/simulation/series`.

차트 위 상자는 그 달의 **투자 수익**을 보인다(사용자 요청 — 평가액·수익률·실거래가 평균과 함께).
점의 `profit`(원 정수 문자열)은 표의 그 달 `profit`과 같고 끝점은 보드(`summary.profit`)와 같다 —
계산하지 않고 옮긴다. 거래 없는 달(`no_trades`)도 평가액이 있으므로 투자 수익이 있다(적용 시세 —
추정 포함).
"""
from __future__ import annotations

import pytest
from httpx2 import ASGITransport, AsyncClient

from src.api.main import create_app
from src.api.services import realestate_lists
from src.db.session import get_session
from tests.integration.apt_support import NOW_UTC, FakePortal, portal_client
from tests.integration.test_realestate_series_price_api import (
    SETTINGS,
    both,
    collected,
    rare_complex,
)


@pytest.fixture
async def client(session_factory):  # type: ignore[no-untyped-def]
    source = portal_client(FakePortal(), SETTINGS)
    app = create_app()

    async def _session():  # type: ignore[no-untyped-def]
        async with session_factory() as s:
            yield s

    app.dependency_overrides[get_session] = _session
    app.dependency_overrides[realestate_lists.get_realestate_now] = lambda: NOW_UTC
    app.dependency_overrides[realestate_lists.get_realestate_settings] = lambda: SETTINGS
    app.dependency_overrides[realestate_lists.get_realestate_source] = lambda: source
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as http:
        yield http, source


async def test_점의_투자_수익은_표의_그_달과_같고_끝점은_보드다(client, session_factory) -> None:  # type: ignore[no-untyped-def]
    http, source = client
    names = await collected(http, source, session_factory)
    table, series = await both(http, complexId=str(names["헬리오시티아파트"]), area="30k",
                               buyDate="2021-03-15")
    rows = {r["month"]: r for r in table["rows"]}
    for point in series["points"][:-1]:
        assert point["profit"] == rows[point["date"][:7]]["profit"], point["date"]
    assert series["points"][-1]["profit"] == table["summary"]["profit"]


async def test_거래_없는_달에도_투자_수익이_있다(client, session_factory) -> None:  # type: ignore[no-untyped-def]
    http, source = client
    await collected(http, source, session_factory)
    complex_id = await rare_complex(session_factory)
    table, series = await both(http, complexId=str(complex_id), area="30k", buyDate="2020-01-20")
    rows = {r["month"]: r for r in table["rows"]}
    *months, end = series["points"]
    no_trades = [p for p in months if p.get("priceMissing") == "no_trades"]
    assert len(no_trades) >= 30
    for point in no_trades:
        assert point["profit"] is not None
        assert point["profit"] == rows[point["date"][:7]]["profit"], point["date"]
    assert end["profit"] == table["summary"]["profit"]
