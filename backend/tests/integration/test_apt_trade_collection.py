"""실거래 수집 실행기 (T015) — 009 FR-008~FR-014, FR-019, SC-006, SC-011, SC-012, research
R9-4·R9-5.

가짜 포털(T001 픽스처)로 실제 클라이언트·관문을 거쳐 송파구(11710)를 받는다. 실행 날짜는
2023-10-05(한국 시간 — `apt_support`).

- **첫 달은 발견한다**: `APT_TRADE_PROBE_START`부터 받고 처음 거래가 있는 달(송파구 2005-12)을
  기록한다
- 달마다 `totalCount`만큼 쪽을 넘긴다(2020-06은 2쪽). 거래는 upsert — 다시 받아도 행이 늘지 않고
  `ingested_at`은
  처음 받은 시각 그대로. 원본은 쪽마다 한 행(본문만), 같은 본문이면 늘지 않는다
- 잠정 12개월: 최근 3개월은 하루 한 번, 4~12개월 전 달은 한 달에 한 번 다시 받는다. 벗어난 달은 다음
  확인에서
  한 번 더 받고 확정이다. 다시 받기에서 바뀐 수(더함·해제·사라짐)는 `apt_trade_revised` 사건이다
- 실패하면 종류를 남기고 그 달은 커버리지에 없다(앞 달은 남는다). `checked_on`은 성공했을 때만
  바뀐다
- 하루 한도에 닿으면 받은 달까지 남기고 `rate_limited`로 멈춘다 — 다음 실행은 받은 달 뒤부터
"""
from __future__ import annotations

import datetime as dt
import re

import aiohttp
import pytest
from sqlalchemy import func, select

from src.db.models import (
    AptCollectionJob,
    AptListState,
    AptRawResponse,
    AptTrade,
    AptTradeCoverage,
    JobStatus,
)
from src.ingestion.datagokr.client import DataGoKrClient
from src.repository import apt_job
from src.repository.apt_usage import ApiUsageCounter
from src.worker import apt_worker
from src.worker.apt_queue import AptWork
from tests.integration.apt_support import (
    KEY,
    NOW_UTC,
    FakePortal,
    Response,
    apt_settings,
    fixture,
    months,
    portal_client,
)

D = dt.date.fromisoformat
FAST = apt_settings(apt_trade_probe_start=D("2022-10-01"))  # 2022-10 ~ 2023-10, 13개월


def at(day: str) -> dt.datetime:
    """그날 한국 시간 12:00의 UTC."""
    return dt.datetime.combine(D(day), dt.time(3, 0))


async def collect(session_factory, client: DataGoKrClient, *, now: dt.datetime = NOW_UTC,  # type: ignore[no-untyped-def]
                  settings=FAST, lawd: str = "11710") -> tuple[JobStatus, int]:
    async with session_factory() as s:
        job_id, created = await apt_job.acquire_or_get_running(s, "trade", lawd, total=0)
        await s.commit()
    assert created
    status = await apt_worker.run_trade_job(
        session_factory, client, AptWork(job_id, "trade", lawd), settings=settings, now=now)
    return status, job_id


async def coverage(session_factory, lawd: str = "11710") -> dict[str, AptTradeCoverage]:  # type: ignore[no-untyped-def]
    async with session_factory() as s:
        rows = (await s.execute(select(AptTradeCoverage).where(
            AptTradeCoverage.lawd_cd == lawd))).scalars().all()
    return {r.deal_ym: r for r in rows}


async def count(session_factory, model, *where) -> int:  # type: ignore[no-untyped-def]
    async with session_factory() as s:
        return int((await s.execute(select(func.count()).select_from(model).where(*where)))
                   .scalar_one())


async def job(session_factory, job_id: int) -> AptCollectionJob:  # type: ignore[no-untyped-def]
    async with session_factory() as s:
        found = await s.get(AptCollectionJob, job_id)
    assert found is not None
    return found


def trade_months(portal: FakePortal) -> list[str]:
    return [q["DEAL_YMD"] for q in portal.calls("trade")]


def revised(captured: list) -> list[dict[str, object]]:  # type: ignore[type-arg]
    return [r.__dict__ for r in captured if getattr(r, "event", None) == "apt_trade_revised"]


def cancel_first_row(body: str) -> str:
    """첫 행에 해제 표시를 붙인다(출처가 나중에 해제를 알린 경우)."""
    return body.replace("<cdealDay> </cdealDay><cdealType> </cdealType>",
                        "<cdealDay>23.10.06</cdealDay><cdealType>O</cdealType>", 1)


