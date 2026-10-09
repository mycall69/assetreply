"""지표 화면의 그래프·다시 시도·진행 (014 T047) — FR-010, FR-012, FR-014, FR-016, FR-018, FR-019,
SC-002, SC-004,
contracts A2~A4.

- 과거 구간이 남았으면 202 + 진행(받는 중), 실패 뒤 성공이 없으면 202 `failed`
- 완성되면 단위 넷의 점·결측 `gaps`·`tailPending`·수집 상태(`lastSuccessAt`·`lastFailure`)
- 오늘 잠정 꼬리는 현재 시세 캐시에서 붙는다. 환율에는 붙지 않는다(다른 계열 — 명확화 2)
- 점 한도를 넘으면 실제 점을 골라 줄인다
- 환율 그래프는 외환 메뉴의 고시 이력과 같은 날 같은 값이다(SC-004). 모자라면 외환 수집 경로에
  넘긴다 — ECOS를 부르지 않는다
- 반복 2026-10-10(T088): 환율도 대시보드의 진행 경로다(외환 진행 스트림은 사건 이름·모양이 다르다).
  마지막 외환 수집이 실패했고 받는 중이 아니면 202 `failed{kind: "fx_collection"}`이고 외환 수집을
  다시 요청하지 않는다 — 다시 물을 때마다 요청하면 풀리지 않는 실패에 ECOS를 계속 부른다
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import json
from decimal import Decimal

import pytest
from httpx2 import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.api.main import create_app
from src.api.routes import dashboard_series
from src.api.services import market_quotes
from src.config.settings import load_settings
from src.db.models import FxCollectionJob, FxCoverage, FxRate, JobStatus
from src.db.session import get_session
from src.repository import market_daily
from src.simulation.market_quote import MarketQuote, Previous
from src.worker import market_worker

D = dt.date
NOW = dt.datetime(2026, 10, 9, 14, 0, tzinfo=dt.UTC)  # 뉴욕 10:00(장중)
AT = dt.datetime(2026, 10, 9, 5, 0)


def weekdays(start: dt.date, end: dt.date, *, skip: tuple[dt.date, ...] = ()) -> list[dt.date]:
    out = []
    day = start
    while day <= end:
        if day.weekday() < 5 and day not in skip:
            out.append(day)
        day += dt.timedelta(days=1)
    return out


class Quotes:
    """현재 시세 서비스 대역 — `quote(id)`만 쓴다."""

    def __init__(self) -> None:
        self.value: MarketQuote | None = MarketQuote(
            value=Decimal("7800.000000"),
            value_time=NOW,
            session_date=D(2026, 10, 9),
            state="open",
            provisional=True,
            delay_minutes=None,
            previous=Previous(Decimal("7765.360000"), D(2026, 10, 8), "history"),
            change=Decimal("34.640000"),
            change_rate=Decimal("0.004461"),
            change_rate_blank=None,
            direction="up",
        )

    async def quote(self, indicator_id: str) -> MarketQuote | None:
        return self.value


async def seed(
    factory: async_sessionmaker[AsyncSession],
    indicator_id: str,
    days: list[dt.date],
    *,
    first: dt.date,
    through: dt.date,
    covered_from: dt.date | None = None,
) -> None:
    async with factory() as s:
        await market_daily.store_closes(
            s, indicator_id, [(d, Decimal(100 + i)) for i, d in enumerate(days)], detected_at=AT
        )
        await market_daily.record_coverage(s, indicator_id, covered_from or first, through)
        await market_daily.record_first_day(s, indicator_id, first)
        await market_daily.record_success(s, indicator_id, at=AT)
        await s.commit()


@pytest.fixture
def quotes() -> Quotes:
    return Quotes()


@pytest.fixture
async def client(session_factory, quotes, monkeypatch):  # type: ignore[no-untyped-def]
    market_quotes.set_shared_service(quotes)  # type: ignore[arg-type]
    monkeypatch.setattr(dashboard_series, "utc_now", lambda: NOW)
    app = create_app()

    async def _session():  # type: ignore[no-untyped-def]
        async with session_factory() as s:
            yield s

    app.dependency_overrides[get_session] = _session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    market_quotes.set_shared_service(None)


DAYS = weekdays(D(2025, 1, 2), D(2026, 10, 8))


async def test_과거_구간이_남았으면_202와_진행(client: AsyncClient, session_factory) -> None:  # type: ignore[no-untyped-def]
    await seed(
        session_factory,
        "sp500",
        DAYS[-200:],
        first=D(1927, 12, 30),
        through=D(2026, 10, 8),
        covered_from=DAYS[-200],
    )
    res = await client.get("/api/dashboard/indicators/sp500/series?unit=monthly")
    assert res.status_code == 202
    body = res.json()
    assert body["status"] == "collecting" and body["failure"] is None
    assert body["progress"]["firstDay"] == "1927-12-30"
    assert body["progress"]["remainingDays"] == (DAYS[-200] - D(1927, 12, 30)).days
    assert body["progressUrl"] == "/api/dashboard/indicators/sp500/progress"


async def test_아직_아무것도_없으면_202(client: AsyncClient) -> None:
    res = await client.get("/api/dashboard/indicators/kospi/series")
    assert res.status_code == 202
    assert res.json()["progress"]["firstDay"] is None


async def test_실패_뒤_성공이_없으면_failed(client: AsyncClient, session_factory) -> None:  # type: ignore[no-untyped-def]
    async with session_factory() as s:
        await market_daily.record_failure(s, "vix", at=AT, kind="rate_limited", message="한도")
        await s.commit()
    body = (await client.get("/api/dashboard/indicators/vix/series")).json()
    assert body["status"] == "failed"
    assert body["failure"]["kind"] == "rate_limited" and body["failure"]["message"] == "한도"


async def test_완성되면_단위_넷과_잠정_꼬리(client: AsyncClient, session_factory) -> None:  # type: ignore[no-untyped-def]
    await seed(session_factory, "sp500", DAYS, first=DAYS[0], through=D(2026, 10, 8))
    for unit, last in (
        ("daily", "2026-10-09"),
        ("weekly", "2026-10-09"),
        ("monthly", "2026-10-09"),
        ("yearly", "2026-10-09"),
    ):
        res = await client.get(f"/api/dashboard/indicators/sp500/series?unit={unit}")
        assert res.status_code == 200, unit
        body = res.json()
        assert body["unit"] == unit
        point = body["points"][-1]
        assert (
            point["date"] == last
            and point["value"] == "7800.000000"
            and point["provisional"] is True
        )
        if unit != "daily":
            assert point["ongoing"] is True
    body = (await client.get("/api/dashboard/indicators/sp500/series")).json()
    assert body["unit"] == "daily"
    assert body["history"]["source"] == "yahoo"
    assert body["history"]["firstDate"] == DAYS[0].isoformat()
    assert body["history"]["lastDate"] == "2026-10-08"
    assert body["history"]["tailPending"] is False
    assert body["history"]["lastFailure"] is None
    assert body["history"]["lastSuccessAt"] == "2026-10-09T05:00:00Z"
    assert body["downsampled"] is False and body["sourcePointCount"] == len(DAYS) + 1
    assert body["indicator"]["id"] == "sp500" and body["gaps"] == []


async def test_틀린_단위는_daily(client: AsyncClient, session_factory) -> None:  # type: ignore[no-untyped-def]
    await seed(session_factory, "sp500", DAYS, first=DAYS[0], through=D(2026, 10, 8))
    body = (await client.get("/api/dashboard/indicators/sp500/series?unit=hourly")).json()
    assert body["unit"] == "daily"


async def test_결측은_gaps이고_휴장은_아니다(client: AsyncClient, session_factory) -> None:  # type: ignore[no-untyped-def]
    holiday = D(2026, 9, 7)
    missing = D(2026, 9, 16)
    await seed(
        session_factory,
        "dow",
        weekdays(D(2025, 1, 2), D(2026, 10, 8), skip=(holiday,)),
        first=D(2025, 1, 2),
        through=D(2026, 10, 8),
    )
    await seed(
        session_factory,
        "sp500",
        weekdays(D(2025, 1, 2), D(2026, 10, 8), skip=(holiday, missing)),
        first=D(2025, 1, 2),
        through=D(2026, 10, 8),
    )
    body = (await client.get("/api/dashboard/indicators/sp500/series")).json()
    assert body["gaps"] == [{"from": "2026-09-16", "to": "2026-09-16", "reason": "missing"}]


async def test_이어_받기가_늦으면_tailPending과_실패_줄(
    client: AsyncClient, session_factory
) -> None:  # type: ignore[no-untyped-def]
    await seed(session_factory, "sp500", DAYS[:-3], first=DAYS[0], through=DAYS[-4])
    async with session_factory() as s:
        await market_daily.record_failure(
            s, "sp500", at=AT + dt.timedelta(hours=1), kind="connection", message="연결"
        )
        await s.commit()
    body = (await client.get("/api/dashboard/indicators/sp500/series")).json()
    assert body["history"]["tailPending"] is True
    assert body["history"]["lastFailure"] == {
        "kind": "connection",
        "message": "연결",
        "at": "2026-10-09T06:00:00Z",
    }


async def test_점_한도를_넘으면_실제_점을_골라_줄인다(
    client: AsyncClient, session_factory, monkeypatch
) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(
        dashboard_series,
        "load_settings",
        lambda: dataclasses.replace(load_settings(), dashboard_series_max_points=50),
    )
    await seed(session_factory, "sp500", DAYS, first=DAYS[0], through=D(2026, 10, 8))
    body = (await client.get("/api/dashboard/indicators/sp500/series")).json()
    assert body["downsampled"] is True and len(body["points"]) <= 50
    values = {
        d.isoformat(): str(Decimal(100 + i).quantize(Decimal("0.000001")))
        for i, d in enumerate(DAYS)
    }
    values["2026-10-09"] = "7800.000000"
    for p in body["points"]:
        assert values[p["date"]] == p["value"]


async def test_환율은_외환_고시_이력과_같다(client: AsyncClient, session_factory) -> None:  # type: ignore[no-untyped-def]
    days = weekdays(D(2026, 9, 1), D(2026, 10, 8))
    async with session_factory() as s:
        for i, d in enumerate(days):
            s.add(
                FxRate(
                    currency_code="USD",
                    quote_date=d,
                    base_rate=Decimal("1300") + i,
                    quote_unit=1,
                    source="ecos",
                    is_provisional=d == days[-1],
                )
            )
        s.add(FxCoverage(currency_code="USD", covered_from=days[0], covered_through=D(2026, 10, 9)))
        await s.commit()
    res = await client.get("/api/dashboard/indicators/usd/series")
    assert res.status_code == 200
    body = res.json()
    assert body["history"]["source"] == "ecos"
    fx = (await client.get(f"/api/fx/series?currency=USD&from={days[0]}&to=2026-10-09")).json()
    assert [(p["date"], p["value"]) for p in body["points"]] == [
        (p["date"], p["baseRate"]) for p in fx["points"]
    ]
    assert body["points"][-1]["provisional"] is True  # 외환의 잠정 고시 — 시장 환율 꼬리가 아니다
    assert all(p["value"] != "7800.000000" for p in body["points"])


class Queue:
    """외환 시작 큐 대역 — `in_progress`만 쓴다."""

    def __init__(self, busy: str | None) -> None:
        self.in_progress = busy


def recorder(requested: list[str]):  # type: ignore[no-untyped-def]
    async def ticket(session, code, **_):  # type: ignore[no-untyped-def]
        requested.append(code)
        from src.api.services.collection_gate import CollectionTicket

        return CollectionTicket(
            code, "queued", None, None, f"/api/fx/collection/stream?currency={code}"
        )

    return ticket


FINISHED = dt.datetime(2026, 10, 9, 22, 0)  # 외환 작업의 종료 시각은 서버 지역 시각(001 관례)


async def failed_fx_job(
    factory: async_sessionmaker[AsyncSession],
    code: str = "JPY",
    *,
    status: JobStatus = JobStatus.FAILED,
    error: str = "ECOS 인증키가 유효하지 않습니다.",
) -> None:
    async with factory() as s:
        s.add(
            FxCollectionJob(
                currency_code=code,
                range_start=D(1990, 1, 1),
                range_end=D(2026, 10, 9),
                status=status,
                chunks_total=10,
                chunks_done=0 if status is JobStatus.FAILED else 3,
                finished_at=FINISHED,
                last_error=error,
            )
        )
        await s.commit()


def utc_z(local: dt.datetime) -> str:
    return local.astimezone(dt.UTC).replace(tzinfo=None).isoformat() + "Z"


async def test_환율_이력이_모자라면_외환_수집_경로(client: AsyncClient, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    requested: list[str] = []
    monkeypatch.setattr(dashboard_series, "ensure_background_job", recorder(requested))
    monkeypatch.setattr(dashboard_series, "get_queue", lambda: Queue(None))
    res = await client.get("/api/dashboard/indicators/jpy/series")
    assert res.status_code == 202
    body = res.json()
    # 014 승인 2026-10-10 — 진행 주소가 외환 진행 스트림이 아니라 대시보드 진행 경로다(T088)
    assert body["status"] == "collecting" and body["failure"] is None
    assert body["progressUrl"] == "/api/dashboard/indicators/jpy/progress"
    assert set(body["progress"]) == {"firstDay", "coveredFrom", "coveredThrough", "remainingDays"}
    assert requested == ["JPY"]


@pytest.mark.parametrize("status", [JobStatus.FAILED, JobStatus.PARTIAL])
async def test_환율_외환_수집이_실패했으면_failed이고_다시_요청하지_않는다(
    client: AsyncClient, session_factory, monkeypatch, status: JobStatus
) -> None:  # type: ignore[no-untyped-def]
    requested: list[str] = []
    monkeypatch.setattr(dashboard_series, "ensure_background_job", recorder(requested))
    monkeypatch.setattr(dashboard_series, "get_queue", lambda: Queue(None))
    await failed_fx_job(session_factory, status=status)
    res = await client.get("/api/dashboard/indicators/jpy/series")
    assert res.status_code == 202
    body = res.json()
    assert body["status"] == "failed"
    assert body["failure"] == {
        "kind": "fx_collection",
        "message": "ECOS 인증키가 유효하지 않습니다.",
        "at": utc_z(FINISHED),
    }
    assert body["progressUrl"] == "/api/dashboard/indicators/jpy/progress"
    assert requested == []


async def test_환율_큐가_그_통화를_처리_중이면_실패보다_받는_중이다(
    client: AsyncClient, session_factory, monkeypatch
) -> None:  # type: ignore[no-untyped-def]
    requested: list[str] = []
    monkeypatch.setattr(dashboard_series, "ensure_background_job", recorder(requested))
    monkeypatch.setattr(dashboard_series, "get_queue", lambda: Queue("JPY"))
    await failed_fx_job(session_factory)
    body = (await client.get("/api/dashboard/indicators/jpy/series")).json()
    assert body["status"] == "collecting" and body["failure"] is None


async def test_환율_다시_시도는_외환_수집을_요청한다(
    client: AsyncClient, session_factory, monkeypatch
) -> None:  # type: ignore[no-untyped-def]
    requested: list[str] = []
    monkeypatch.setattr(dashboard_series, "ensure_background_job", recorder(requested))
    await failed_fx_job(session_factory)
    res = await client.post("/api/dashboard/indicators/jpy/collect")
    assert res.status_code == 202
    assert requested == ["JPY"]


async def test_환율_진행_스트림(session_factory, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(dashboard_series, "utc_now", lambda: NOW)
    monkeypatch.setattr(dashboard_series, "get_queue", lambda: Queue(None))
    async with session_factory() as s:
        frames = [f async for f in dashboard_series.stream_body(s, "jpy", max_frames=1)]
    event, data = frames[0].strip().split("\n")
    assert event == "event: snapshot"
    assert set(json.loads(data.removeprefix("data: "))) == {
        "firstDay",
        "coveredFrom",
        "coveredThrough",
        "remainingDays",
    }
    await failed_fx_job(session_factory)
    async with session_factory() as s:
        frames = [f async for f in dashboard_series.stream_body(s, "jpy", max_frames=3)]
    event, data = frames[-1].strip().split("\n")
    assert event == "event: failed"
    assert json.loads(data.removeprefix("data: ")) == {
        "id": "jpy",
        "kind": "fx_collection",
        "message": "ECOS 인증키가 유효하지 않습니다.",
    }
    days = weekdays(D(2026, 9, 1), D(2026, 10, 8))
    async with session_factory() as s:
        for i, d in enumerate(days):
            s.add(
                FxRate(
                    currency_code="JPY",
                    quote_date=d,
                    base_rate=Decimal("900") + i,
                    quote_unit=100,
                    source="ecos",
                    is_provisional=False,
                )
            )
        s.add(FxCoverage(currency_code="JPY", covered_from=days[0], covered_through=D(2026, 10, 9)))
        await s.commit()
    async with session_factory() as s:
        frames = [f async for f in dashboard_series.stream_body(s, "jpy", max_frames=3)]
    assert frames[-1].startswith("event: completed")


async def test_없는_지표는_404(client: AsyncClient) -> None:
    res = await client.get("/api/dashboard/indicators/kospii/series")
    assert res.status_code == 404
    assert res.json()["status"] == "unknown_indicator"
    assert (await client.post("/api/dashboard/indicators/kospii/collect")).status_code == 404


async def test_다시_시도는_워커를_깨운다(client: AsyncClient) -> None:
    event = market_worker.wake_event()
    event.clear()
    res = await client.post("/api/dashboard/indicators/kospi/collect")
    assert res.status_code == 202 and res.json()["status"] == "queued"
    assert event.is_set()


async def test_진행_스트림(session_factory) -> None:  # type: ignore[no-untyped-def]
    await seed(
        session_factory,
        "sp500",
        DAYS[-10:],
        first=D(1927, 12, 30),
        through=D(2026, 10, 8),
        covered_from=DAYS[-10],
    )
    async with session_factory() as s:
        frames = [f async for f in dashboard_series.stream_body(s, "sp500", max_frames=1)]
    event, data = frames[0].strip().split("\n")
    assert event == "event: snapshot"
    snapshot = json.loads(data.removeprefix("data: "))
    assert snapshot["firstDay"] == "1927-12-30" and snapshot["coveredFrom"] == DAYS[-10].isoformat()
    async with session_factory() as s:
        await market_daily.record_coverage(s, "sp500", D(1927, 12, 30), DAYS[-11])
        await s.commit()
    async with session_factory() as s:
        frames = [f async for f in dashboard_series.stream_body(s, "sp500", max_frames=3)]
    assert frames[-1].startswith("event: completed")
    async with session_factory() as s:
        await market_daily.record_failure(s, "vix", at=AT, kind="blocked", message="막힘")
        await s.commit()
    async with session_factory() as s:
        frames = [f async for f in dashboard_series.stream_body(s, "vix", max_frames=3)]
    assert frames[-1].startswith("event: failed")
