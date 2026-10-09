"""`GET /api/dashboard/quotes` (014 T023) — FR-003~FR-005, FR-009, FR-018, SC-003, contracts A1.

출처는 실측 spark 본문(2026-10-09 13:21 UTC — 한글날 밤, 미국 장 전)을 돌려주는 스텁이다(네트워크
없음). 이력은 시험 DB다.

- 응답은 늘 15개이고 `order` 차례다. 값은 문자열이다(원칙 VI)
- 카드의 전일은 이력이 있으면 이력이다(`history`), 지우면 출처로 물러난다(`source`)
- 환율 셋은 출처(`source_fx`) + `market_fx` 주석, 선물은 `future_roll`
- 출처가 모두 실패해도 200이다
- 대시보드는 외환 고시 이력(`fx_rate`)에 아무것도 쓰지 않는다(명확화 2)
"""

from __future__ import annotations

import dataclasses
import datetime as dt
from collections.abc import Sequence
from decimal import Decimal
from pathlib import Path

import pytest
from httpx2 import ASGITransport, AsyncClient
from sqlalchemy import func, select

from src.api.main import create_app
from src.api.services import market_quotes
from src.api.services.market_quotes import DbMarketHistory, MarketQuoteService
from src.config.settings import load_settings
from src.db.models import FxRate
from src.ingestion.yahoo.errors import StockSourceUnavailable
from src.ingestion.yahoo.market import QuoteFetch
from src.ingestion.yahoo.market_parse import load, parse_spark
from src.ingestion.yahoo.market_symbols import SYMBOLS
from src.repository import market_daily

FIX = Path(__file__).parents[1] / "contract" / "fixtures" / "market"
NOW = dt.datetime(2026, 10, 9, 13, 21, 30, tzinfo=dt.UTC)
AT = dt.datetime(2026, 10, 9, 5, 0)


class SparkSource:
    def __init__(self) -> None:
        self.fail = False

    async def fetch_quotes(self, indicator_ids: Sequence[str]) -> QuoteFetch:
        if self.fail:
            raise StockSourceUnavailable("시세 출처가 응답하지 않습니다.")
        parsed = parse_spark(load((FIX / "spark_15.json").read_text(encoding="utf-8")))
        quotes = {}
        for indicator_id in indicator_ids:
            found = parsed.get(SYMBOLS[indicator_id])
            if found is not None:
                quotes[indicator_id] = found
        return QuoteFetch(quotes, {})


@pytest.fixture
def source() -> SparkSource:
    return SparkSource()


@pytest.fixture
async def client(session_factory, source):  # type: ignore[no-untyped-def]
    settings = dataclasses.replace(load_settings(), dashboard_refresh_seconds=60)
    market_quotes.set_shared_service(
        MarketQuoteService(source, DbMarketHistory(session_factory), settings, clock=lambda: NOW)
    )
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    market_quotes.set_shared_service(None)


def by_id(body: dict[str, object]) -> dict[str, dict[str, object]]:
    items = body["indicators"]
    assert isinstance(items, list)
    return {str(i["id"]): i for i in items}


async def test_15개를_차례대로(client: AsyncClient) -> None:
    res = await client.get("/api/dashboard/quotes")
    assert res.status_code == 200
    body = res.json()
    assert [i["order"] for i in body["indicators"]] == list(range(1, 16))
    assert body["refreshAfterSeconds"] == 60
    kospi = by_id(body)["kospi"]
    assert set(kospi) == {
        "id",
        "name",
        "group",
        "order",
        "unit",
        "kind",
        "market",
        "notes",
        "status",
        "quote",
        "stale",
        "failure",
    }
    assert kospi["market"] == {"key": "krx", "timezone": "Asia/Seoul"}
    quote = kospi["quote"]
    assert isinstance(quote, dict)
    assert set(quote) == {
        "value",
        "valueTime",
        "sessionDate",
        "state",
        "provisional",
        "delayMinutes",
        "previous",
        "change",
        "changeRate",
        "changeRateBlank",
        "direction",
    }
    assert quote["value"] == "6625.930000" and isinstance(quote["change"], str)
    assert (quote["state"], quote["sessionDate"]) == ("holiday", "2026-10-08")


async def test_이력이_있으면_이력의_전일이다(client: AsyncClient, session_factory) -> None:  # type: ignore[no-untyped-def]
    async with session_factory() as s:
        await market_daily.store_closes(
            s, "kospi", [(dt.date(2026, 10, 7), Decimal("6803.9"))], detected_at=AT
        )
        await market_daily.record_coverage(s, "kospi", dt.date(2024, 10, 9), dt.date(2026, 10, 8))
        await s.commit()
    quote = by_id((await client.get("/api/dashboard/quotes")).json())["kospi"]["quote"]
    assert isinstance(quote, dict)
    assert quote["previous"] == {"close": "6803.900000", "date": "2026-10-07", "from": "history"}
    assert quote["change"] == "-177.970000"


async def test_이력이_없으면_출처로_물러난다(client: AsyncClient) -> None:
    quote = by_id((await client.get("/api/dashboard/quotes")).json())["kospi"]["quote"]
    assert isinstance(quote, dict)
    assert quote["previous"] == {"close": "6803.900000", "date": None, "from": "source"}


async def test_환율과_선물의_주석(client: AsyncClient) -> None:
    items = by_id((await client.get("/api/dashboard/quotes")).json())
    for fx in ("usd", "jpy", "eur"):
        assert items[fx]["notes"] == ["market_fx"]
        previous = items[fx]["quote"]["previous"]  # type: ignore[index]
        assert previous["from"] == "source_fx"
        assert items[fx]["market"] == {"key": "fx", "timezone": "Europe/London"}
    jpy = items["jpy"]["quote"]
    assert isinstance(jpy, dict) and jpy["value"].startswith("844.")
    assert items["wti"]["notes"] == ["future_roll"] and items["gold"]["notes"] == ["future_roll"]


async def test_출처가_실패해도_200(client: AsyncClient, source: SparkSource) -> None:
    source.fail = True
    res = await client.get("/api/dashboard/quotes")
    assert res.status_code == 200
    items = by_id(res.json())
    assert len(items) == 15
    assert {i["status"] for i in items.values()} == {"failed"}
    assert items["kospi"]["failure"] == {
        "kind": "connection",
        "message": "시세 출처가 응답하지 않습니다.",
    }


async def test_외환_고시_이력에_쓰지_않는다(client: AsyncClient, session_factory) -> None:  # type: ignore[no-untyped-def]
    async with session_factory() as s:
        before = (await s.execute(select(func.count()).select_from(FxRate))).scalar_one()
    await client.get("/api/dashboard/quotes")
    async with session_factory() as s:
        after = (await s.execute(select(func.count()).select_from(FxRate))).scalar_one()
    assert before == after


async def test_서비스가_없으면_503() -> None:
    market_quotes.set_shared_service(None)
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get("/api/dashboard/quotes")
    assert res.status_code == 503
