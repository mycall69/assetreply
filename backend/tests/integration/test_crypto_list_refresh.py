"""코인 목록 갱신 (T014) — 007 FR-004, FR-005, FR-005a, FR-005b, FR-006, FR-019, SC-011, data-model
1~4절.

**두 판(영문·한국어)을 다 받은 뒤** 한 트랜잭션에서 교체한다. 영문 판이 목록이고 한국어 판은 한글
이름만 준다 — 그래서 한국어 판만 실패하면 영문으로 교체하고 한글 이름은 이전 값을 둔다. 영문 판이
실패하거나 **절반 넘게 줄면** 아무것도 바꾸지 않는다 — 출처가 오류 없이 일부만 주면 실패 판정을
통과하므로 축소 검사가 두 번째 방어선이다(006과 같다).

코인은 **(출처, 출처 식별자)로** 식별한다 — 심볼은 유일하지 않다(FR-004). 목록에서 빠진 코인은
지우지 않는다(FR-005a).
"""
from __future__ import annotations

import asyncio
import datetime as dt

import pytest
from sqlalchemy import func, select

from src.api.services.crypto_list_refresh import refresh_coins, request_refresh
from src.db.models import (
    CryptoCoin,
    CryptoCoinRefresh,
    CryptoListLock,
    CryptoListRaw,
    CryptoListRawBody,
)
from src.ingestion.investing.errors import (
    InvestingBlocked,
    InvestingFormatError,
    InvestingNetworkError,
)
from src.repository import crypto_list_lock as locks
from src.worker.crypto_list_queue import CryptoListQueue
from tests.integration.crypto_support import (
    BNB_ID,
    BTC_ID,
    EN,
    ETH_ID,
    KO,
    NOW,
    TODAY,
    UA_SENTINEL,
    StubCoinSource,
    crypto_settings,
    fixture,
    reset_crypto_list_state,
    seed,
)

LATER = NOW + dt.timedelta(days=8)


@pytest.fixture(autouse=True)
def _list_state():
    reset_crypto_list_state()
    yield
    reset_crypto_list_state()


async def coins(session_factory) -> dict[str, CryptoCoin]:  # type: ignore[no-untyped-def]
    async with session_factory() as s:
        return {c.source_id: c for c in (await s.execute(select(CryptoCoin))).scalars()}


async def refresh_row(session_factory, edition: str) -> CryptoCoinRefresh | None:  # type: ignore[no-untyped-def]
    async with session_factory() as s:
        return await s.get(CryptoCoinRefresh, edition)


async def run(session_factory, source: StubCoinSource, *, now: dt.datetime = LATER,  # type: ignore[no-untyped-def]
              **settings: object):
    return await refresh_coins(session_factory, source, settings=crypto_settings(**settings),
                               now=lambda: now)


class Test교체:
    async def test_두_판을_받아_한_번에_넣는다(self, session_factory) -> None:
        result = await seed(session_factory)
        assert (result.outcome, result.coins, result.korean) == ("replaced", 154, "ready")

        rows = await coins(session_factory)
        assert len(rows) == 154
        btc = rows[BTC_ID]
        assert (btc.source, btc.symbol, btc.name_en, btc.name_ko, btc.slug, btc.quote_currency,
                btc.market_rank, btc.status) == (
            "investing", "BTC", "Bitcoin", "비트코인", "bitcoin", "USD", 1, "listed")
        assert (btc.first_seen_at, btc.last_seen_at) == (NOW, NOW)
        assert rows[ETH_ID].name_ko == "이더리움"
        # 한국어 판도 영문 그대로인 코인은 한글 이름이 없다(FR-006)
        assert rows[BNB_ID].name_ko is None

        en = await refresh_row(session_factory, "en")
        assert en is not None
        assert (en.as_of, en.as_of_date, en.row_count, en.attempts, en.last_error_kind) == (
            NOW, TODAY, 154, 1, None)
        ko = await refresh_row(session_factory, "ko")
        assert ko is not None and (ko.as_of, ko.row_count) == (NOW, 100)

    async def test_한글_이름은_식별자로만_짝짓는다(self, session_factory) -> None:
        """한국어 판의 순서가 달라도, 영문 판에 없는 코인이 있어도 이름이 다른 코인에 붙지
        않는다."""
        import json

        body = json.loads(fixture("coins_ko_p1.json"))
        body["coins"] = list(reversed(body["coins"])) + [
            {"instrument_id": 9999999, "name": "유령코인", "symbol": "BTC", "rank": 2,
             "slug": "ghost"}]
        await seed(session_factory, ko=[json.dumps(body, ensure_ascii=False)])
        rows = await coins(session_factory)
        assert rows[BTC_ID].name_ko == "비트코인"
        assert "9999999" not in rows
        assert [c.name_ko for c in rows.values()].count("유령코인") == 0

    async def test_같은_코인이_두_쪽에_오면_한_번만_넣는다(self, session_factory) -> None:
        """쪽을 넘기는 사이 순위가 바뀌면 같은 코인이 두 쪽에 온다 — 식별자 유일 키에 걸려 교체
        전체가 실패하면 안 된다."""
        result = await seed(session_factory, en=[EN[0], EN[0], EN[1]])
        assert result.outcome == "replaced"
        assert len(await coins(session_factory)) == 154


