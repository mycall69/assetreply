"""투자처 목록의 적금 칸 (011 T044) — FR-029, contracts/rest-api §4.

- 투자처마다 `installment`를 더한다. 기존 키·다섯 투자처 순서는
  그대로다(`test_deposit_institutions_api.py`)
- 시중은행·상호금융은 `available true`와 상품 범위 설명이다. 받기 전에는 범위·시작 가능 날짜가
  `null`이다(상수로 박지 않는다)
- 시작 가능 날짜는 **두 계열을 다 받았을 때만** 있다 — max(적금 첫 달, 정기예금 첫 달 − 1년)
- 저축은행·신협·새마을금고는 `available false`와 사유다 — 정기예금 금리로 대신하지 않는다
"""
from __future__ import annotations

import pytest
from httpx2 import ASGITransport, AsyncClient

from src.api.main import create_app
from src.db.session import get_session
from tests.integration.deposit_support import TODAY, seed_rates

NONE = "출처(ECOS)에 이 투자처의 정기적금 금리 통계가 없습니다."


@pytest.fixture
async def client(session_factory):  # type: ignore[no-untyped-def]
    app = create_app()

    async def _session():  # type: ignore[no-untyped-def]
        async with session_factory() as s:
            yield s

    app.dependency_overrides[get_session] = _session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        yield c


async def listing(client) -> dict[str, dict]:  # type: ignore[no-untyped-def,type-arg]
    body = (await client.get("/api/deposit/institutions")).json()
    assert [i["key"] for i in body["institutions"]] == [
        "commercial_bank", "savings_bank", "credit_union", "mutual_finance", "saemaul"]
    return {i["key"]: i for i in body["institutions"]}


async def test_받기_전에는_고를_수_있는지와_설명만_있다(client) -> None:  # type: ignore[no-untyped-def]
    items = await listing(client)
    assert items["commercial_bank"]["installment"] == {
        "available": True, "description": "예금은행 정기적금(1~2년 만기) 평균",
        "firstMonth": None, "latestMonth": None, "checkedOn": None, "startableFrom": None}
    assert items["mutual_finance"]["installment"]["description"] == (
        "상호금융 정기적금 평균 — 만기 구분 없음")
    for key in ("savings_bank", "credit_union", "saemaul"):
        assert items[key]["installment"] == {"available": False, "reason": NONE}


async def test_두_계열을_받으면_시작_가능_날짜가_있다(client, session_factory) -> None:  # type: ignore[no-untyped-def]
    await seed_rates(session_factory, "commercial_bank_isav")
    only = (await listing(client))["commercial_bank"]["installment"]
    # 정기예금 쪽을 모르면 시작 가능 날짜를 모른다
    assert (only["firstMonth"], only["latestMonth"], only["checkedOn"], only["startableFrom"]) == (
        "2003-01", "2026-08", TODAY.isoformat(), None)
    await seed_rates(session_factory, "commercial_bank")
    items = await listing(client)
    assert items["commercial_bank"]["installment"]["startableFrom"] == "2011-01-01"
    # 정기예금 칸(008)은 그대로다
    assert items["commercial_bank"]["firstMonth"] == "2012-01"
    await seed_rates(session_factory, "mutual_finance_isav")
    await seed_rates(session_factory, "mutual_finance")
    assert (await listing(client))["mutual_finance"]["installment"]["startableFrom"] == "2012-01-01"
