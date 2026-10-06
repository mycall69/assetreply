"""부동산 보드의 매도비용 (010 반복 5, T076) — FR-031, SC-012, contracts/rest-api "반복 5".

`GET /api/realestate/simulation`의 `summary`에 **더하는** 키 — `saleCost`(매도 중개 보수 +
양도소득세, 1세대 1주택·부부 5:5), `profitAfterSale` = `profit` − `saleCost.total`,
`returnRateAfterSale` = 그 값 ÷ `invested`. `condition.residenceRatio`. 기존 키는 그대로다.

시드는 009 통합 테스트와 같다(가짜 공공데이터포털 — 송파구 실거래 픽스처, 실행 날짜 2023-10-05).
기대값은 응답의 입력(평가액·매입가·취득 비용·매입일·기준일·거주 비율)을 순수
함수(`simulation/apt_sale_cost.sale_cost` — 단위 테스트가 손 계산으로 고정)에 넣은 값이다 — 이
파일은 연결(어느 값이 어디로 가는지)을 본다. 거주 비율 설정을 바꾸면 결과가 바뀐다.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest
from httpx2 import ASGITransport, AsyncClient

from src.api.main import create_app
from src.api.services import realestate_lists
from src.db.session import get_session
from src.repository import apt_job
from src.simulation.apt_sale_cost import sale_cost
from src.simulation.money import quantize_rate
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
    await runner(
        session_factory, source, AptWork(job_id, kind, target), settings=SETTINGS, now=NOW_UTC
    )
    (get_apt_trade_queue() if kind == "trade" else get_apt_list_queue()).done(kind, target)


async def helio(http, source, session_factory) -> int:  # type: ignore[no-untyped-def]
    first = (await http.get("/api/realestate/regions")).json()
    await _run(session_factory, source, first["jobId"], "region", "regions")
    body = (await http.get("/api/realestate/complexes", params={"umd": GARAK})).json()
    await _run(session_factory, source, body["trades"]["jobId"], "trade", "11710")
    async with session_factory() as s:
        details = await apt_job.running_job_id(s, "complex_details", GARAK)
    if details is not None:
        await _run(session_factory, source, details, "complex_details", GARAK)
    items = (await http.get("/api/realestate/complexes", params={"umd": GARAK})).json()["items"]
    return next(int(i["complexId"]) for i in items if "헬리오시티" in i["name"])


async def simulate(http: AsyncClient, complex_id: int) -> dict:  # type: ignore[type-arg]
    response = await http.get(
        "/api/realestate/simulation",
        params={"complexId": str(complex_id), "area": "30k", "buyDate": "2021-03-15"},
    )
    assert response.status_code == 200, response.text
    return response.json()  # type: ignore[no-any-return]


def expected(body: dict, ratio: str) -> dict:  # type: ignore[type-arg]
    summary, condition = body["summary"], body["condition"]
    cost = sale_cost(
        sale_price=int(summary["value"]),
        buy_price=int(condition["buyPrice"]),
        acquisition_total=int(body["acquisition"]["total"]),
        buy_date=D(condition["buyDate"]),
        sale_date=D(summary["asOf"]),
        residence_ratio=Decimal(ratio),
    )
    return {
        "brokerage": str(cost.brokerage),
        "incomeTax": str(cost.income_tax),
        "localTax": str(cost.local_tax),
        "total": str(cost.total),
        "kind": cost.kind,
        "gain": str(cost.gain),
        "taxableGain": str(cost.taxable_gain),
        "ltsdRate": format(cost.ltsd_rate, ".6f"),
        "holdingYears": cost.holding_years,
        "residenceYears": cost.residence_years,
        "basePerOwner": str(cost.base_per_owner),
    }


async def test_매도비용은_평가액으로_판다고_가정한_중개_보수와_양도소득세다(
    client, session_factory
) -> None:  # type: ignore[no-untyped-def]
    http, source = client
    body = await simulate(http, await helio(http, source, session_factory))
    summary = body["summary"]
    assert summary["value"] is not None
    assert body["condition"]["residenceRatio"] == "1.000000"
    assert summary["saleCost"] == expected(body, "1")
    after = int(summary["profit"]) - int(summary["saleCost"]["total"])
    assert summary["profitAfterSale"] == str(after)
    assert summary["returnRateAfterSale"] == str(
        quantize_rate(Decimal(after) / Decimal(summary["invested"]))
    )
    # 보유 2년(2021-03-15 → 2023-10-05)·거주 2년 — 비과세 요건 안, 장특공은 보유 3년 전이라 없다
    assert (summary["saleCost"]["holdingYears"], summary["saleCost"]["residenceYears"]) == (2, 2)
    assert summary["saleCost"]["kind"] in ("exempt", "high_price")


async def test_거주_비율을_바꾸면_비과세_판정이_바뀐다(client, session_factory) -> None:  # type: ignore[no-untyped-def]
    http, source = client
    complex_id = await helio(http, source, session_factory)
    before = await simulate(http, complex_id)
    await http.put("/api/realestate/settings/residence", json={"residenceRatio": "0"})
    after = await simulate(http, complex_id)
    assert after["condition"]["residenceRatio"] == "0.000000"
    assert after["summary"]["saleCost"] == expected(after, "0")
    assert (
        after["summary"]["saleCost"]["residenceYears"],
        after["summary"]["saleCost"]["kind"],
    ) == (0, "taxed")
    assert int(after["summary"]["saleCost"]["total"]) > int(before["summary"]["saleCost"]["total"])
    # 보유 중 값·표는 거주 비율과 무관하다
    assert (after["summary"]["profit"], after["rows"]) == (
        before["summary"]["profit"],
        before["rows"],
    )


async def test_기존_요약_키는_그대로다(client, session_factory) -> None:  # type: ignore[no-untyped-def]
    http, source = client
    summary = (await simulate(http, await helio(http, source, session_factory)))["summary"]
    for key in ("buyPrice", "invested", "holdingTaxTotal", "value", "profit", "returnRate", "asOf"):
        assert key in summary
    assert int(summary["profit"]) == int(summary["value"]) - int(summary["invested"]) - int(
        summary["holdingTaxTotal"]
    )
