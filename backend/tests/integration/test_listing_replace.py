"""목록 교체 트랜잭션 (T019) — 006 FR-015, FR-016, FR-018, FR-018a, FR-019, FR-019a, FR-061,
SC-004, SC-016, research R6-4, R6-13.

**실패는 아무것도 바꾸지 않는다.** 반쯤 받은 목록, 오류 없이 짧게 온 목록으로 바꾸면 빠진
종목이 전부 "목록에서 빠짐"이 되는데 남은 종목은 정상이라 무엇이 빠졌는지 알 수 없다.
"""
from __future__ import annotations

import datetime as dt
import hashlib

import pytest
from sqlalchemy import func, select
from src.api.services.listing_refresh import AuthBlocker, refresh_unit

from src.db.models import (
    StockListing,
    StockListingRaw,
    StockListingRawBody,
    StockListingRefresh,
)
from src.ingestion.kiwoom.errors import KiwoomRateLimited, KiwoomUnavailable
from tests.integration.listing_support import (
    APP_KEY,
    APP_SECRET,
    KOSPI_ROWS,
    NOW,
    YESTERDAY_NOW,
    StubListingSource,
    kr_body,
    kr_row,
    listing_settings,
    page,
    reset_listing_state,
    seed,
)


@pytest.fixture(autouse=True)
def _listing_state():
    reset_listing_state()
    yield
    reset_listing_state()


def rows_of(n: int, prefix: str = "1") -> list[dict[str, str]]:
    return [kr_row(f"{prefix}{i:05d}", f"종목{prefix}{i}") for i in range(n)]


async def count(session_factory, model) -> int:  # type: ignore[no-untyped-def]
    async with session_factory() as s:
        return int((await s.execute(select(func.count()).select_from(model))).scalar_one())


async def listings(session_factory) -> dict[str, StockListing]:
    async with session_factory() as s:
        return {r.code: r for r in (await s.execute(select(StockListing))).scalars()}


async def refresh_row(session_factory, unit: str) -> StockListingRefresh | None:
    async with session_factory() as s:
        return await s.get(StockListingRefresh, unit)


async def run(session_factory, unit: str, response, *, now: dt.datetime = NOW):  # type: ignore[no-untyped-def]
    source = StubListingSource({unit: [response]})
    return await refresh_unit(session_factory, source, unit, settings=listing_settings(),
                              now=lambda: now, blocker=AuthBlocker())


class Test온전한_교체:
    async def test_받은_종목이_목록이_되고_기준_시각이_남는다(self, session_factory) -> None:
        result = await seed(session_factory, "KOSPI", KOSPI_ROWS)
        assert result.outcome == "replaced" and result.rows == 4

        rows = await listings(session_factory)
        assert set(rows) == {"005930", "005935", "069500", "0030R0"}
        samsung = rows["005930"]
        assert (samsung.country, samsung.unit, samsung.name_ko, samsung.kind) == (
            "KR", "KOSPI", "삼성전자", "stock")
        assert samsung.listed_on == dt.date(1975, 6, 11)
        assert samsung.status == "listed"
        assert samsung.source == "kiwoom:ka10099"
        assert samsung.first_seen_at == NOW and samsung.last_seen_at == NOW
        assert rows["069500"].kind == "etf" and rows["0030R0"].kind == "reit"

        refresh = await refresh_row(session_factory, "KOSPI")
        assert refresh is not None
        assert refresh.as_of == NOW
        assert refresh.as_of_date == dt.date(2026, 10, 2)
        assert refresh.row_count == 4

    async def test_단위마다_기준_시각이_따로다(self, session_factory) -> None:
        """FR-015."""
        await seed(session_factory, "KOSPI", KOSPI_ROWS, now=YESTERDAY_NOW)
        await seed(session_factory, "KOSDAQ", [kr_row("247540", "에코프로비엠", "코스닥")])
        kospi = await refresh_row(session_factory, "KOSPI")
        kosdaq = await refresh_row(session_factory, "KOSDAQ")
        assert kospi is not None and kosdaq is not None
        assert kospi.as_of == YESTERDAY_NOW and kosdaq.as_of == NOW

    async def test_이름이_바뀌어도_같은_종목이다(self, session_factory) -> None:
        """FR-019a — 코드로 식별한다. 이름으로 묶으면 사명을 바꾼 회사가 둘이 된다."""
        await seed(session_factory, "KOSPI", [kr_row("000001", "옛이름")], now=YESTERDAY_NOW)
        await seed(session_factory, "KOSPI", [kr_row("000001", "새이름")])
        rows = await listings(session_factory)
        assert len(rows) == 1
        assert rows["000001"].name_ko == "새이름"
        assert rows["000001"].first_seen_at == YESTERDAY_NOW
        assert rows["000001"].last_seen_at == NOW


