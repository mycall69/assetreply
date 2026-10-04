"""예금 투자처 목록 (T014) — 008 FR-003, FR-006, contracts/rest-api `GET /api/deposit/institutions`.

라디오 버튼의 순서·이름·설명과 받아 둔 범위다. 받기 전에는 시작 가능 날짜를 모른다(research
R8-12) — 상수로 박지 않는다.
"""
from __future__ import annotations

import datetime as dt

import pytest
from httpx2 import ASGITransport, AsyncClient

from src.api.main import create_app
from src.db.session import get_session
from src.repository import deposit_rate
from tests.integration.deposit_support import TODAY, seed_rates

D = dt.date.fromisoformat


@pytest.fixture
async def client(session_factory):  # type: ignore[no-untyped-def]
    app = create_app()

    async def _session():  # type: ignore[no-untyped-def]
        async with session_factory() as s:
            yield s

    app.dependency_overrides[get_session] = _session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        yield c


class Test투자처_목록:
    async def test_다섯_투자처의_순서와_이름과_출처(self, client) -> None:  # type: ignore[no-untyped-def]
        body = (await client.get("/api/deposit/institutions")).json()
        assert [i["key"] for i in body["institutions"]] == [
            "commercial_bank", "savings_bank", "credit_union", "mutual_finance", "saemaul"]
        assert [i["name"] for i in body["institutions"]] == [
            "시중은행", "저축은행", "신협", "상호금융", "새마을금고"]
        assert all(i["description"] for i in body["institutions"])
        assert body["source"] == "한국은행 경제통계시스템(ECOS)"
        assert body["basis"] == "신규취급액 기준 가중평균"

    async def test_받기_전에는_범위를_모른다(self, client) -> None:  # type: ignore[no-untyped-def]
        first = (await client.get("/api/deposit/institutions")).json()["institutions"][0]
        assert (first["firstMonth"], first["latestMonth"], first["checkedOn"]) == (None, None, None)

    async def test_받은_뒤에는_첫_달·마지막_달·확인한_날(self, client, session_factory) -> None:  # type: ignore[no-untyped-def]
        await seed_rates(session_factory, "savings_bank")
        body = (await client.get("/api/deposit/institutions")).json()["institutions"]
        savings = next(i for i in body if i["key"] == "savings_bank")
        assert (savings["firstMonth"], savings["latestMonth"], savings["checkedOn"]) == (
            "1997-08", "2026-08", TODAY.isoformat())

    async def test_커버리지_저장소(self, session_factory) -> None:
        await seed_rates(session_factory, "saemaul")
        async with session_factory() as s:
            coverage = await deposit_rate.get_coverage(s, "saemaul")
        assert coverage is not None and coverage.first_month == D("2012-01-01")
