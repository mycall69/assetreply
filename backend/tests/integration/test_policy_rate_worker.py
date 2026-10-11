"""기준금리 결정 이력 수집 (014 반복 2026-10-11d T204) — FR-043, SC-026, research R14-32,
data-model 17.

스텁 출처(네트워크 없음)와 시험 DB로 본다.

- 한 바퀴는 목록 한 번 → 은행마다 결정 이력. 처음은 짧은 쪽이 올 때까지 전부(끝나야
  `history_complete`), 그 뒤는 목록의 최근 결정이 저장된 것보다 늦거나
  그 한국 날짜에 아직 겹쳐 받지 않았을 때만 첫 쪽
- 처음 받기가 중간에 실패하면 끝났다고 기록하지 않는다 — 다음 바퀴가 다시 받는다. 은행마다 따로
  실패한다
- 새 날만 넣는다. 저장된 날의 금리가 다르면 덮지 않고 `policy_rate_revised`. 같은 날 다른 값(출처
  충돌)은 `policy_rate_conflict`
- 목록이 실패하면 은행 다섯 모두 그 실패다(결정 이력을 부르지 않는다). 목록에 없는 은행은
  `not_found`
- 원본은 본문 그대로(종류·은행·쪽). 다음 결정 예정일은 목록의 것 — 오늘(한국)보다 이르면 비운다
- 깨우기 이벤트가 곧바로 한 바퀴를 돌린다
"""

from __future__ import annotations

import asyncio
import dataclasses
import datetime as dt
from decimal import Decimal

import pytest
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from src.config.settings import Settings, load_settings
from src.db.migrate import _alembic_config
from src.db.models import PolicyRateBank, PolicyRateRaw
from src.ingestion.naver_rate.client import CalendarFetch, ListFetch
from src.ingestion.naver_rate.errors import PolicyRateBlocked, PolicyRateConnectionError
from src.ingestion.naver_rate.parse import CalendarPage, Conflict, ListEntry, SourceDecision
from src.repository import policy_rate_repository as repo
from src.simulation.policy_rate import BANKS
from src.worker import policy_rate_runner, policy_rate_worker
from src.worker.policy_rate_runner import run_round

D = dt.date
NOW = dt.datetime(2026, 10, 11, 9, 40, tzinfo=dt.UTC)  # 한국 2026-10-11 18:40
AT = NOW.replace(tzinfo=None)
IDS = [b.id for b in BANKS]
LATEST = D(2026, 9, 17)
Factory = async_sessionmaker[AsyncSession]
Events = list[tuple[str, dict[str, object]]]


def history(count: int, *, latest: dt.date = LATEST) -> list[SourceDecision]:
    """최신부터 45일 간격의 결정. 금리는 날마다 다르다(0.25 계단)."""
    out = []
    for k in range(count):
        day = latest - dt.timedelta(days=45 * k)
        out.append(SourceDecision(day, None, Decimal("1.00") + Decimal("0.25") * (k % 8)))
    return out


def pages_of(decisions: list[SourceDecision]) -> list[CalendarPage]:
    chunks = [decisions[i:i + 60] for i in range(0, len(decisions), 60)] or [[]]
    pages = [CalendarPage(chunk, [], None, len(chunk)) for chunk in chunks]
    if len(chunks[-1]) == 60:
        pages.append(CalendarPage([], [], None, 0))
    return pages


class Source:
    """은행마다 쪽 목록을 돌려준다. `fail`은 (종류, 은행, 쪽) → 예외."""

    def __init__(self, count: int = 87) -> None:
        self.pages = {bank: pages_of(history(count)) for bank in IDS}
        first = history(1)[0].rate
        self.entries = {bank: ListEntry(LATEST, first, D(2026, 10, 29)) for bank in IDS}
        self.calls: list[tuple[str, str | None, int | None]] = []
        self.fail: dict[tuple[str, str | None, int | None], Exception] = {}

    async def fetch_list(self) -> ListFetch:
        key = ("list", None, None)
        self.calls.append(key)
        if key in self.fail:
            raise self.fail.pop(key)
        return ListFetch('[{"목록": 1}]', dict(self.entries))

    async def fetch_calendars(self, bank_id: str, page: int) -> CalendarFetch:
        key = ("calendars", bank_id, page)
        self.calls.append(key)
        if key in self.fail:
            raise self.fail.pop(key)
        pages = self.pages[bank_id]
        body = pages[page - 1] if page <= len(pages) else CalendarPage([], [], None, 0)
        return CalendarFetch(f'[{{"{bank_id}": {page}}}]', body)