class Test실패는_아무것도_바꾸지_않는다:
    async def test_중간_쪽_실패(self, session_factory) -> None:
        """FR-018 — 클라이언트는 중간 쪽이 실패하면 받은 쪽을 돌려주지 않고 예외를 낸다."""
        await seed(session_factory, "KOSPI", KOSPI_ROWS, now=YESTERDAY_NOW)
        result = await run(session_factory, "KOSPI", KiwoomUnavailable("연결 끊김"))
        assert result.outcome == "failed" and result.kind == "network"

        rows = await listings(session_factory)
        assert set(rows) == {"005930", "005935", "069500", "0030R0"}
        assert all(r.status == "listed" and r.last_seen_at == YESTERDAY_NOW
                   for r in rows.values())
        refresh = await refresh_row(session_factory, "KOSPI")
        assert refresh is not None
        assert refresh.as_of == YESTERDAY_NOW            # 기준 시각이 그대로다
        assert refresh.last_failed_at == NOW
        assert refresh.last_error_kind == "network"

    async def test_한도_초과(self, session_factory) -> None:
        await seed(session_factory, "KOSPI", KOSPI_ROWS, now=YESTERDAY_NOW)
        result = await run(session_factory, "KOSPI", KiwoomRateLimited("한도"))
        assert result.kind == "rate_limit"
        assert len(await listings(session_factory)) == 4

    async def test_빈_목록은_실패다(self, session_factory) -> None:
        """`return_code=0`인 빈 목록은 실패 판정을 통과한다 — 두 번째 방어선이 막아야 한다."""
        await seed(session_factory, "KOSPI", KOSPI_ROWS, now=YESTERDAY_NOW)
        result = await run(session_factory, "KOSPI", [page(kr_body([]))])
        assert result.outcome == "failed" and result.kind == "invalid"
        assert all(r.status == "listed" for r in (await listings(session_factory)).values())

    async def test_처음_보는_시장명은_실패다(self, session_factory) -> None:
        await seed(session_factory, "KOSPI", KOSPI_ROWS, now=YESTERDAY_NOW)
        renamed = [dict(r, marketName="유가증권") if r["marketName"] == "거래소" else r
                   for r in KOSPI_ROWS]
        result = await run(session_factory, "KOSPI", [page(kr_body(renamed))])
        assert result.kind == "invalid"
        assert all(r.status == "listed" for r in (await listings(session_factory)).values())


