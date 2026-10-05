"""목록 줄 — 행정구역·단지 목록·기본 정보·짝짓기 (T016) — 009 FR-002, FR-003, FR-012, FR-014,
FR-015, FR-032, research R9-3.

- 행정구역은 전국을 받아 upsert한다(`seen_at`). 다음 갱신에서 **사라진 코드는 지우지 않고
  `retired_at`** —
  시·군·구면 그 `lawd_cd`의 거래를 `missing_since`(`region_retired`)로 집계에서 뺀다(출처는 과거
  거래도 새 코드로만 준다)
- 단지 목록은 동을 고를 때 요청 경로에서 1회(이름 곧바로), 30일 지나면 다시. 기본 정보는 새 단지만
  1회로
  세대수·입주년도를 채운다
- 실거래를 받으면 실거래 단지가 더해지고 짝지은 단지는 한 행이다. 단지 목록이 먼저면 그 행에
  `apt_seq`를
  붙이고, 실거래가 먼저면 이름으로 짝지은 행에 `kapt_code`를 붙인다. **두 행이 이미 따로 있을 때
  짝이 드러나면**(기본 정보로 지번을 알게 됨) 먼저 만든 행에 합치고 다른 행은 `merged_into`(지우지
  않는다)
- 입주년도는 사용승인 연도(`kapt`), 없으면 실거래 건축년도(`trade`)
"""
from __future__ import annotations

import datetime as dt
from decimal import Decimal

from sqlalchemy import func, select

from src.api.services import realestate_lists
from src.db.models import (
    AptCollectionJob,
    AptComplex,
    AptListState,
    AptRegion,
    AptTrade,
    JobStatus,
)
from src.repository import apt_job
from src.worker import apt_worker
from src.worker.apt_queue import AptWork
from tests.integration.apt_support import (
    KEY,
    NOW_UTC,
    FakePortal,
    Response,
    apt_settings,
    fixture,
    portal_client,
)

D = dt.date.fromisoformat
GARAK = "1171010700"
#: 픽스처 범위 전부(78개 실거래 단지).
FROM_2020 = apt_settings(apt_trade_probe_start=D("2020-01-01"))


def later(days: int) -> dt.datetime:
    return NOW_UTC + dt.timedelta(days=days)


async def run(session_factory, client, kind: str, target: str, *,  # type: ignore[no-untyped-def]
              now: dt.datetime = NOW_UTC, settings=None) -> tuple[JobStatus, int]:
    settings = settings or apt_settings()
    async with session_factory() as s:
        job_id, _ = await apt_job.acquire_or_get_running(s, kind, target, total=0)
        await s.commit()
    runner = apt_worker.run_trade_job if kind == "trade" else apt_worker.run_list_job
    status = await runner(session_factory, client, AptWork(job_id, kind, target),
                          settings=settings, now=now)
    return status, job_id


async def regions(session_factory) -> dict[str, AptRegion]:  # type: ignore[no-untyped-def]
    async with session_factory() as s:
        return {r.code: r for r in (await s.execute(select(AptRegion))).scalars()}


async def complexes(session_factory, umd: str = GARAK) -> list[AptComplex]:  # type: ignore[no-untyped-def]
    async with session_factory() as s:
        return list((await s.execute(select(AptComplex).where(
            AptComplex.umd_code == umd).order_by(AptComplex.id))).scalars())


async def load_list(session_factory, client, *, now: dt.datetime = NOW_UTC):  # type: ignore[no-untyped-def]
    async with session_factory() as s:
        outcome = await realestate_lists.load_complex_list(
            s, client, GARAK, settings=apt_settings(), now=now)
        await s.commit()
    return outcome