def drop_first_row(body: str) -> str:
    """첫 행을 지우고 전체 건수를 줄인다(출처가 거래를 지운 경우)."""
    start, end = body.index("<item>"), body.index("</item>") + len("</item>")
    total = int(re.search(r"<totalCount>(\d+)</totalCount>", body).group(1))  # type: ignore[union-attr]
    body = body[:start] + body[end:]
    return body.replace(f"<totalCount>{total}</totalCount>",
                        f"<totalCount>{total - 1}</totalCount>")


def truncate(body: str) -> str:
    """첫 행을 지우되 전체 건수는 그대로 — 잘린 응답."""
    start, end = body.index("<item>"), body.index("</item>") + len("</item>")
    return body[:start] + body[end:]


def add_row(body: str) -> str:
    """첫 행을 금액만 바꿔 하나 더한다(늦게 신고된 거래)."""
    start, end = body.index("<item>"), body.index("</item>") + len("</item>")
    item = re.sub(r"<dealAmount>[^<]+</dealAmount>", "<dealAmount>1,234,567</dealAmount>",
                  body[start:end])
    total = int(re.search(r"<totalCount>(\d+)</totalCount>", body).group(1))  # type: ignore[union-attr]
    body = body[:end] + item + body[end:]
    return body.replace(f"<totalCount>{total}</totalCount>",
                        f"<totalCount>{total + 1}</totalCount>")


def only(ym: str, edit):  # type: ignore[no-untyped-def]
    def apply(lawd: str, month: str, page: int, body: str) -> str:
        return edit(body) if month == ym and page == 1 else body
    return apply


class Test처음_받기:
    async def test_첫_달을_발견하고_전체_이력을_받는다(self, session_factory) -> None:  # type: ignore[no-untyped-def]
        """2005-10부터 탐색 — 처음 거래가 있는 달은 2005-12다. 2005-10 ~ 2023-10, 217개월."""
        portal = FakePortal()
        settings = apt_settings(apt_trade_probe_start=D("2005-10-01"))
        status, job_id = await collect(session_factory, portal_client(portal, settings),
                                       settings=settings)
        assert status is JobStatus.SUCCEEDED
        expected = months("200510", "202310")
        assert trade_months(portal) == expected[:expected.index("202006") + 1] + [
            "202006"] + expected[expected.index("202006") + 1:]  # 2020-06은 2쪽
        async with session_factory() as s:
            state = await s.get(AptListState, "sgg:11710")
        assert state is not None and state.first_trade_ym == "200512"
        cov = await coverage(session_factory)
        assert sorted(cov) == expected
        assert (cov["202006"].trade_rows, cov["200512"].trade_rows, cov["201501"].trade_rows) == (
            1173, 3, 0)
        assert {m for m, c in cov.items() if c.state == "provisional"} == set(
            months("202211", "202310"))
        assert {c.checked_on for c in cov.values()} == {D("2023-10-05")}
        assert await count(session_factory, AptTrade) == 9758 + 3
        done = await job(session_factory, job_id)
        assert (done.status, done.total, done.done) == (JobStatus.SUCCEEDED, 217, 217)

    async def test_거래와_원본(self, session_factory) -> None:  # type: ignore[no-untyped-def]
        portal = FakePortal()
        await collect(session_factory, portal_client(portal))
        async with session_factory() as s:
            trade = (await s.execute(select(AptTrade).where(
                AptTrade.apt_seq == "11710-8865", AptTrade.deal_date == D("2023-09-28"))
            )).scalars().first()
            raws = (await s.execute(select(AptRawResponse))).scalars().all()
        assert trade is not None
        assert (trade.source, trade.ingested_at, trade.lawd_cd, trade.deal_ym) == (
            "molit:aptdev", NOW_UTC, "11710", "202309")
        assert len(raws) == 13  # 13개월 × 1쪽
        first = next(r for r in raws if r.request_ref == "11710/202301/p1")
        assert first.endpoint == "trade" and first.status_code == 200
        assert first.body == fixture("trade_11710_202301_p1.xml.gz")
        assert all(KEY not in r.body for r in raws)