class Test축소_검사:
    """FR-018a — **새 건수 < 이전 건수 × 0.5**이면 교체하지 않는다."""

    async def test_40퍼센트_길이면_교체하지_않는다(self, session_factory) -> None:
        await seed(session_factory, "KOSPI", rows_of(10), now=YESTERDAY_NOW)
        result = await run(session_factory, "KOSPI", [page(kr_body(rows_of(4)))])
        assert result.outcome == "failed" and result.kind == "invalid"

        rows = await listings(session_factory)
        assert len(rows) == 10
        assert all(r.status == "listed" for r in rows.values())
        refresh = await refresh_row(session_factory, "KOSPI")
        assert refresh is not None
        assert refresh.row_count == 10 and refresh.as_of == YESTERDAY_NOW
        assert refresh.last_error is not None and "4" in refresh.last_error

    async def test_정확히_50퍼센트면_교체한다(self, session_factory) -> None:
        await seed(session_factory, "KOSPI", rows_of(10), now=YESTERDAY_NOW)
        result = await run(session_factory, "KOSPI", [page(kr_body(rows_of(5)))])
        assert result.outcome == "replaced"
        rows = await listings(session_factory)
        assert len(rows) == 10                              # 지우지 않는다
        assert sum(r.status == "listed" for r in rows.values()) == 5
        assert sum(r.status == "missing" for r in rows.values()) == 5
        refresh = await refresh_row(session_factory, "KOSPI")
        assert refresh is not None and refresh.row_count == 5


class Test목록에서_빠짐:
    async def test_빠진_종목을_지우지_않고_표시한다(self, session_factory) -> None:
        """FR-019, SC-016 — 지우면 005의 시세와 이력이 가리키는 대상이 사라진다."""
        await seed(session_factory, "KOSPI", KOSPI_ROWS, now=YESTERDAY_NOW)
        await seed(session_factory, "KOSPI", KOSPI_ROWS[:3])
        rows = await listings(session_factory)
        assert len(rows) == 4
        assert rows["0030R0"].status == "missing"
        assert rows["0030R0"].last_seen_at == YESTERDAY_NOW
        assert rows["005930"].status == "listed"

    async def test_다시_보이면_listed로_돌아온다(self, session_factory) -> None:
        await seed(session_factory, "KOSPI", KOSPI_ROWS, now=YESTERDAY_NOW - dt.timedelta(days=1))
        await seed(session_factory, "KOSPI", KOSPI_ROWS[:3], now=YESTERDAY_NOW)
        await seed(session_factory, "KOSPI", KOSPI_ROWS)
        rows = await listings(session_factory)
        assert rows["0030R0"].status == "listed"
        assert rows["0030R0"].last_seen_at == NOW

    async def test_다른_단위의_종목은_건드리지_않는다(self, session_factory) -> None:
        """FR-015 — KOSPI만 받고 전체를 그것으로 바꾸면 KOSDAQ 종목이 조용히 사라진다."""
        await seed(session_factory, "KOSDAQ", [kr_row("247540", "에코프로비엠", "코스닥")])
        await seed(session_factory, "KOSPI", KOSPI_ROWS)
        rows = await listings(session_factory)
        assert rows["247540"].status == "listed" and rows["247540"].unit == "KOSDAQ"


class Test단위를_옮긴_종목:
    """FR-019a — 코스닥 → 코스피 이전상장. 행은 하나이고, 갱신 순서와 무관하게 결과가 같다."""

    MOVED = kr_row("091990", "셀트리온헬스케어", "코스닥")
    STAY = [kr_row("247540", "에코프로비엠", "코스닥"), kr_row("086520", "에코프로", "코스닥"),
            kr_row("028300", "HLB", "코스닥")]

    async def _before(self, session_factory) -> None:  # type: ignore[no-untyped-def]
        before = YESTERDAY_NOW
        await seed(session_factory, "KOSDAQ", [*self.STAY, self.MOVED], now=before)
        await seed(session_factory, "KOSPI", KOSPI_ROWS, now=before)

    def _moved_to_kospi(self) -> list[dict[str, str]]:
        return [*KOSPI_ROWS, dict(self.MOVED, marketName="거래소")]

    async def _check(self, session_factory) -> None:  # type: ignore[no-untyped-def]
        async with session_factory() as s:
            moved = (await s.execute(select(StockListing).where(
                StockListing.code == "091990"))).scalars().all()
        assert len(moved) == 1
        assert moved[0].unit == "KOSPI"
        assert moved[0].status == "listed"

    async def test_코스피가_먼저(self, session_factory) -> None:
        await self._before(session_factory)
        await seed(session_factory, "KOSPI", self._moved_to_kospi(), now=NOW)
        await seed(session_factory, "KOSDAQ", self.STAY, now=NOW + dt.timedelta(minutes=1))
        await self._check(session_factory)

    async def test_코스닥이_먼저(self, session_factory) -> None:
        await self._before(session_factory)
        await seed(session_factory, "KOSDAQ", self.STAY, now=NOW)
        await seed(session_factory, "KOSPI", self._moved_to_kospi(),
                   now=NOW + dt.timedelta(minutes=1))
        await self._check(session_factory)


