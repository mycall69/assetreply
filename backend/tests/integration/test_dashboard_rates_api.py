"""기준금리 경로 (014 반복 2026-10-11d T204) — FR-040~FR-042, SC-025, SC-026, contracts A14~A17.

- A14 칸: 은행 다섯이 늘 차례대로, **DB만 읽는다**(출처를 부르지 않는다). 금리·전회대비는 서버
  글자(소수 둘째 자리 이상), 첫 결정의 전회대비는
  `null`. 상태 — 결정이 있으면 `ready`(성공 뒤의 실패면 `failure`도), 없고 실패도 없으면
  `collecting`, 없고 실패면 `failed`
- 다음 결정 예정일은 오늘(한국)보다 이르면 `null`. 결정일은 한국 날짜, 발표 시각은 UTC(자리 표시면
  `null`)
- A15 모달: 같은 머리 + 결정 전부(최신부터), 저장된 기간. 없는 은행 404
- A16 변화 까닭: 공유 서비스의 본문 그대로, 없는 은행 404, 서비스가 없으면 503
- A17 다시 시도: 202 — 워커를 깨운다(이 요청에서 출처를 부르지 않는다)
"""

from __future__ import annotations

import dataclasses
import datetime as dt
from decimal import Decimal

import pytest
from httpx2 import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.api.main import create_app
from src.api.routes import dashboard_rates
from src.api.services import policy_rate_commentary
from src.config.settings import load_settings
from src.db.session import get_session
from src.ingestion.naver_rate.parse import SourceDecision
from src.repository import policy_rate_repository as repo
from src.simulation.policy_rate import Bank
from src.worker import policy_rate_worker

D = dt.date
NOW = dt.datetime(2026, 10, 11, 9, 40, tzinfo=dt.UTC)  # 한국 2026-10-11 18:40
AT = NOW.replace(tzinfo=None)
UTC = dt.UTC
Factory = async_sessionmaker[AsyncSession]


async def seed(
    factory: Factory,
    bank: str,
    decisions: list[SourceDecision],
    *,
    next_meeting: dt.date | None = None,
    success: dt.datetime | None = AT,
    complete: bool = True,
) -> None:
    async with factory() as s:
        await repo.store_decisions(s, bank, decisions, ingested_at=AT)
        await repo.set_next_meeting(s, bank, next_meeting)
        if complete:
            await repo.mark_history_complete(s, bank)
        if success is not None:
            await repo.record_success(s, bank, at=success)
        await s.commit()


async def fail(factory: Factory, bank: str, at: dt.datetime, kind: str = "connection") -> None:
    async with factory() as s:
        await repo.record_failure(
            s, bank, at=at, kind=kind, message="기준금리 출처에 연결하지 못했습니다.")
        await s.commit()


BOK = [
    SourceDecision(D(2026, 8, 27), dt.datetime(2026, 8, 27, 1, 0, tzinfo=UTC), Decimal("3.00")),
    SourceDecision(D(2026, 7, 16), dt.datetime(2026, 7, 16, 1, 0, tzinfo=UTC), Decimal("2.75")),
    SourceDecision(D(2026, 5, 28), None, Decimal("2.75")),
    SourceDecision(D(2016, 1, 14), None, Decimal("1.50")),
]
BOJ = [
    SourceDecision(D(2026, 9, 18), dt.datetime(2026, 9, 18, 2, 54, 4, tzinfo=UTC), Decimal("1.25")),
    SourceDecision(D(2024, 1, 23), None, Decimal("-0.10")),
]


class Commentary:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def body(self, bank: Bank) -> dict[str, object]:
        self.calls.append(bank.id)
        return {"bank": bank.id, "status": "none", "items": [], "decisionDate": None,
                "failure": None}


@pytest.fixture
async def client(session_factory, monkeypatch):  # type: ignore[no-untyped-def]
    monkeypatch.setattr(dashboard_rates, "utc_now", lambda: NOW)
    policy_rate_commentary.set_shared_service(Commentary())  # type: ignore[arg-type]
    app = create_app()

    async def _session():  # type: ignore[no-untyped-def]
        async with session_factory() as s:
            yield s

    app.dependency_overrides[get_session] = _session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    policy_rate_commentary.set_shared_service(None)