class Test빠진_코인:
    async def test_지우지_않고_missing_다시_보이면_listed(self, session_factory) -> None:
        await seed(session_factory)
        # 첫 쪽(100개)만 — 154 × 0.5 = 77 이상이라 교체한다
        result = await run(session_factory, StubCoinSource({"en": [[EN[0]]], "ko": [KO]}))
        assert result.outcome == "replaced"
        rows = await coins(session_factory)
        assert len(rows) == 154
        missing = [c for c in rows.values() if c.status == "missing"]
        assert len(missing) == 54
        assert all(c.last_seen_at == NOW for c in missing)
        assert rows[BTC_ID].last_seen_at == LATER
        en = await refresh_row(session_factory, "en")
        assert en is not None and en.row_count == 100

        again = LATER + dt.timedelta(days=8)
        await run(session_factory, StubCoinSource({"en": [EN], "ko": [KO]}), now=again)
        assert {c.status for c in (await coins(session_factory)).values()} == {"listed"}


class Test교체하지_않는_경우:
    async def test_절반_넘게_줄면_거절하고_아무것도_바꾸지_않는다(self, session_factory) -> None:
        await seed(session_factory)
        result = await run(session_factory, StubCoinSource({"en": [[EN[1]]], "ko": [KO]}))
        assert (result.outcome, result.kind) == ("failed", "shrunk")
        rows = await coins(session_factory)
        assert {c.status for c in rows.values()} == {"listed"}
        assert rows[BTC_ID].last_seen_at == NOW
        en = await refresh_row(session_factory, "en")
        assert en is not None
        assert (en.as_of, en.row_count, en.last_error_kind) == (NOW, 154, "shrunk")
        assert en.last_failed_at == LATER

    @pytest.mark.parametrize(("error", "kind"), [
        (InvestingBlocked("막힘"), "blocked"), (InvestingNetworkError("끊김"), "network"),
        (InvestingFormatError("모양"), "format")])
    async def test_영문_판이_실패하면_아무것도_바꾸지_않는다(
        self, session_factory, error: Exception, kind: str
    ) -> None:
        await seed(session_factory)
        source = StubCoinSource({"en": [[error]], "ko": [KO]})
        result = await run(session_factory, source)
        assert (result.outcome, result.kind) == ("failed", kind)
        assert source.calls == ["en"]
        assert {c.last_seen_at for c in (await coins(session_factory)).values()} == {NOW}
        en = await refresh_row(session_factory, "en")
        assert en is not None and (en.as_of, en.last_error_kind) == (NOW, kind)

    async def test_중간_쪽이_실패해도_아무것도_바꾸지_않는다(self, session_factory) -> None:
        source = StubCoinSource({"en": [[EN[0], InvestingFormatError("2쪽 모양")]], "ko": [KO]})
        result = await run(session_factory, source, now=NOW)
        assert (result.outcome, result.kind) == ("failed", "format")
        assert await coins(session_factory) == {}
        en = await refresh_row(session_factory, "en")
        assert en is not None and (en.as_of, en.attempts, en.last_error_kind) == (
            None, 1, "format")

    async def test_빈_목록은_형식_오류다(self, session_factory) -> None:
        source = StubCoinSource({"en": [['{"coins": [], "next_page_cursor": null}']], "ko": [KO]})
        result = await run(session_factory, source, now=NOW)
        assert (result.outcome, result.kind) == ("failed", "format")
        assert await coins(session_factory) == {}