@pytest.fixture
def settings() -> Settings:
    return dataclasses.replace(load_settings(), policy_rate_collect_interval_seconds=3600)


@pytest.fixture
def events(monkeypatch: pytest.MonkeyPatch) -> Events:
    seen: Events = []
    monkeypatch.setattr(
        policy_rate_runner, "_event", lambda name, **fields: seen.append((name, fields)))
    return seen


async def raws(factory: Factory) -> list[PolicyRateRaw]:
    async with factory() as s:
        rows = await s.execute(select(PolicyRateRaw).order_by(PolicyRateRaw.id))
        return list(rows.scalars())


async def stored(factory: Factory, bank: str) -> list[tuple[dt.date, Decimal]]:
    async with factory() as s:
        return [(row.decided_on, row.rate) for row in await repo.decisions(s, bank)]


async def state(factory: Factory, bank: str) -> PolicyRateBank:
    async with factory() as s:
        row = await repo.get_state(s, bank)
        assert row is not None
        return row


async def has_state(factory: Factory, bank: str) -> bool:
    async with factory() as s:
        return await repo.get_state(s, bank) is not None


class Test처음:
    async def test_목록_한_번과_은행마다_전부(
        self, session_factory: Factory, settings: Settings, events: Events
    ) -> None:
        source = Source(87)
        result = await run_round(session_factory, source, settings=settings, now=NOW)
        assert source.calls[0] == ("list", None, None)
        assert source.calls[1:] == [("calendars", b, p) for b in IDS for p in (1, 2)]
        assert result.failed == frozenset() and result.requests == 11
        for bank in IDS:
            rows = await stored(session_factory, bank)
            assert len(rows) == 87
            assert rows[0] == (LATEST, Decimal("1.00"))
            assert [d for d, _ in rows] == sorted((d for d, _ in rows), reverse=True)
            st = await state(session_factory, bank)
            assert st.history_complete is True
            assert st.next_meeting_on == D(2026, 10, 29)
            assert st.last_success_at == AT
            assert st.last_overlap_on == D(2026, 10, 11)

    async def test_원본은_본문_그대로(
        self, session_factory: Factory, settings: Settings, events: Events
    ) -> None:
        await run_round(session_factory, Source(87), settings=settings, now=NOW)
        rows = await raws(session_factory)
        assert len(rows) == 11
        assert (rows[0].kind, rows[0].bank, rows[0].page) == ("list", None, None)
        assert rows[0].body == '[{"목록": 1}]'
        assert (rows[1].kind, rows[1].bank, rows[1].page) == ("calendars", "fed", 1)
        assert rows[1].body == '[{"fed": 1}]'
        assert rows[1].fetched_at == AT

    async def test_정확히_60의_배수면_빈_쪽까지(
        self, session_factory: Factory, settings: Settings, events: Events
    ) -> None:
        source = Source(60)
        await run_round(session_factory, source, settings=settings, now=NOW)
        assert ("calendars", "fed", 2) in source.calls
        assert (await state(session_factory, "fed")).history_complete is True


