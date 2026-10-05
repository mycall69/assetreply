"""부동산 시계열의 그 달 실거래가 평균 (010 T010) — FR-001~FR-003, FR-006, SC-001, SC-002,
contracts/rest-api `GET /api/realestate/simulation/series`.

- `priceKind "apt_average"`, `priceCurrency "KRW"`
- 점의 `price` = 표의 그 달 `monthAverage`(같은 단지·같은 평형, 해제 제외). 첫 점(매입일)은 매입 달,
  끝점(계산 끝)은 그 달
- 표의 `monthAverage`가 빈 달 → `price null` + `priceMissing "no_trades"`. 그 점의 평가액·수익률은
  표와 같다(적용 시세 — 추정 포함)
- 시세 없음 달은 지금처럼 점이 없고 `gaps`(`no_price`)다
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


async def rare_complex(session_factory) -> int:  # type: ignore[no-untyped-def]
    """거래가 2020-01과 2023-06뿐인 단지 — 그 사이 달은 거래 없음(넓힌 창의 추정), 2023-01~05는 시세
    없음."""
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
        return int(row.id)


async def both(http, **params: str):  # type: ignore[no-untyped-def]
    table = await http.get("/api/realestate/simulation", params=params)
    series = await http.get("/api/realestate/simulation/series", params=params)
    assert (table.status_code, series.status_code) == (200, 200), (table.text, series.text)
    return table.json(), series.json()


def check_against_table(table: dict, series: dict) -> int:  # type: ignore[type-arg]
    """점마다 표의 그 달 행과 대조한다. 거래 없는 달의 수를 돌려준다."""
    rows = {r["month"]: r for r in table["rows"]}
    no_trades = 0
    for point in series["points"]:
        row = rows[point["date"][:7]]
        assert point["price"] == row["monthAverage"], point["date"]
        if row["monthAverage"] is None:
            no_trades += 1
            assert point["priceMissing"] == "no_trades", point["date"]
            assert (point["balance"], point["returnRate"]) == (row["value"], row["returnRate"])
        else:
            assert "priceMissing" not in point, point["date"]
    return no_trades


async def test_가격의_종류와_통화(client, session_factory) -> None:  # type: ignore[no-untyped-def]
    http, source = client
    names = await collected(http, source, session_factory)
    _, series = await both(http, complexId=str(names["헬리오시티아파트"]), area="30k",
                           buyDate="2021-03-15")
    assert (series["priceKind"], series["priceCurrency"]) == ("apt_average", "KRW")


async def test_점마다_표의_그_달_평균과_같다(client, session_factory) -> None:  # type: ignore[no-untyped-def]
    http, source = client
    names = await collected(http, source, session_factory)
    table, series = await both(http, complexId=str(names["헬리오시티아파트"]), area="30k",
                               buyDate="2021-03-15")
    check_against_table(table, series)
    assert series["points"][0]["date"] == "2021-03-15"
    assert series["points"][-1]["price"] == {r["month"]: r for r in table["rows"]}[
        series["points"][-1]["date"][:7]]["monthAverage"]


async def test_거래_없는_달은_비고_평가는_표와_같으며_시세_없음은_점이_없다(  # type: ignore[no-untyped-def]
        client, session_factory) -> None:
    http, source = client
    await collected(http, source, session_factory)
    complex_id = await rare_complex(session_factory)
    table, series = await both(http, complexId=str(complex_id), area="30k", buyDate="2020-01-20")
    assert check_against_table(table, series) >= 30
    assert series["gaps"] == [{"from": "2023-01-01", "to": "2023-05-01", "reason": "no_price"}]
    assert not any("2023-01-01" <= p["date"] <= "2023-05-01" for p in series["points"])
    # 추정 평가 + 실거래 없음
    assert any(p["estimated"] and p["price"] is None for p in series["points"])
