"""부동산 차트 시계열 (T045) — 009 FR-031, SC-006, SC-009, contracts/rest-api `GET
/api/realestate/simulation/series`.

**계산하지 않는다** — 시뮬레이션과 같은 계산의 행을 차트 모양으로 바꾼다(표와 차트가 어긋나지 않게,
005~008과 같다).

- 점 = **첫 점은 매입일**, 그 뒤 매달 1일, 끝점은 계산 끝(오늘 한국 시간 — 보드). 매입일보다 이른
  점은 없다
- 점마다 표의 그 달 평가액·수익률과 같고 끝점은 `summary`와 같다(SC-009).
  `estimated`·`provisional`은 점마다
- 시세 없음 달은 점이 없고 `gaps`(`no_price` — 끊는다). `provisionalFrom`은 잠정 12개월의 첫 달 1일
- 202·오류는 시뮬레이션과 같다
"""
from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest
from httpx2 import ASGITransport, AsyncClient

from src.api.main import create_app
from src.api.services import realestate_lists
from src.db.models import AptComplex, AptTrade
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


async def collected(http, source, session_factory) -> dict[str, int]:  # type: ignore[no-untyped-def]
    first = (await http.get("/api/realestate/regions")).json()
    await _run(session_factory, source, first["jobId"], "region", "regions")
    body = (await http.get("/api/realestate/complexes", params={"umd": GARAK})).json()
    await _run(session_factory, source, body["trades"]["jobId"], "trade", "11710")
    async with session_factory() as s:
        details = await apt_job.running_job_id(s, "complex_details", GARAK)
    if details is not None:
        await _run(session_factory, source, details, "complex_details", GARAK)
    items = (await http.get("/api/realestate/complexes", params={"umd": GARAK})).json()["items"]
    return {i["name"]: i["complexId"] for i in items}


async def both(http, **params: str):  # type: ignore[no-untyped-def]
    table = (await http.get("/api/realestate/simulation", params=params)).json()
    series = await http.get("/api/realestate/simulation/series", params=params)
    return table, series


async def test_점은_매입일_매달_1일_끝점이고_표와_보드와_같다(client, session_factory) -> None:  # type: ignore[no-untyped-def]
    http, source = client
    names = await collected(http, source, session_factory)
    params = {"complexId": str(names["헬리오시티아파트"]), "area": "30k", "buyDate": "2021-03-15"}
    table, response = await both(http, **params)
    assert response.status_code == 200
    series = response.json()
    assert (series["from"], series["to"]) == ("2021-03-15", "2023-10-05")
    assert (series["principalCurrency"], series["basisCurrency"]) == ("KRW", "KRW")
    assert (series["downsampled"], series["algorithm"]) == (False, "lttb")
    assert series["provisionalFrom"] == "2022-11-01"
    points = series["points"]
    assert series["sourcePointCount"] == len(points)
    assert points[0]["date"] == "2021-03-15"  # 첫 점은 매입일 — 그 달 1일이 아니다
    assert [p["date"] for p in points[1:-1]] == [f"{r['month']}-01" for r in reversed(
        table["rows"][:-1])]
    assert points[-1]["date"] == "2023-10-05"
    rows = {r["month"]: r for r in table["rows"]}
    for point in points[:-1]:
        row = rows[point["date"][:7]]
        assert (point["balance"], point["returnRate"]) == (row["value"], row["returnRate"])
        assert (point["estimated"], point["provisional"]) == (row["estimated"], row["provisional"])
    end = points[-1]
    summary = table["summary"]
    assert (end["balance"], end["returnRate"]) == (summary["value"], summary["returnRate"])
    assert (end["estimated"], end["provisional"]) == (summary["estimated"],
                                                      summary["provisional"])
    assert series["gaps"] == []


async def test_시세_없음_달은_점이_없고_끊는다(client, session_factory) -> None:  # type: ignore[no-untyped-def]
    """거래가 2020-01과 2023-06뿐인 단지 — 36개월 창이 닿지 않는 2023-01~2023-05에 시세가 없다."""
    http, source = client
    await collected(http, source, session_factory)
    async with session_factory() as s:
        row = AptComplex(umd_code=GARAK, lawd_cd="11710", apt_seq="11710-99999", name="드문단지")
        s.add(row)
        for occurrence, day in enumerate(("2020-01-15", "2023-06-15")):
            s.add(AptTrade(
                lawd_cd="11710", deal_ym=day[:7].replace("-", ""), deal_date=D(day),
                apt_seq="11710-99999", umd_code=GARAK, jibun="1", apt_name="드문단지", apt_dong="",
                floor=5, excl_area=Decimal("84.0"), amount=900_000_000 + occurrence,
                occurrence=0, cancelled=False, source="molit:aptdev", ingested_at=NOW_UTC))
        await s.commit()
        complex_id = row.id
    table, response = await both(http, complexId=str(complex_id), area="30k",
                                 buyDate="2020-01-20")
    series = response.json()
    assert series["gaps"] == [{"from": "2023-01-01", "to": "2023-05-01", "reason": "no_price"}]
    dates = [p["date"] for p in series["points"]]
    assert "2022-12-01" in dates and "2023-06-01" in dates
    assert not any("2023-01-01" <= d <= "2023-05-01" for d in dates)
    no_price = [r["month"] for r in table["rows"] if r["price"] is None]
    assert sorted(no_price) == ["2023-01", "2023-02", "2023-03", "2023-04", "2023-05"]
    assert any(p["estimated"] for p in series["points"])  # 거래 없는 달은 넓은 창의 추정


async def test_202와_오류는_시뮬레이션과_같다(client, session_factory) -> None:  # type: ignore[no-untyped-def]
    http, source = client
    first = (await http.get("/api/realestate/regions")).json()
    await _run(session_factory, source, first["jobId"], "region", "regions")
    body = (await http.get("/api/realestate/complexes", params={"umd": GARAK})).json()
    helio = next(i["complexId"] for i in body["items"] if i["name"].startswith("헬리오시티"))
    params = {"complexId": str(helio), "area": "30k", "buyDate": "2021-03-15"}
    waiting = await http.get("/api/realestate/simulation/series", params=params)
    assert (waiting.status_code, waiting.json()["kind"]) == (202, "trade")
    assert waiting.json()["jobId"] == body["trades"]["jobId"]
    await _run(session_factory, source, body["trades"]["jobId"], "trade", "11710")
    early = await http.get("/api/realestate/simulation/series",
                           params={**params, "buyDate": "2020-01-15"})
    assert (early.status_code, early.json()["status"]) == (409, "before_first_trade")
    unknown = await http.get("/api/realestate/simulation/series",
                             params={**params, "complexId": "987654"})
    assert (unknown.status_code, unknown.json()["status"]) == (400, "unknown_complex")
    bad = await http.get("/api/realestate/simulation/series", params={**params, "area": "x"})
    assert (bad.status_code, bad.json()["status"]) == (400, "invalid_query")