class Test실패:
    async def test_중간_실패는_끝나지_않고_다음_바퀴에_다시(
        self, session_factory: Factory, settings: Settings, events: Events
    ) -> None:
        source = Source(87)
        source.fail[("calendars", "bok", 2)] = PolicyRateConnectionError(
            "기준금리 출처가 응답하지 못했습니다(503).")
        result = await run_round(session_factory, source, settings=settings, now=NOW)
        assert result.failed == frozenset({"bok"})
        bok = await state(session_factory, "bok")
        assert bok.history_complete is False
        assert (bok.failure_kind, bok.last_failure_at) == ("connection", AT)
        assert "503" in (bok.failure_message or "")
        assert len(await stored(session_factory, "bok")) == 60  # 받은 첫 쪽은 남는다
        # 다른 은행은 계속된다
        assert (await state(session_factory, "ecb")).history_complete is True
        assert ("calendars", "boj", 2) in source.calls
        assert any(n == "policy_rate_fetch" and f.get("status") == "failed" for n, f in events)

        source.calls.clear()
        later = NOW + dt.timedelta(minutes=30)
        await run_round(session_factory, source, settings=settings, now=later)
        assert source.calls == [
            ("list", None, None), ("calendars", "bok", 1), ("calendars", "bok", 2)]
        bok = await state(session_factory, "bok")
        assert bok.history_complete is True
        assert len(await stored(session_factory, "bok")) == 87

    async def test_목록이_실패하면_다섯_모두_그_실패(
        self, session_factory: Factory, settings: Settings, events: Events
    ) -> None:
        source = Source(87)
        source.fail[("list", None, None)] = PolicyRateBlocked(
            "기준금리 출처가 접근을 막았습니다(403).")
        result = await run_round(session_factory, source, settings=settings, now=NOW)
        assert source.calls == [("list", None, None)]
        assert result.failed == frozenset(IDS)
        for bank in IDS:
            assert (await state(session_factory, bank)).failure_kind == "blocked"

    async def test_목록이_다시_성공하면_할_일이_없는_은행의_실패도_풀린다(
        self, session_factory: Factory, settings: Settings, events: Events
    ) -> None:
        # 목록 실패 뒤의 바퀴에서 새 결정도 겹쳐 받기도 없는 은행 — 목록으로 저장된 결정이 최신임을
        # 확인했으니 성공이다.
        # 성공을 남기지 않으면 "최근 갱신 실패"가 다음 날의 겹쳐 받기까지 남는다(T210 실측 준비 중
        # 찾음)
        source = Source(10)
        await run_round(session_factory, source, settings=settings, now=NOW)
        source.fail[("list", None, None)] = PolicyRateConnectionError("연결하지 못했습니다.")
        failed_at = NOW + dt.timedelta(minutes=30)
        await run_round(session_factory, source, settings=settings, now=failed_at)
        fed = await state(session_factory, "fed")
        assert fed.last_failure_at == failed_at.replace(tzinfo=None)
        source.calls.clear()
        later = NOW + dt.timedelta(minutes=60)
        await run_round(session_factory, source, settings=settings, now=later)
        assert source.calls == [("list", None, None)]
        for bank in IDS:
            st = await state(session_factory, bank)
            assert st.last_success_at == later.replace(tzinfo=None)
            assert st.last_success_at > (st.last_failure_at or st.last_success_at)

    async def test_목록에_없는_은행은_not_found(
        self, session_factory: Factory, settings: Settings, events: Events
    ) -> None:
        source = Source(87)
        del source.entries["boe"]
        result = await run_round(session_factory, source, settings=settings, now=NOW)
        assert result.failed == frozenset({"boe"})
        assert all(call[1] != "boe" for call in source.calls)
        assert (await state(session_factory, "boe")).failure_kind == "not_found"
        assert len(await stored(session_factory, "boj")) == 87