class Test다시_받기:
    async def test_같은_달을_다시_받아도_행이_늘지_않는다(self, session_factory) -> None:  # type: ignore[no-untyped-def]
        portal = FakePortal()
        client = portal_client(portal)
        await collect(session_factory, client)
        trades, raws = await count(session_factory, AptTrade), await count(session_factory,
                                                                          AptRawResponse)
        await collect(session_factory, client, now=at("2023-10-06"))
        assert trade_months(portal)[13:] == ["202308", "202309", "202310"]  # 최근 3개월만
        assert await count(session_factory, AptTrade) == trades
        # 같은 본문 — 원본이 늘지 않는다
        assert await count(session_factory, AptRawResponse) == raws
        async with session_factory() as s:
            ingested = set((await s.execute(select(AptTrade.ingested_at).distinct())).scalars())
        assert ingested == {NOW_UTC}
        cov = await coverage(session_factory)
        assert cov["202309"].checked_on == D("2023-10-06")
        assert cov["202307"].checked_on == D("2023-10-05")

    async def test_오늘_이미_받았으면_다시_보내지_않는다(self, session_factory) -> None:  # type: ignore[no-untyped-def]
        portal = FakePortal()
        client = portal_client(portal)
        await collect(session_factory, client)
        await collect(session_factory, client, now=at("2023-10-05") + dt.timedelta(hours=5))
        assert len(trade_months(portal)) == 13

    async def test_해제가_붙으면_같은_행이_해제로(self, session_factory, captured) -> None:  # type: ignore[no-untyped-def]
        portal = FakePortal()
        client = portal_client(portal)
        await collect(session_factory, client)
        trades = await count(session_factory, AptTrade)
        portal.edit_trades = only("202309", cancel_first_row)
        await collect(session_factory, client, now=at("2023-10-06"))
        assert await count(session_factory, AptTrade) == trades
        assert await count(session_factory, AptTrade, AptTrade.cancelled.is_(True),
                           AptTrade.cancelled_on == D("2023-10-06")) == 1
        assert await count(session_factory, AptRawResponse,
                           AptRawResponse.request_ref == "11710/202309/p1") == 2  # 새 판
        events = revised(captured)
        assert [(e["lawd_cd"], e["month"], e["added"], e["cancelled"], e["missing"])
                for e in events] == [("11710", "2023-09", 0, 1, 0)]

    async def test_사라진_행은_지우지_않고_표시한다(self, session_factory, captured) -> None:  # type: ignore[no-untyped-def]
        portal = FakePortal()
        client = portal_client(portal)
        await collect(session_factory, client)
        trades = await count(session_factory, AptTrade)
        portal.edit_trades = only("202309", drop_first_row)
        await collect(session_factory, client, now=at("2023-10-06"))
        assert await count(session_factory, AptTrade) == trades  # 지우지 않는다
        assert await count(session_factory, AptTrade, AptTrade.missing_since == at("2023-10-06"),
                           AptTrade.missing_reason == "absent") == 1
        assert [(e["added"], e["cancelled"], e["missing"]) for e in revised(captured)] == [
            (0, 0, 1)]
        total = int(re.search(r"<totalCount>(\d+)",  # type: ignore[union-attr]
                              fixture("trade_11710_202309_p1.xml.gz")).group(1))
        assert (await coverage(session_factory))["202309"].trade_rows == total - 1

    async def test_새_거래는_더한다(self, session_factory, captured) -> None:  # type: ignore[no-untyped-def]
        portal = FakePortal()
        client = portal_client(portal)
        await collect(session_factory, client)
        trades = await count(session_factory, AptTrade)
        portal.edit_trades = only("202308", add_row)
        await collect(session_factory, client, now=at("2023-10-06"))
        assert await count(session_factory, AptTrade) == trades + 1
        assert await count(session_factory, AptTrade, AptTrade.amount == 12_345_670_000) == 1
        assert [(e["month"], e["added"]) for e in revised(captured)] == [("2023-08", 1)]


class Test잠정_빈도:
    async def test_최근_3개월은_하루_한_번_4_12개월은_한_달에_한_번(self, session_factory) -> None:  # type: ignore[no-untyped-def]
        portal = FakePortal()
        client = portal_client(portal)
        await collect(session_factory, client)  # 2023-10-05
        await collect(session_factory, client, now=at("2023-10-20"))
        assert trade_months(portal)[13:] == ["202308", "202309", "202310"]
        await collect(session_factory, client, now=at("2023-11-02"))
        # 새 달: 최근 3개월(2023-09~11) + 4~12개월 전(2022-12~2023-08) + 잠정을 벗어난 2022-11(확정
        # 전 한 번 더)
        assert trade_months(portal)[16:] == months("202211", "202311")
        cov = await coverage(session_factory)
        assert (cov["202211"].state, cov["202212"].state) == ("confirmed", "provisional")
        assert cov["202210"].checked_on == D("2023-10-05")  # 확정 달은 다시 받지 않는다
        await collect(session_factory, client, now=at("2023-11-03"))
        assert trade_months(portal)[29:] == ["202309", "202310", "202311"]

    async def test_늦게_붙은_해제가_사건으로_남는다(self, session_factory, captured) -> None:  # type: ignore[no-untyped-def]
        """4~12개월 전 달(2023-02)의 해제는 새 달의 첫 확인에서 잡힌다(잠정 12개월 — R9-5)."""
        portal = FakePortal()
        client = portal_client(portal)
        await collect(session_factory, client)
        portal.edit_trades = only("202302", cancel_first_row)
        await collect(session_factory, client, now=at("2023-11-02"))
        assert [(e["month"], e["cancelled"]) for e in revised(captured)] == [("2023-02", 1)]