class Test한국어_판:
    async def test_한국어_판만_실패하면_영문으로_교체하고_한글_이름은_이전_값이다(
        self, session_factory
    ) -> None:
        await seed(session_factory)
        result = await run(session_factory, StubCoinSource(
            {"en": [EN], "ko": [[InvestingNetworkError("끊김")]]}))
        assert (result.outcome, result.korean) == ("replaced", "failed")
        rows = await coins(session_factory)
        assert rows[BTC_ID].name_ko == "비트코인"
        assert rows[BTC_ID].last_seen_at == LATER
        en = await refresh_row(session_factory, "en")
        ko = await refresh_row(session_factory, "ko")
        assert en is not None and en.as_of == LATER
        assert ko is not None and (ko.as_of, ko.last_error_kind) == (NOW, "network")

    async def test_처음부터_한국어_판이_실패하면_영문으로만_찾는다(self, session_factory) -> None:
        result = await run(session_factory, StubCoinSource(
            {"en": [EN], "ko": [[InvestingBlocked("막힘")]]}), now=NOW)
        assert (result.outcome, result.korean) == ("replaced", "failed")
        assert {c.name_ko for c in (await coins(session_factory)).values()} == {None}


class Test원본:
    async def test_같은_본문은_한_번만_남기고_쪽_기록은_매번_남긴다(self, session_factory) -> None:
        await seed(session_factory)
        await seed(session_factory, now=LATER)
        async with session_factory() as s:
            bodies = (await s.execute(select(func.count()).select_from(CryptoListRawBody))).scalar()
            pages = list((await s.execute(
                select(CryptoListRaw).order_by(CryptoListRaw.id))).scalars())
        assert bodies == 3
        assert len(pages) == 6
        assert [(p.edition, p.page_no) for p in pages[:3]] == [("en", 1), ("en", 2), ("ko", 1)]
        assert {p.status_code for p in pages} == {200}

    async def test_실패한_갱신의_원본도_남긴다(self, session_factory) -> None:
        """무엇이 잘못 왔는지 되짚는 근거다 — 축소로 거절한 목록도 남긴다."""
        await seed(session_factory)
        await run(session_factory, StubCoinSource({"en": [[EN[1]]], "ko": [KO]}))
        async with session_factory() as s:
            pages = (await s.execute(select(func.count()).select_from(CryptoListRaw))).scalar()
        assert pages == 4


class Test점유와_진행:
    async def test_점유_중이면_시작하지_않는다(self, session_factory) -> None:
        async with session_factory() as s:
            assert await locks.try_lock(s, NOW)
        source = StubCoinSource({"en": [EN], "ko": [KO]})
        result = await run(session_factory, source)
        assert result.outcome == "busy"
        assert source.calls == []

    async def test_쪽마다_진행을_기록하고_판이_바뀌면_0부터_센다(self, session_factory) -> None:
        seen: list[tuple[str, int, str | None, int, int]] = []

        async def look(edition: str, page_no: int) -> None:
            async with session_factory() as s:
                lock = await s.get(CryptoListLock, "coins")
                assert lock is not None
                seen.append((edition, page_no, lock.edition, lock.pages_done, lock.coins_seen))

        source = StubCoinSource({"en": [EN], "ko": [KO]})
        source.before_page = look
        await run(session_factory, source, now=NOW)
        assert seen == [("en", 1, "en", 0, 0), ("en", 2, "en", 1, 100), ("ko", 1, "ko", 0, 0)]
        async with session_factory() as s:
            assert await s.get(CryptoListLock, "coins") is None

    async def test_동시에_두_갱신이면_하나만_받는다(self, session_factory) -> None:
        gate = asyncio.Event()
        entered = asyncio.Event()

        async def hold(edition: str, page_no: int) -> None:
            entered.set()
            await gate.wait()

        first = StubCoinSource({"en": [EN], "ko": [KO]})
        first.before_page = hold
        task = asyncio.create_task(run(session_factory, first, now=NOW))
        await asyncio.wait_for(entered.wait(), timeout=3)
        second = StubCoinSource({"en": [EN], "ko": [KO]})
        assert (await run(session_factory, second, now=NOW)).outcome == "busy"
        gate.set()
        assert (await task).outcome == "replaced"
        assert second.calls == []