class Test행정구역:
    async def test_전국을_받아_단계를_만든다(self, session_factory) -> None:  # type: ignore[no-untyped-def]
        portal = FakePortal()
        status, job_id = await run(session_factory, portal_client(portal), "region", "regions")
        assert status is JobStatus.SUCCEEDED
        got = await regions(session_factory)
        assert (got["1100000000"].level, got["1100000000"].name) == ("sido", "서울특별시")
        assert (got["1171000000"].level, got["1171000000"].lawd_cd,
                got["1171000000"].parent_code) == ("sgg", "11710", "1100000000")
        assert (got[GARAK].name, got[GARAK].level, got[GARAK].parent_code) == (
            "가락동", "umd", "1171000000")
        assert got["4111100000"].name == "수원시 장안구"
        assert "4111000000" not in got  # 일반시(수원시)는 시·군·구에서 뺀다
        assert all(code[8:] == "00" for code in got)  # 리 없음
        assert {r.seen_at for r in got.values()} == {NOW_UTC}
        assert {r.retired_at for r in got.values()} == {None}
        async with session_factory() as s:
            state = await s.get(AptListState, "regions")
            job = await s.get(AptCollectionJob, job_id)
        assert state is not None and state.refreshed_at == NOW_UTC
        assert job is not None and (job.total, job.done) == (1, 1)
        assert len(portal.calls("region")) == 1

    async def test_사라진_코드는_지우지_않고_retired_at과_그_거래는_집계에서_뺀다(  # type: ignore[no-untyped-def]
            self, session_factory) -> None:
        """2023 강원특별자치도 개편 — 옛 강원도(42…) 코드가 다음 갱신에서 사라진다."""
        await run(session_factory, portal_client(FakePortal(old_gangwon=True)), "region",
                  "regions")
        async with session_factory() as s:
            for occurrence, amount in enumerate((300_000_000, 310_000_000)):
                s.add(AptTrade(
                    lawd_cd="42110", deal_ym="202001", deal_date=D("2020-01-10"),
                    apt_seq="42110-7", umd_code="4211010100", jibun="1", apt_name="옛단지",
                    apt_dong="", floor=3, excl_area=Decimal("84.9"), amount=amount,
                    occurrence=occurrence, cancelled=False, source="molit:aptdev",
                    ingested_at=NOW_UTC))
            await s.commit()
        await run(session_factory, portal_client(FakePortal()), "region", "regions",
                  now=later(31))
        got = await regions(session_factory)
        assert got["4211000000"].retired_at == later(31)
        assert got["4200000000"].retired_at == later(31)
        assert got["5111000000"].retired_at is None
        async with session_factory() as s:
            marks = (await s.execute(select(AptTrade.missing_since, AptTrade.missing_reason))).all()
        assert set(marks) == {(later(31), "region_retired")}

    async def test_받지_못하면_아무것도_바꾸지_않는다(self, session_factory) -> None:  # type: ignore[no-untyped-def]
        portal = FakePortal()
        portal.overrides.append(lambda api, q: Response("<html>점검", 200))
        status, job_id = await run(session_factory, portal_client(portal), "region", "regions")
        assert status is JobStatus.FAILED
        assert await regions(session_factory) == {}
        async with session_factory() as s:
            job = await s.get(AptCollectionJob, job_id)
            state = await s.get(AptListState, "regions")
        assert job is not None and job.last_error is not None
        assert job.last_error.startswith("network: ") and KEY not in job.last_error
        assert state is None


class Test단지_목록:
    async def test_요청_경로에서_한_번_이름을_곧바로(self, session_factory) -> None:  # type: ignore[no-untyped-def]
        portal = FakePortal()
        client = portal_client(portal)
        outcome = await load_list(session_factory, client)
        assert outcome.error is None
        rows = await complexes(session_factory)
        assert len(rows) == 23
        helio = next(r for r in rows if r.kapt_code == "A10025850")
        assert (helio.name, helio.lawd_cd, helio.apt_seq, helio.households) == (
            "헬리오시티아파트", "11710", None, None)
        async with session_factory() as s:
            state = await s.get(AptListState, f"umd:{GARAK}")
        assert state is not None and state.refreshed_at == NOW_UTC
        await load_list(session_factory, client, now=later(29))
        assert len(portal.calls("complex_list")) == 1  # 30일 안에는 다시 받지 않는다
        await load_list(session_factory, client, now=later(31))
        assert len(portal.calls("complex_list")) == 2
        assert len(await complexes(session_factory)) == 23  # 다시 받아도 행이 늘지 않는다

    async def test_받지_못하면_종류와_사유(self, session_factory) -> None:  # type: ignore[no-untyped-def]
        portal = FakePortal()
        portal.overrides.append(lambda api, q: Response(fixture("gateway_30.xml"), 403))
        outcome = await load_list(session_factory, portal_client(portal))
        assert outcome.error is not None and outcome.error[0] == "auth"
        assert KEY not in outcome.error[1]
        assert await complexes(session_factory) == []
        async with session_factory() as s:
            assert await s.get(AptListState, f"umd:{GARAK}") is None


class Test기본_정보:
    async def test_새_단지만_한_번씩_세대수와_입주년도(self, session_factory) -> None:  # type: ignore[no-untyped-def]
        portal = FakePortal()
        client = portal_client(portal)
        await load_list(session_factory, client)
        status, job_id = await run(session_factory, client, "complex_details", GARAK)
        assert status is JobStatus.SUCCEEDED
        rows = {r.kapt_code: r for r in await complexes(session_factory)}
        helio = rows["A10025850"]
        assert (helio.households, helio.move_in_year, helio.move_in_source, helio.jibun) == (
            9510, 2018, "kapt", "479")
        assert helio.details_checked_at == NOW_UTC
        assert rows["A10020074"].households == 183  # 세대수 0.0 → 호수
        assert rows["A10020074"].jibun == "161-3"
        async with session_factory() as s:
            job = await s.get(AptCollectionJob, job_id)
        assert job is not None and (job.total, job.done) == (23, 23)
        assert len(portal.calls("complex_basis")) == 23
        await run(session_factory, client, "complex_details", GARAK, now=later(1))
        assert len(portal.calls("complex_basis")) == 23  # 받은 단지는 다시 받지 않는다

    async def test_실패하면_종류를_남기고_받은_단지는_남는다(self, session_factory) -> None:  # type: ignore[no-untyped-def]
        portal = FakePortal()
        client = portal_client(portal)
        await load_list(session_factory, client)
        calls = {"n": 0}

        def fifth_fails(api: str, q: dict[str, str]) -> Response | None:
            if api != "complex_basis":
                return None
            calls["n"] += 1
            return Response(fixture("gateway_22.xml"), 429) if calls["n"] == 5 else None

        portal.overrides.append(fifth_fails)
        status, job_id = await run(session_factory, client, "complex_details", GARAK)
        assert status is JobStatus.FAILED
        async with session_factory() as s:
            job = await s.get(AptCollectionJob, job_id)
        assert job is not None and job.last_error is not None
        assert job.last_error.startswith("rate_limited: ") and job.done == 4
        filled = [r for r in await complexes(session_factory) if r.details_checked_at]
        assert len(filled) == 4