async def rates_of(client: AsyncClient) -> list[dict[str, object]]:
    body = (await client.get("/api/dashboard/rates")).json()
    banks: list[dict[str, object]] = body["banks"]
    return banks


class Test칸:
    async def test_다섯_은행이_차례대로(self, client: AsyncClient) -> None:
        res = await client.get("/api/dashboard/rates")
        assert res.status_code == 200
        body = res.json()
        assert [b["bank"] for b in body["banks"]] == ["fed", "bok", "ecb", "boe", "boj"]
        assert body["source"] == "네이버 증권"
        assert body["sourceUrl"] == (
            "https://stock.naver.com/market/marketindex/bondAndInterest/standardInterest")
        assert body["refreshAfterSeconds"] == load_settings().dashboard_refresh_seconds
        # 아직 아무것도 받지 않았다 — 받는 중
        assert {b["state"] for b in body["banks"]} == {"collecting"}
        fed = body["banks"][0]
        assert (fed["name"], fed["flag"], fed["rateKind"]) == (
            "미국연방준비은행", "🇺🇸", "연방기금금리 목표 범위 상단")
        assert (fed["rate"], fed["change"], fed["direction"], fed["decidedOn"]) == (
            None, None, None, None)

    async def test_받은_은행의_금리_전회대비_결정일(
        self, client: AsyncClient, session_factory: Factory
    ) -> None:
        await seed(session_factory, "bok", BOK, next_meeting=D(2026, 10, 22))
        bok = (await rates_of(client))[1]
        assert bok == {
            "bank": "bok", "name": "한국은행", "flag": "🇰🇷", "rateKind": "기준금리",
            "rate": "3.00", "change": "0.25", "direction": "up",
            "decidedOn": "2026-08-27", "announcedAt": "2026-08-27T01:00:00Z",
            "nextMeetingOn": "2026-10-22", "state": "ready", "failure": None,
            "lastSuccessAt": "2026-10-11T09:40:00Z",
        }

    async def test_마이너스_금리와_자리_표시_시각(
        self, client: AsyncClient, session_factory: Factory
    ) -> None:
        await seed(session_factory, "boj", BOJ)
        boj = (await rates_of(client))[4]
        assert (boj["rate"], boj["change"], boj["direction"]) == ("1.25", "1.35", "up")
        detail = (await client.get("/api/dashboard/rates/boj")).json()
        assert detail["decisions"][1] == {
            "decidedOn": "2024-01-23", "announcedAt": None, "rate": "-0.10", "change": None,
            "direction": None}

    async def test_첫_결정만이면_전회대비가_없다(
        self, client: AsyncClient, session_factory: Factory
    ) -> None:
        await seed(session_factory, "ecb", [SourceDecision(D(2026, 9, 10), None, Decimal("2.65"))])
        ecb = (await rates_of(client))[2]
        assert (ecb["rate"], ecb["change"], ecb["direction"], ecb["state"]) == (
            "2.65", None, None, "ready")

    async def test_지난_다음_결정일은_null(
        self, client: AsyncClient, session_factory: Factory
    ) -> None:
        await seed(session_factory, "bok", BOK, next_meeting=D(2026, 10, 10))
        assert (await rates_of(client))[1]["nextMeetingOn"] is None

    async def test_받은_값이_없고_실패면_failed(
        self, client: AsyncClient, session_factory: Factory
    ) -> None:
        await fail(session_factory, "boe", AT, kind="blocked")
        boe = (await rates_of(client))[3]
        assert boe["state"] == "failed"
        assert boe["failure"] == {
            "kind": "blocked", "message": "기준금리 출처에 연결하지 못했습니다.",
            "at": "2026-10-11T09:40:00Z"}

    async def test_받은_값이_있고_그_뒤에_실패면_ready와_failure(
        self, client: AsyncClient, session_factory: Factory
    ) -> None:
        await seed(session_factory, "bok", BOK, success=AT - dt.timedelta(hours=1))
        await fail(session_factory, "bok", AT)
        bok = (await rates_of(client))[1]
        assert bok["state"] == "ready" and bok["rate"] == "3.00"
        assert bok["failure"]["kind"] == "connection"  # type: ignore[index]

    async def test_실패_뒤에_성공했으면_failure가_없다(
        self, client: AsyncClient, session_factory: Factory
    ) -> None:
        await fail(session_factory, "bok", AT - dt.timedelta(hours=1))
        await seed(session_factory, "bok", BOK, success=AT)
        assert (await rates_of(client))[1]["failure"] is None

    async def test_받는_중에_실패가_없으면_collecting(
        self, client: AsyncClient, session_factory: Factory
    ) -> None:
        await seed(session_factory, "fed", [], success=None, complete=False)
        assert (await rates_of(client))[0]["state"] == "collecting"