class Test사건과_비밀값:
    async def test_시작과_완료를_남긴다(self, session_factory, captured) -> None:
        await seed(session_factory)
        events = [r.__dict__.get("event") for r in captured]
        assert events[0] == "crypto_list_refresh_started"
        assert events[-1] == "crypto_list_refresh_completed"
        done = captured[-1].__dict__
        assert (done["coins"], done["korean"]) == (154, "ready")

    async def test_실패를_남기고_사용자_에이전트를_싣지_않는다(
        self, session_factory, captured
    ) -> None:
        """출처 오류 문구에 요청 값이 섞여 와도 로그·갱신 기록에 남기지 않는다(FR-019, SC-011)."""
        error = InvestingBlocked(f"403 for request with User-Agent {UA_SENTINEL}")
        result = await run(session_factory, StubCoinSource({"en": [[error]]}), now=NOW)
        assert result.kind == "blocked"
        failed = [r for r in captured if r.__dict__.get("event") == "crypto_list_refresh_failed"]
        assert failed and failed[0].__dict__["kind"] == "blocked"
        for record in captured:
            assert UA_SENTINEL not in record.getMessage()
            assert all(UA_SENTINEL not in str(v) for v in record.__dict__.values())
        en = await refresh_row(session_factory, "en")
        assert en is not None and en.last_error is not None
        assert UA_SENTINEL not in en.last_error


class Test갱신_요청:
    async def test_받을_때가_되면_요청만_하고_기다리지_않는다(self, session_factory) -> None:
        queue = CryptoListQueue()
        async with session_factory() as s:
            status = await request_refresh(s, now=NOW, settings=crypto_settings(), queue=queue)
        assert queue.is_active("coins")
        assert status.list.state == "never"

    async def test_받을_때가_아니면_요청하지_않는다(self, session_factory) -> None:
        await seed(session_factory)
        queue = CryptoListQueue()
        async with session_factory() as s:
            status = await request_refresh(
                s, now=NOW + dt.timedelta(days=6), settings=crypto_settings(), queue=queue)
        assert not queue.is_active("coins")
        assert (status.list.state, status.list.as_of) == ("ready", NOW)
        assert status.korean.state == "ready"

    async def test_요청이_대기_중이면_갱신_중이다(self, session_factory) -> None:
        await seed(session_factory)
        queue = CryptoListQueue()
        async with session_factory() as s:
            status = await request_refresh(s, now=LATER, settings=crypto_settings(), queue=queue)
        assert queue.is_active("coins")
        assert (status.list.state, status.list.as_of) == ("refreshing", NOW)

    async def test_정체된_점유는_회수한다(self, session_factory) -> None:
        """프로세스가 갱신 도중 죽으면 점유가 남는다 — 회수하지 않으면 화면이 영원히 "갱신
        중"이다."""
        async with session_factory() as s:
            assert await locks.try_lock(s, NOW - dt.timedelta(minutes=30))
        queue = CryptoListQueue()
        async with session_factory() as s:
            await request_refresh(s, now=NOW, settings=crypto_settings(), queue=queue)
        async with session_factory() as s:
            assert await s.get(CryptoListLock, "coins") is None
        assert queue.is_active("coins")