class Test원본_보관:
    """FR-061, research R6-13 — 원본은 지우지 않고, 같은 본문은 한 번만 저장한다."""

    async def test_쪽마다_본문을_해시로_가리킨다(self, session_factory) -> None:
        body = kr_body(KOSPI_ROWS)
        await run(session_factory, "KOSPI", [page(body)])
        async with session_factory() as s:
            raw = (await s.execute(select(StockListingRaw))).scalars().all()
            bodies = (await s.execute(select(StockListingRawBody))).scalars().all()
        assert len(raw) == 1 and len(bodies) == 1
        digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
        assert raw[0].body_sha256 == digest == bodies[0].sha256
        assert (raw[0].unit, raw[0].page_no, raw[0].status_code) == ("KOSPI", 1, 200)
        assert raw[0].batch_started_at == NOW
        assert bodies[0].body == body

    async def test_헤더와_인증_정보를_남기지_않는다(self, session_factory) -> None:
        await run(session_factory, "KOSPI", [page(kr_body(KOSPI_ROWS))])
        async with session_factory() as s:
            bodies = (await s.execute(select(StockListingRawBody.body))).scalars().all()
        for text in bodies:
            for secret in (APP_KEY, APP_SECRET, "authorization", "Bearer", "cont-yn"):
                assert secret not in text

    async def test_같은_본문은_한_번만_저장하고_쪽_기록은_남는다(self, session_factory) -> None:
        body = kr_body(KOSPI_ROWS)
        await run(session_factory, "KOSPI", [page(body)], now=YESTERDAY_NOW)
        await run(session_factory, "KOSPI", [page(body)])
        raw_count = await count(session_factory, StockListingRaw)
        body_count = await count(session_factory, StockListingRawBody)
        async with session_factory() as s:
            first = (await s.execute(select(StockListingRawBody))).scalar_one()
        assert raw_count == 2
        assert body_count == 1
        assert first.first_stored_at == YESTERDAY_NOW

    async def test_여러_쪽을_각각_남긴다(self, session_factory) -> None:
        first, second = kr_body(KOSPI_ROWS[:2]), kr_body(KOSPI_ROWS[2:])
        result = await run(session_factory, "KOSPI",
                           [page(first, 1, cont_yn="Y"), page(second, 2)])
        assert result.outcome == "replaced" and result.rows == 4
        async with session_factory() as s:
            pages = (await s.execute(
                select(StockListingRaw.page_no).order_by(StockListingRaw.page_no))).scalars().all()
        assert pages == [1, 2]

    async def test_실패한_갱신의_원본도_남긴다(self, session_factory) -> None:
        """무엇이 잘못 왔는지 되짚는 근거가 그것이다."""
        await seed(session_factory, "KOSPI", rows_of(10), now=YESTERDAY_NOW)
        await run(session_factory, "KOSPI", [page(kr_body(rows_of(4)))])
        assert await count(session_factory, StockListingRaw) == 2

    async def test_이전_원본을_지우지_않는다(self, session_factory) -> None:
        for days in range(10, 0, -1):
            await seed(session_factory, "KOSPI", rows_of(5 + days),
                       now=NOW - dt.timedelta(days=days))
        assert await count(session_factory, StockListingRaw) == 10
        assert await count(session_factory, StockListingRawBody) == 10