class Test모달:
    async def test_결정_전부와_저장된_기간(
        self, client: AsyncClient, session_factory: Factory
    ) -> None:
        await seed(session_factory, "bok", BOK, next_meeting=D(2026, 10, 22))
        res = await client.get("/api/dashboard/rates/bok")
        assert res.status_code == 200
        body = res.json()
        head = (await rates_of(client))[1]
        assert {k: body[k] for k in head} == head  # 머리 칸은 칸 행과 같다
        assert (body["firstDecidedOn"], body["lastDecidedOn"]) == ("2016-01-14", "2026-08-27")
        decisions = [(d["decidedOn"], d["rate"], d["change"], d["direction"])
                     for d in body["decisions"]]
        assert decisions == [
            ("2026-08-27", "3.00", "0.25", "up"),
            ("2026-07-16", "2.75", "0.00", "flat"),
            ("2026-05-28", "2.75", "1.25", "up"),
            ("2016-01-14", "1.50", None, None),
        ]

    async def test_받는_중이면_빈_결정(self, client: AsyncClient) -> None:
        body = (await client.get("/api/dashboard/rates/fed")).json()
        assert (body["state"], body["decisions"], body["firstDecidedOn"]) == (
            "collecting", [], None)

    async def test_없는_은행은_404(self, client: AsyncClient) -> None:
        res = await client.get("/api/dashboard/rates/arg")
        assert res.status_code == 404
        assert res.json()["status"] == "unknown_bank"


class Test까닭:
    async def test_서비스의_본문(self, client: AsyncClient) -> None:
        res = await client.get("/api/dashboard/rates/boe/commentary")
        assert res.status_code == 200
        assert res.json()["bank"] == "boe"
        assert policy_rate_commentary.get_shared_service().calls == ["boe"]  # type: ignore[union-attr]

    async def test_없는_은행은_404(self, client: AsyncClient) -> None:
        assert (await client.get("/api/dashboard/rates/arg/commentary")).status_code == 404

    async def test_서비스가_없으면_503(self, session_factory: Factory) -> None:
        policy_rate_commentary.set_shared_service(None)
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            assert (await ac.get("/api/dashboard/rates/bok/commentary")).status_code == 503


class Test다시_시도:
    async def test_202와_깨우기(self, client: AsyncClient) -> None:
        event = policy_rate_worker.wake_event()
        event.clear()
        res = await client.post("/api/dashboard/rates/collect")
        assert res.status_code == 202
        assert res.json() == {"accepted": True}
        assert event.is_set()
        event.clear()


def test_칸_경로는_출처_클라이언트를_쓰지_않는다() -> None:
    """DB만 읽는다(FR-040) — 경로 모듈이 출처 어댑터를 임포트하지 않는다."""
    import inspect

    body = inspect.getsource(dashboard_rates)
    assert "naver_rate.client" not in body
    assert "NaverRateClient" not in body
    assert dataclasses.is_dataclass(Bank)
