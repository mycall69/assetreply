"""`GET /api/fx/series` 통합 테스트 (T074, T075).

FR-032: 미수집 구간과 고시 없는 날을 값으로 메우지 않고 비어 있음으로 표현한다.
FR-032a: 차트 요청도 조회와 동일한 자동 수집 규칙을 적용한다.
"""
from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest
from httpx2 import ASGITransport, AsyncClient

from src.api.main import create_app
from src.db.dialect import upsert
from src.db.models import FxCoverage, FxRate
from src.db.session import get_session

# 2005-03-15,16,17 고시 / 18,19는 없음(휴장) / 커버리지는 3-01~3-20
QUOTES = [("2005-03-15", "1012.30"), ("2005-03-16", "1008.70"),
          ("2005-03-17", "1015.55"), ("2005-03-20", "1011.00")]


@pytest.fixture
async def client(session_factory):
    async with session_factory() as s:
        await upsert(s, FxRate, [
            {"currency_code": "USD", "quote_date": dt.date.fromisoformat(d),
             "base_rate": Decimal(v), "quote_unit": 1, "source": "ECOS:731Y001"}
            for d, v in QUOTES])
        await upsert(s, FxCoverage, [{
            "currency_code": "USD",
            "covered_from": dt.date(2005, 3, 1),
            "covered_through": dt.date(2005, 3, 20),
        }], preserve=())
        await s.commit()

    app = create_app()

    async def _override():
        async with session_factory() as s:
            yield s

    app.dependency_overrides[get_session] = _override
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


async def _series(client: AsyncClient, **params: object) -> dict[str, object]:
    return (await client.get("/api/fx/series", params={
        "currency": "USD", "from": "2005-03-14", "to": "2005-03-20", **params})).json()


class Test시계열:
    async def test_시간_순으로_반환한다(self, client: AsyncClient) -> None:
        body = await _series(client)
        dates = [p["date"] for p in body["points"]]
        assert dates == sorted(dates)

    async def test_값이_문자열이다(self, client: AsyncClient) -> None:
        body = await _series(client)
        assert all(isinstance(p["baseRate"], str) for p in body["points"])

    async def test_원본_개수를_알린다(self, client: AsyncClient) -> None:
        body = await _series(client)
        assert body["sourcePointCount"] == 4

    async def test_단위를_함께_준다(self, client: AsyncClient) -> None:
        body = await _series(client)
        assert body["quoteUnit"] == 1


class Test결측_구간:
    """FR-032 — 두 종류를 구분한다."""

    async def test_고시_없는_날을_gap으로_표시한다(self, client: AsyncClient) -> None:
        body = await _series(client)
        no_quote = [g for g in body["gaps"] if g["reason"] == "no_quote"]
        assert any(g["from"] == "2005-03-18" and g["to"] == "2005-03-19" for g in no_quote)

    async def test_미수집_구간을_구분해_표시한다(self, client: AsyncClient) -> None:
        """커버리지 밖(2005-03-14 이전)은 no_quote가 아니라 not_collected다."""
        body = (await client.get("/api/fx/series", params={
            "currency": "USD", "from": "2005-02-20", "to": "2005-03-20"})).json()
        assert any(g["reason"] == "not_collected" for g in body["gaps"])

    async def test_결측을_값으로_메우지_않는다(self, client: AsyncClient) -> None:
        """헌법 원칙 V — 없는 날짜의 포인트가 생기면 안 된다."""
        body = await _series(client)
        dates = {p["date"] for p in body["points"]}
        assert "2005-03-18" not in dates
        assert "2005-03-19" not in dates

    async def test_결측이_없으면_gaps도_비어_있다(self, client: AsyncClient) -> None:
        body = await _series(client, **{"from": "2005-03-15", "to": "2005-03-17"})
        assert body["gaps"] == []


class Test다운샘플링:
    async def test_포인트가_적으면_다운샘플링하지_않는다(self, client: AsyncClient) -> None:
        body = await _series(client)
        assert body["downsampled"] is False
        assert len(body["points"]) == 4

    async def test_알고리즘을_밝힌다(self, client: AsyncClient) -> None:
        body = await _series(client, maxPoints=2)
        assert body["algorithm"] == "lttb"
        assert body["downsampled"] is True


class Test자동_수집:
    """FR-032a — 조회와 동일한 임계값 규칙."""

    async def test_임계값_초과_미수집이면_202(self, client: AsyncClient) -> None:
        res = await client.get("/api/fx/series", params={
            "currency": "USD", "from": "1995-01-01", "to": "2005-03-20"})
        assert res.status_code == 202
        assert res.json()["status"] == "collecting"

    async def test_지원하지_않는_통화는_404(self, client: AsyncClient) -> None:
        res = await client.get("/api/fx/series", params={
            "currency": "GBP", "from": "2005-03-14", "to": "2005-03-20"})
        assert res.status_code == 404
