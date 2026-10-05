"""부동산 보유세 기준 비율 (T041) — 009 FR-034, US2, contracts/rest-api `GET`·`PUT
/api/realestate/settings`.

보유세 기준 금액 = 그해 6월 적용 시세 × 비율(기본 0.600000 — 실거래 평균의 60%를 공시가격 대용으로
쓴다). **다른 자산군 설정과 따로다.** 바꾼 비율은 다음 시뮬레이션에 쓰이고 조건에 보인다 — 결과를
저장하지 않으므로 무효화할 캐시가 없다. 0 < 비율 ≤ 1, 소수 6자리까지 — 넘는 자릿수를 반올림해
저장하지 않는다(넣은 값과 달라진다).
"""
from __future__ import annotations

import datetime as dt

import pytest
from httpx2 import ASGITransport, AsyncClient

from src.api.main import create_app
from src.api.services import realestate_lists
from src.db.session import get_session
from src.repository import apt_job
from src.worker import apt_worker
from src.worker.apt_queue import AptWork, get_apt_list_queue, get_apt_trade_queue
from tests.integration.apt_support import NOW_UTC, FakePortal, apt_settings, portal_client

D = dt.date.fromisoformat
SETTINGS = apt_settings(apt_trade_probe_start=D("2020-01-01"))
GARAK = "1171010700"


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


async def _run(session_factory, source, job_id: int, kind: str, target: str) -> None:  # type: ignore[no-untyped-def]
    runner = apt_worker.run_trade_job if kind == "trade" else apt_worker.run_list_job
    await runner(session_factory, source, AptWork(job_id, kind, target), settings=SETTINGS,
                 now=NOW_UTC)
    (get_apt_trade_queue() if kind == "trade" else get_apt_list_queue()).done(kind, target)


async def helio(http, source, session_factory) -> int:  # type: ignore[no-untyped-def]
    """행정구역·가락동·송파구 실거래를 받고 헬리오시티 단지 id."""
    first = (await http.get("/api/realestate/regions")).json()
    await _run(session_factory, source, first["jobId"], "region", "regions")
    body = (await http.get("/api/realestate/complexes", params={"umd": GARAK})).json()
    await _run(session_factory, source, body["trades"]["jobId"], "trade", "11710")
    async with session_factory() as s:
        details = await apt_job.running_job_id(s, "complex_details", GARAK)
    if details is not None:
        await _run(session_factory, source, details, "complex_details", GARAK)
    items = (await http.get("/api/realestate/complexes", params={"umd": GARAK})).json()["items"]
    return int(next(i["complexId"] for i in items if i["name"].startswith("헬리오시티")))


async def test_기본은_60퍼센트다(client) -> None:  # type: ignore[no-untyped-def]
    http, _ = client
    response = await http.get("/api/realestate/settings")
    assert response.status_code == 200
    assert response.json() == {"holdingTaxBaseRatio": "0.600000", "isDefault": True}


async def test_저장하면_기본값이_아니고_되돌리면_기본이다(client) -> None:  # type: ignore[no-untyped-def]
    http, _ = client
    response = await http.put("/api/realestate/settings", json={"holdingTaxBaseRatio": "0.7"})
    assert response.status_code == 200
    assert response.json() == {"holdingTaxBaseRatio": "0.700000", "isDefault": False}
    assert (await http.get("/api/realestate/settings")).json()["holdingTaxBaseRatio"] == "0.700000"
    back = await http.put("/api/realestate/settings", json={"holdingTaxBaseRatio": "0.6"})
    assert back.json() == {"holdingTaxBaseRatio": "0.600000", "isDefault": True}


async def test_1은_저장한다(client) -> None:  # type: ignore[no-untyped-def]
    """100% — 시세 그대로를 기준 금액으로 쓴다."""
    http, _ = client
    response = await http.put("/api/realestate/settings", json={"holdingTaxBaseRatio": "1"})
    assert response.json() == {"holdingTaxBaseRatio": "1.000000", "isDefault": False}


@pytest.mark.parametrize("body", [
    {"holdingTaxBaseRatio": "0"}, {"holdingTaxBaseRatio": "-0.1"},
    {"holdingTaxBaseRatio": "1.000001"}, {"holdingTaxBaseRatio": "1.5"},
    {"holdingTaxBaseRatio": "abc"}, {"holdingTaxBaseRatio": "NaN"},
    {"holdingTaxBaseRatio": 0.6}, {"holdingTaxBaseRatio": "0.6000001"}, {}])
async def test_범위_밖이나_숫자_문자열이_아니거나_6자리를_넘으면_422다(client, body: dict) -> None:  # type: ignore[no-untyped-def,type-arg]
    http, _ = client
    response = await http.put("/api/realestate/settings", json=body)
    assert response.status_code == 422
    assert response.json()["status"] == "invalid_setting"
    assert (await http.get("/api/realestate/settings")).json()["isDefault"] is True


async def test_다른_자산군_설정과_따로다(client) -> None:  # type: ignore[no-untyped-def]
    http, _ = client
    others = {path: (await http.get(path)).json()
              for path in ("/api/stocks/settings", "/api/crypto/settings", "/api/deposit/settings")}
    saved = await http.put("/api/realestate/settings", json={"holdingTaxBaseRatio": "0.8"})
    assert saved.status_code == 200
    assert {path: (await http.get(path)).json() for path in others} == others


async def test_바꾼_비율이_다음_시뮬레이션에_쓰인다(client, session_factory) -> None:  # type: ignore[no-untyped-def]
    """보유세 기준 금액이 늘어 재산세·종부세가 늘고, 조건에 비율이 보인다. 되돌리면 처음 결과."""
    http, source = client
    complex_id = await helio(http, source, session_factory)
    params = {"complexId": str(complex_id), "area": "30k", "buyDate": "2021-03-15"}
    before = (await http.get("/api/realestate/simulation", params=params)).json()
    await http.put("/api/realestate/settings", json={"holdingTaxBaseRatio": "0.7"})
    after = (await http.get("/api/realestate/simulation", params=params)).json()
    assert (before["condition"]["holdingTaxBaseRatio"],
            after["condition"]["holdingTaxBaseRatio"]) == ("0.600000", "0.700000")
    assert int(after["summary"]["propertyTaxTotal"]) > int(before["summary"]["propertyTaxTotal"])
    assert int(after["summary"]["comprehensiveTaxTotal"]) > int(
        before["summary"]["comprehensiveTaxTotal"])
    assert int(after["summary"]["profit"]) < int(before["summary"]["profit"])
    assert after["acquisition"] == before["acquisition"]  # 취득 비용은 비율과 무관하다
    await http.put("/api/realestate/settings", json={"holdingTaxBaseRatio": "0.6"})
    assert (await http.get("/api/realestate/simulation", params=params)).json() == before