class Test이어_받기:
    async def test_같은_날_새_결정이_없으면_부르지_않는다(
        self, session_factory: Factory, settings: Settings, events: Events
    ) -> None:
        source = Source(87)
        await run_round(session_factory, source, settings=settings, now=NOW)
        source.calls.clear()
        later = NOW + dt.timedelta(minutes=30)
        await run_round(session_factory, source, settings=settings, now=later)
        assert source.calls == [("list", None, None)]

    async def test_새_결정이_보이면_그_은행의_첫_쪽(
        self, session_factory: Factory, settings: Settings, events: Events
    ) -> None:
        source = Source(87)
        await run_round(session_factory, source, settings=settings, now=NOW)
        announced = dt.datetime(2026, 10, 11, 1, 0, tzinfo=dt.UTC)
        new = SourceDecision(D(2026, 10, 11), announced, Decimal("3.25"))
        first = source.pages["bok"][0]
        source.pages["bok"][0] = dataclasses.replace(
            first, decisions=[new, *first.decisions[:59]])
        source.entries["bok"] = ListEntry(D(2026, 10, 11), Decimal("3.25"), D(2026, 11, 26))
        source.calls.clear()
        later = NOW + dt.timedelta(minutes=30)
        await run_round(session_factory, source, settings=settings, now=later)
        assert source.calls == [("list", None, None), ("calendars", "bok", 1)]
        rows = await stored(session_factory, "bok")
        assert rows[0] == (D(2026, 10, 11), Decimal("3.25"))
        assert len(rows) == 88
        assert (await state(session_factory, "bok")).next_meeting_on == D(2026, 11, 26)

    async def test_다음_한국_날짜에는_다섯_모두_첫_쪽을_겹쳐_받는다(
        self, session_factory: Factory, settings: Settings, events: Events
    ) -> None:
        source = Source(87)
        await run_round(session_factory, source, settings=settings, now=NOW)
        source.calls.clear()
        tomorrow = NOW + dt.timedelta(hours=15)  # 한국 10-12 09:40
        await run_round(session_factory, source, settings=settings, now=tomorrow)
        assert source.calls == [("list", None, None)] + [("calendars", b, 1) for b in IDS]
        assert (await state(session_factory, "fed")).last_overlap_on == D(2026, 10, 12)

    async def test_개정은_덮지_않고_사건을_남긴다(
        self, session_factory: Factory, settings: Settings, events: Events
    ) -> None:
        source = Source(87)
        await run_round(session_factory, source, settings=settings, now=NOW)
        first = source.pages["fed"][0]
        changed = dataclasses.replace(first.decisions[1], rate=Decimal("9.99"))
        source.pages["fed"][0] = dataclasses.replace(
            first, decisions=[first.decisions[0], changed, *first.decisions[2:]])
        events.clear()
        tomorrow = NOW + dt.timedelta(hours=15)
        await run_round(session_factory, source, settings=settings, now=tomorrow)
        rows = dict(await stored(session_factory, "fed"))
        assert rows[changed.decided_on] == Decimal("1.25")
        revised = [f for name, f in events if name == "policy_rate_revised"]
        assert revised == [{
            "bank": "fed", "date": changed.decided_on.isoformat(),
            "stored": "1.25", "source": "9.99"}]

    async def test_같은_날_다른_값은_저장하지_않고_사건(
        self, session_factory: Factory, settings: Settings, events: Events
    ) -> None:
        source = Source(10)
        page = source.pages["ecb"][0]
        clash = D(2026, 8, 3)
        # 파서는 충돌한 날을 결정에서 뺀다(contract `test_같은_날_다른_값은_고르지_않고_충돌이다`)
        source.pages["ecb"][0] = dataclasses.replace(
            page,
            decisions=[d for d in page.decisions if d.decided_on != clash],
            conflicts=[Conflict(clash, (Decimal("2.40"), Decimal("2.15")))],
        )
        await run_round(session_factory, source, settings=settings, now=NOW)
        assert clash not in dict(await stored(session_factory, "ecb"))
        conflicts = [f for name, f in events if name == "policy_rate_conflict"]
        assert conflicts == [{"bank": "ecb", "date": "2026-08-03", "rates": ["2.40", "2.15"]}]

    async def test_지난_다음_결정일은_비운다(
        self, session_factory: Factory, settings: Settings, events: Events
    ) -> None:
        source = Source(10)
        source.entries["boj"] = ListEntry(LATEST, Decimal("1.00"), D(2025, 2, 1))
        await run_round(session_factory, source, settings=settings, now=NOW)
        assert (await state(session_factory, "boj")).next_meeting_on is None


class Test워커:
    async def test_깨우면_곧바로_한_바퀴(
        self, session_factory: Factory, settings: Settings, events: Events
    ) -> None:
        source = Source(10)
        task = asyncio.create_task(policy_rate_worker.policy_rate_worker_loop(
            session_factory, source, settings=settings, clock=lambda: NOW))
        try:
            for _ in range(300):
                if len(source.calls) >= 6 and await has_state(session_factory, "boj"):
                    break
                await asyncio.sleep(0.01)
            calls = len(source.calls)
            assert calls == 6
            policy_rate_worker.wake()
            for _ in range(300):
                if len(source.calls) > calls:
                    break
                await asyncio.sleep(0.01)
            assert source.calls[calls] == ("list", None, None)
        finally:
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task


class Test스키마:
    def test_리비전은_첫_거래일_뒤의_머리다(self) -> None:
        script = ScriptDirectory.from_config(_alembic_config())
        head = script.get_revision(script.get_current_head())
        assert head is not None
        assert head.revision == "e9f3b7c2a4d1"
        assert head.down_revision == "a6c2e8f41b93"
        assert "기준금리" in (head.doc or "")

    async def test_테이블_셋(self, engine: AsyncEngine) -> None:
        async with engine.connect() as conn:
            names = set(await conn.run_sync(lambda c: inspect(c).get_table_names()))
        assert {"policy_rate_decision", "policy_rate_raw", "policy_rate_bank"} <= names
