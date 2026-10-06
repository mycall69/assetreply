"""부동산 거주 기간 비율 설정 (010 반복 5, T077) — FR-031, contracts/rest-api `GET`·`PUT
/api/realestate/settings/residence`.

- 행이 없으면 기본 1.000000(보유 내내 거주) — 0으로 떨어지면 비과세·장특공이 조용히 사라진다
- 0 이상 1 이하의 소수 문자열(소수 6자리까지). 그 밖은 보유세 기준 비율과 같은
  오류(`invalid_setting`) — 조용히 고치지 않는다
- **기존 `/api/realestate/settings`는 그대로다** — 응답에 거주 비율을 더하지 않는다(009 설정
  테스트가 응답 전체를 단언한다)
"""

from __future__ import annotations

import pytest
from httpx2 import ASGITransport, AsyncClient

from src.api.main import create_app
from src.db.session import get_session


@pytest.fixture
async def http(session_factory):  # type: ignore[no-untyped-def]
    app = create_app()

    async def _session():  # type: ignore[no-untyped-def]
        async with session_factory() as s:
            yield s

    app.dependency_overrides[get_session] = _session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        yield client


async def test_기본값은_100퍼센트다(http: AsyncClient) -> None:
    response = await http.get("/api/realestate/settings/residence")
    assert response.status_code == 200
    assert response.json() == {"residenceRatio": "1.000000", "isDefault": True}


async def test_저장하고_다시_읽는다(http: AsyncClient) -> None:
    saved = await http.put("/api/realestate/settings/residence", json={"residenceRatio": "0.5"})
    assert saved.json() == {"residenceRatio": "0.500000", "isDefault": False}
    assert (await http.get("/api/realestate/settings/residence")).json()[
        "residenceRatio"
    ] == "0.500000"
    zero = await http.put("/api/realestate/settings/residence", json={"residenceRatio": "0"})
    assert zero.json() == {"residenceRatio": "0.000000", "isDefault": False}
    back = await http.put("/api/realestate/settings/residence", json={"residenceRatio": "1"})
    assert back.json() == {"residenceRatio": "1.000000", "isDefault": True}


@pytest.mark.parametrize(
    "body",
    [
        {"residenceRatio": "-0.1"},
        {"residenceRatio": "1.000001"},
        {"residenceRatio": "abc"},
        {"residenceRatio": "NaN"},
        {"residenceRatio": 0.5},
        {"residenceRatio": "0.5000001"},
        {},
    ],
)
async def test_범위_밖은_거절한다(http: AsyncClient, body: dict) -> None:  # type: ignore[type-arg]
    response = await http.put("/api/realestate/settings/residence", json=body)
    assert response.status_code == 422
    assert response.json()["status"] == "invalid_setting"
    assert (await http.get("/api/realestate/settings/residence")).json()["isDefault"] is True


async def test_보유세_기준_비율_설정과_따로다(http: AsyncClient) -> None:
    await http.put("/api/realestate/settings/residence", json={"residenceRatio": "0.3"})
    assert (await http.get("/api/realestate/settings")).json() == {
        "holdingTaxBaseRatio": "0.600000",
        "isDefault": True,
    }
    await http.put("/api/realestate/settings", json={"holdingTaxBaseRatio": "0.7"})
    assert (await http.get("/api/realestate/settings/residence")).json()[
        "residenceRatio"
    ] == "0.300000"
