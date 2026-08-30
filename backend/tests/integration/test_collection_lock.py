"""통화별 단일 작업 잠금 테스트 (T086, T087).

FR-015a: 동일 통화에 대해 동시에 두 개 이상의 수집 작업을 실행하지 않는다.
FR-015b: 중복 요청은 진행 중인 작업에 합류한다.
FR-015c: 서로 다른 통화는 서로를 차단하지 않는다.

research R6: 기본 키 INSERT 충돌이 곧 "이미 진행 중"이다. 생성 컬럼·부분 인덱스 같은
DB 종속 문법을 쓰지 않는다 (헌법 v4.0.0).
"""
from __future__ import annotations

import datetime as dt

from sqlalchemy import func, select

from src.db.models import FxCollectionLock
from src.repository.collection_lock import (
    acquire_lock,
    heartbeat,
    reclaim_stale_locks,
    release_lock,
)
from src.repository.job import create_job

RANGE = (dt.date(1995, 1, 1), dt.date(2026, 8, 29))


async def _job(session, currency: str) -> int:
    job = await create_job(session, currency, *RANGE, chunks_total=32)
    await session.commit()
    return job.id


class Test잠금_획득:
    async def test_최초_획득에_성공한다(self, session_factory) -> None:
        async with session_factory() as s:
            job_id = await _job(s, "USD")
            assert await acquire_lock(s, "USD", job_id) is None
            await s.commit()
            assert (await s.execute(
                select(func.count()).select_from(FxCollectionLock))).scalar() == 1

    async def test_같은_통화_중복_요청은_기존_작업을_돌려준다(self, session_factory) -> None:
        """FR-015b: 새 작업을 만들지 않고 진행 중인 작업에 합류한다."""
        async with session_factory() as s:
            first = await _job(s, "USD")
            await acquire_lock(s, "USD", first)
            await s.commit()

            second = await _job(s, "USD")
            existing = await acquire_lock(s, "USD", second)
            await s.commit()
        assert existing == first, "기존 작업 ID를 돌려주어야 한다"

    async def test_중복_요청이_잠금을_늘리지_않는다(self, session_factory) -> None:
        async with session_factory() as s:
            await acquire_lock(s, "USD", await _job(s, "USD"))
            await s.commit()
            await acquire_lock(s, "USD", await _job(s, "USD"))
            await s.commit()
            n = (await s.execute(
                select(func.count()).select_from(FxCollectionLock)
                .where(FxCollectionLock.currency_code == "USD"))).scalar()
        assert n == 1

    async def test_다른_통화는_차단되지_않는다(self, session_factory) -> None:
        """FR-015c."""
        async with session_factory() as s:
            await acquire_lock(s, "USD", await _job(s, "USD"))
            await s.commit()
            assert await acquire_lock(s, "JPY", await _job(s, "JPY")) is None
            await s.commit()
            n = (await s.execute(
                select(func.count()).select_from(FxCollectionLock))).scalar()
        assert n == 2


class Test잠금_해제:
    async def test_해제_후_재획득이_가능하다(self, session_factory) -> None:
        async with session_factory() as s:
            first = await _job(s, "USD")
            await acquire_lock(s, "USD", first)
            await s.commit()
            await release_lock(s, "USD")
            await s.commit()
            assert await acquire_lock(s, "USD", await _job(s, "USD")) is None
            await s.commit()

    async def test_없는_잠금_해제는_조용히_넘어간다(self, session_factory) -> None:
        async with session_factory() as s:
            await release_lock(s, "EUR")
            await s.commit()


class Test스테일_잠금:
    """프로세스가 비정상 종료해 잠금이 남는 경우 (research R6)."""

    async def test_하트비트가_갱신된다(self, session_factory) -> None:
        async with session_factory() as s:
            await acquire_lock(s, "USD", await _job(s, "USD"))
            await s.commit()
            before = (await s.execute(select(FxCollectionLock))).scalar_one().heartbeat_at
            await heartbeat(s, "USD", at=before + dt.timedelta(minutes=5))
            await s.commit()
            after = (await s.execute(select(FxCollectionLock))).scalar_one().heartbeat_at
        assert after > before

    async def test_오래된_잠금은_회수된다(self, session_factory) -> None:
        async with session_factory() as s:
            await acquire_lock(s, "USD", await _job(s, "USD"))
            await s.commit()
            stale = dt.datetime.now() - dt.timedelta(hours=2)
            await heartbeat(s, "USD", at=stale)
            await s.commit()
            reclaimed = await reclaim_stale_locks(s, older_than_seconds=600)
            await s.commit()
            n = (await s.execute(
                select(func.count()).select_from(FxCollectionLock))).scalar()
        assert reclaimed == ["USD"]
        assert n == 0

    async def test_살아있는_잠금은_회수되지_않는다(self, session_factory) -> None:
        async with session_factory() as s:
            await acquire_lock(s, "USD", await _job(s, "USD"))
            await s.commit()
            reclaimed = await reclaim_stale_locks(s, older_than_seconds=600)
            await s.commit()
        assert reclaimed == []

    async def test_회수된_통화는_다시_획득할_수_있다(self, session_factory) -> None:
        async with session_factory() as s:
            await acquire_lock(s, "USD", await _job(s, "USD"))
            await s.commit()
            await heartbeat(s, "USD", at=dt.datetime.now() - dt.timedelta(hours=2))
            await s.commit()
            await reclaim_stale_locks(s, older_than_seconds=600)
            await s.commit()
            assert await acquire_lock(s, "USD", await _job(s, "USD")) is None


class Test이식성:
    def test_생성_컬럼이나_부분_인덱스를_쓰지_않는다(self) -> None:
        """헌법 v4.0.0: DB 종속 문법 금지 — 표준 SQL만으로 강제한다."""
        import pathlib

        src = pathlib.Path(__file__).resolve().parents[2] / "src" / "repository"
        body = (src / "collection_lock.py").read_text(encoding="utf-8")
        for token in ("GENERATED ALWAYS", "Computed", "postgresql_where", "mysql_"):
            assert token not in body, f"DB 종속 문법 발견: {token}"