class Test짝짓기:
    async def test_단지_목록이_먼저면_그_행에_apt_seq를_붙인다(self, session_factory) -> None:  # type: ignore[no-untyped-def]
        portal = FakePortal()
        client = portal_client(portal)
        await load_list(session_factory, client)
        await run(session_factory, client, "complex_details", GARAK)
        before = {r.kapt_code: r.id for r in await complexes(session_factory)}
        await run(session_factory, client, "trade", "11710", settings=FROM_2020)
        rows = await complexes(session_factory)
        live = [r for r in rows if r.merged_into is None]
        assert len(live) == 23 + 56 and len(rows) == len(live)  # 합칠 것 없이 붙였다
        helio = next(r for r in live if r.kapt_code == "A10025850")
        assert (helio.id, helio.apt_seq, helio.households, helio.jibun) == (
            before["A10025850"], "11710-8865", 9510, "913")
        assert sum(1 for r in live if r.apt_seq and r.kapt_code) == 22
        trade_only = next(r for r in live if r.apt_seq == "11710-7775")  # 현진타워
        assert (trade_only.name, trade_only.kapt_code, trade_only.households) == (
            "현진타워", None, None)
        assert (trade_only.move_in_year, trade_only.move_in_source) == (2015, "trade")

    async def test_실거래가_먼저면_나중에_드러난_짝을_먼저_만든_행에_합친다(  # type: ignore[no-untyped-def]
            self, session_factory) -> None:
        portal = FakePortal()
        client = portal_client(portal)
        await run(session_factory, client, "trade", "11710", settings=FROM_2020)
        trade_ids = {r.apt_seq: r.id for r in await complexes(session_factory)}
        assert len(trade_ids) == 78
        await load_list(session_factory, client)  # 지번을 아직 모른다 — 이름으로만 짝짓는다
        rows = await complexes(session_factory)
        helio = next(r for r in rows if r.apt_seq == "11710-8865")
        assert (helio.id, helio.kapt_code) == (trade_ids["11710-8865"], "A10025850")
        await run(session_factory, client, "complex_details", GARAK)  # 지번이 드러난다
        rows = await complexes(session_factory)
        merged = [r for r in rows if r.merged_into is not None]
        live = [r for r in rows if r.merged_into is None]
        assert len(live) == 23 + 56
        assert merged, "지번으로 드러난 짝은 이미 따로 있던 두 행이다"
        for row in merged:
            keep = next(r for r in rows if r.id == row.merged_into)
            assert keep.id < row.id and keep.kapt_code and keep.apt_seq
            assert (row.kapt_code, row.apt_seq) == (None, None)  # 식별자를 옮겼다
        pungrim = next(r for r in live if r.kapt_code == "A10021256")  # 가락풍림 ↔ 풍림1(지번 142)
        assert (pungrim.id, pungrim.apt_seq, pungrim.households) == (
            trade_ids["11710-65"], "11710-65", 105)

    async def test_새_코드로_받은_거래의_같은_단지는_코드가_바뀐다(self, session_factory) -> None:  # type: ignore[no-untyped-def]
        """춘천 51110 2020-01의 단지 하나가 옛 코드(42110)로 남아 있었다 — 같은 `aptSeq`면 새
        코드로."""
        page = fixture("trade_51110_202001_p1.xml.gz")
        seq = page.split("<aptSeq>")[1].split("</aptSeq>")[0]
        umd = "51110" + page.split("<umdCd>")[1].split("</umdCd>")[0]
        async with session_factory() as s:
            s.add_all([AptComplex(umd_code="4211010100", lawd_cd="42110", apt_seq=seq, name="옛"),
                       AptComplex(umd_code="4211010100", lawd_cd="42110", apt_seq="42110-77",
                                  name="식별자도 바뀐 단지")])
            await s.commit()
        await run(session_factory, portal_client(FakePortal()), "trade", "51110",
                  settings=FROM_2020)
        async with session_factory() as s:
            moved = (await s.execute(select(AptComplex).where(AptComplex.apt_seq == seq))
                     ).scalar_one()
            stale = (await s.execute(select(AptComplex).where(
                AptComplex.apt_seq == "42110-77"))).scalar_one()
            total = (await s.execute(select(func.count()).select_from(AptComplex).where(
                AptComplex.apt_seq == seq))).scalar_one()
        assert (moved.lawd_cd, moved.umd_code, total) == ("51110", umd, 1)
        assert (stale.lawd_cd, stale.umd_code) == ("42110", "4211010100")