class Test실패:
    @pytest.mark.parametrize(("respond", "kind"), [
        (lambda: Response(fixture("gateway_30.xml"), 403), "auth"),
        (lambda: Response(fixture("gateway_22.xml"), 429), "rate_limited"),
        (lambda: Response(truncate(fixture("trade_11710_202301_p1.xml.gz"))), "format"),
        (lambda: aiohttp.ClientConnectionError(
            f"Cannot connect to https://apis.data.go.kr/x?serviceKey={KEY}"), "network"),
    ])
    async def test_실패한_달은_커버리지에_없고_앞_달은_남는다(  # type: ignore[no-untyped-def]
            self, session_factory, captured, respond, kind: str) -> None:
        portal = FakePortal()
        portal.overrides.append(
            lambda api, q: respond() if q.get("DEAL_YMD") == "202301" else None)
        status, job_id = await collect(session_factory, portal_client(portal))
        assert status is JobStatus.FAILED
        cov = await coverage(session_factory)
        assert sorted(cov) == ["202210", "202211", "202212"]  # 2023-01부터는 없다
        failed = await job(session_factory, job_id)
        assert failed.last_error is not None and failed.last_error.startswith(f"{kind}: ")
        assert KEY not in failed.last_error
        assert (failed.done, failed.total) == (3, 13)
        logged = [r.__dict__ for r in captured
                  if getattr(r, "event", None) == "apt_collection_failed"]
        assert [(e["lawd_cd"], e["kind"]) for e in logged] == [("11710", kind)]
        assert all(KEY not in str(r.__dict__) for r in captured)

    async def test_실패하면_확인한_날을_바꾸지_않는다(self, session_factory) -> None:  # type: ignore[no-untyped-def]
        portal = FakePortal()
        client = portal_client(portal)
        await collect(session_factory, client)
        portal.overrides.append(
            lambda api, q: Response("Service Unavailable", 503)
            if q.get("DEAL_YMD") == "202309" else None)
        status, _ = await collect(session_factory, client, now=at("2023-10-06"))
        assert status is JobStatus.FAILED
        cov = await coverage(session_factory)
        assert cov["202308"].checked_on == D("2023-10-06")
        assert cov["202309"].checked_on == D("2023-10-05")

    async def test_하루_한도에_닿으면_받은_달까지_남기고_다음은_이어서(  # type: ignore[no-untyped-def]
            self, session_factory) -> None:
        portal = FakePortal()
        counter = ApiUsageCounter(session_factory)
        settings = apt_settings(apt_trade_probe_start=D("2005-10-01"))
        client = portal_client(portal, settings, counter=counter, limits={
            "trade": 50, "region": 9000, "kapt": 4500})
        status, job_id = await collect(session_factory, client, settings=settings)
        assert status is JobStatus.FAILED
        failed = await job(session_factory, job_id)
        assert failed.last_error is not None and failed.last_error.startswith("rate_limited: ")
        cov = await coverage(session_factory)
        assert sorted(cov) == months("200510", "200911")  # 50개월
        assert len(portal.urls) == 50  # 51번째는 보내지 않았다
        # 다음 날 — 받은 달 뒤부터
        tomorrow = portal_client(portal, settings, counter=counter, limits={
            "trade": 50, "region": 9000, "kapt": 4500}, today=D("2023-10-06"))
        await collect(session_factory, tomorrow, settings=settings, now=at("2023-10-06"))
        assert trade_months(portal)[50] == "200912"

    async def test_같은_시군구_점유_중이면_두_번째_작업이_없다(self, session_factory) -> None:  # type: ignore[no-untyped-def]
        async with session_factory() as s:
            first, created = await apt_job.acquire_or_get_running(s, "trade", "11710", total=13)
            await s.commit()
            second, again = await apt_job.acquire_or_get_running(s, "trade", "11710", total=13)
        assert created and not again and first == second
        assert await count(session_factory, AptCollectionJob) == 1


class Test로그:
    async def test_시작과_완료(self, session_factory, captured) -> None:  # type: ignore[no-untyped-def]
        _, job_id = await collect(session_factory, portal_client(FakePortal()))
        events = [(r.__dict__["event"], r.__dict__.get("lawd_cd"), r.__dict__.get("job"))
                  for r in captured if str(getattr(r, "event", "")).startswith("apt_collection_")]
        assert events == [("apt_collection_started", "11710", job_id),
                          ("apt_collection_completed", "11710", job_id)]
        completed = next(r.__dict__ for r in captured
                         if getattr(r, "event", None) == "apt_collection_completed")
        assert (completed["first"], completed["last"]) == ("2022-10", "2023-10")
