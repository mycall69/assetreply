"""행정구역·단지·평형 API (T017) — 009 FR-002~FR-005, FR-011, FR-012, FR-014, FR-015, FR-032,
SC-007, contracts/rest-api.

- 행정구역: 처음이면 202(`kind: region`)와 수집 요청. 받은 뒤 시·도 → 시·군·구 → 법정동(가나다순,
  **현존
  코드만**). 30일이 지났으면 받아 둔 목록으로 200을 주고 백그라운드로 다시 받는다
- 단지: 단지 목록 자료로 곧바로 `items`. 기본 정보는 백그라운드(`details.pending`). 그 시·군·구
  실거래를
  받은 적 없으면 **동 선택이 수집을 시작한다**(`trades.state = collecting`). `collected`는 첫 달부터
  잠정 기간 앞 달까지 모두 받았을 때만, 마지막 작업이 실패했고 그 뒤 다 받은 적 없으면 `failed` +
  `failure`
- 평형: 일곱 구분을 늘, 거래 수·첫 달은 해제·사라짐 제외, `startableFrom` = 첫 거래 달 1일과 세법 표
  첫 날
  (2006-01-01) 중 늦은 날. 합쳐진 단지의 옛 id도 같은 결과
"""
from __future__ import annotations

import datetime as dt

import pytest
from httpx2 import ASGITransport, AsyncClient
from sqlalchemy import select

from src.api.main import create_app
from src.api.services import realestate_lists
from src.db.models import AptComplex, AptTrade, JobStatus
from src.db.session import get_session
from src.repository import apt_job
from src.worker import apt_worker
from src.worker.apt_queue import AptWork, get_apt_list_queue, get_apt_trade_queue
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
SETTINGS = apt_settings(apt_trade_probe_start=D("2020-01-01"))  # 2020-01 ~ 2023-10, 46개월


class Api:
    """앱과 가짜 포털. `now`를 바꿔 날짜가 지난 경우를 만든다."""

    def __init__(self, client: AsyncClient, portal: FakePortal, session_factory) -> None:  # type: ignore[no-untyped-def]
        self.http, self.portal, self.session_factory = client, portal, session_factory
        self.now = NOW_UTC
        self.settings = SETTINGS
        self.source = portal_client(portal, SETTINGS)

    async def get(self, path: str, **params: str):  # type: ignore[no-untyped-def]
        return await self.http.get(path, params=params)

    async def run(self, job_id: int, kind: str, target: str) -> JobStatus:
        runner = apt_worker.run_trade_job if kind == "trade" else apt_worker.run_list_job
        status = await runner(self.session_factory, self.source, AptWork(job_id, kind, target),
                              settings=self.settings, now=self.now)
        queue = get_apt_trade_queue() if kind == "trade" else get_apt_list_queue()
        queue.done(kind, target)
        return status

    async def regions_ready(self) -> None:
        first = await self.get("/api/realestate/regions")
        assert first.status_code == 202
        await self.run(first.json()["jobId"], "region", "regions")

    async def garak_ready(self) -> dict[str, object]:
        """행정구역·가락동 단지 목록·기본 정보·송파구 실거래를 모두 받는다."""
        await self.regions_ready()
        body = (await self.get("/api/realestate/complexes", umd=GARAK)).json()
        await self.run(body["trades"]["jobId"], "trade", "11710")
        details = await self._details_job()
        if details is not None:
            await self.run(details, "complex_details", GARAK)
        return (await self.get("/api/realestate/complexes", umd=GARAK)).json()  # type: ignore[no-any-return]

    async def _details_job(self) -> int | None:
        async with self.session_factory() as s:
            return await apt_job.running_job_id(s, "complex_details", GARAK)


@pytest.fixture
async def api(session_factory):  # type: ignore[no-untyped-def]
    portal = FakePortal()
    app = create_app()

    async def _session():  # type: ignore[no-untyped-def]
        async with session_factory() as s:
            yield s

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as http:
        holder = Api(http, portal, session_factory)
        app.dependency_overrides[get_session] = _session
        app.dependency_overrides[realestate_lists.get_realestate_now] = lambda: holder.now
        app.dependency_overrides[realestate_lists.get_realestate_settings] = (
            lambda: holder.settings)
        app.dependency_overrides[realestate_lists.get_realestate_source] = lambda: holder.source
        yield holder


class Test행정구역:
    async def test_처음이면_202와_수집_요청(self, api: Api) -> None:
        first = await api.get("/api/realestate/regions")
        assert first.status_code == 202
        body = first.json()
        assert (body["status"], body["kind"]) == ("collecting", "region")
        assert body["progressUrl"] == f"/api/realestate/progress?jobId={body['jobId']}"
        assert get_apt_list_queue().is_active("region", "regions")
        again = await api.get("/api/realestate/regions")
        assert (again.status_code, again.json()["jobId"]) == (202, body["jobId"])  # 새 작업 없음

    async def test_실패한_뒤의_요청은_새_작업(self, api: Api) -> None:
        first = (await api.get("/api/realestate/regions")).json()
        api.portal.overrides.append(lambda a, q: Response(fixture("gateway_30.xml"), 403))
        assert await api.run(first["jobId"], "region", "regions") is JobStatus.FAILED
        again = await api.get("/api/realestate/regions")
        assert again.status_code == 202 and again.json()["jobId"] != first["jobId"]

    async def test_받은_뒤_세_단계(self, api: Api) -> None:
        await api.regions_ready()
        sido = await api.get("/api/realestate/regions")
        assert sido.status_code == 200
        assert [i["name"] for i in sido.json()["items"]] == [
            "강원특별자치도", "경기도", "서울특별시"]
        assert sido.json()["refreshedAt"] == "2023-10-05T03:00:00Z"
        gyeonggi = (await api.get("/api/realestate/regions", parent="4100000000")).json()
        names = [i["name"] for i in gyeonggi["items"]]
        assert names == sorted(names) and "수원시 장안구" in names and "수원시" not in names
        seoul = (await api.get("/api/realestate/regions", parent="1100000000")).json()["items"]
        songpa = next(i for i in seoul if i["name"] == "송파구")
        assert songpa == {"code": "1171000000", "name": "송파구", "level": "sgg"}
        dongs = (await api.get("/api/realestate/regions", parent="1171000000")).json()["items"]
        assert {"code": GARAK, "name": "가락동", "level": "umd"} in dongs
        assert [i["name"] for i in dongs] == sorted(i["name"] for i in dongs)

    async def test_사라진_코드는_보이지_않는다(self, api: Api) -> None:
        api.portal.old_gangwon = True
        await api.regions_ready()
        assert "강원도" in [i["name"] for i in (await api.get("/api/realestate/regions")).json()[
            "items"]]
        api.portal.old_gangwon = False
        api.now = NOW_UTC + dt.timedelta(days=31)
        stale = await api.get("/api/realestate/regions")  # 30일 지남 — 받아 둔 목록 + 백그라운드
        assert stale.status_code == 200
        async with api.session_factory() as s:
            job_id = await apt_job.running_job_id(s, "region", "regions")
        assert job_id is not None
        await api.run(job_id, "region", "regions")
        names = [i["name"] for i in (await api.get("/api/realestate/regions")).json()["items"]]
        assert "강원도" not in names and "강원특별자치도" in names
        gone = await api.get("/api/realestate/regions", parent="4200000000")
        assert (gone.status_code, gone.json()["status"]) == (400, "unknown_region")

    async def test_30일_갱신이_실패해도_받아_둔_목록(self, api: Api) -> None:
        await api.regions_ready()
        api.now = NOW_UTC + dt.timedelta(days=31)
        await api.get("/api/realestate/regions")
        async with api.session_factory() as s:
            job_id = await apt_job.running_job_id(s, "region", "regions")
        assert job_id is not None
        api.portal.overrides.append(lambda a, q: Response("Service Unavailable", 503))
        await api.run(job_id, "region", "regions")
        again = await api.get("/api/realestate/regions")
        assert again.status_code == 200 and len(again.json()["items"]) == 3

    async def test_모르는_상위_코드(self, api: Api) -> None:
        await api.regions_ready()
        for parent in ("9900000000", "abc"):
            response = await api.get("/api/realestate/regions", parent=parent)
            assert (response.status_code, response.json()["status"]) == (400, "unknown_region")


class Test단지:
    async def test_목록은_곧바로_실거래는_수집_시작(self, api: Api) -> None:
        await api.regions_ready()
        response = await api.get("/api/realestate/complexes", umd=GARAK)
        assert response.status_code == 200
        body = response.json()
        assert body["umd"] == {"code": GARAK, "name": "가락동", "lawdCd": "11710"}
        assert len(body["items"]) == 23
        names = [i["name"] for i in body["items"]]
        assert names == sorted(names)  # 세대수를 아직 모른다 — 이름순
        assert all(i["households"] is None and i["sources"] == ["kapt"] for i in body["items"])
        assert body["details"]["pending"] is True
        assert body["details"]["progressUrl"].startswith("/api/realestate/progress?jobId=")
        trades = body["trades"]
        assert (trades["state"], trades["monthsDone"], trades["monthsTotal"],
                trades["failure"]) == ("collecting", 0, 46, None)
        assert trades["progressUrl"] == f"/api/realestate/progress?jobId={trades['jobId']}"
        assert get_apt_trade_queue().is_active("trade", "11710")
        assert get_apt_list_queue().is_active("complex_details", GARAK)
        again = (await api.get("/api/realestate/complexes", umd=GARAK)).json()
        assert again["trades"]["jobId"] == trades["jobId"]  # 진행 중 — 새 작업 없음
        assert len(api.portal.calls("complex_list")) == 1

    async def test_받은_뒤_실거래_단지가_더해지고_가구수_순(self, api: Api) -> None:
        body = await api.garak_ready()
        items = body["items"]
        assert len(items) == 23 + 56
        assert items[0]["name"] == "헬리오시티아파트"
        helio = items[0]
        assert (helio["jibun"], helio["moveInYear"], helio["households"], helio["sources"]) == (
            "913", 2018, 9510, ["kapt", "trade"])
        known = [i["households"] for i in items if i["households"] is not None]
        assert known == sorted(known, reverse=True)
        assert all(i["households"] is None for i in items[len(known):])  # 모르는 단지는 뒤
        hyunjin = next(i for i in items if i["name"] == "현진타워")
        assert (hyunjin["sources"], hyunjin["households"], hyunjin["jibun"]) == (
            ["trade"], None, "171")
        assert body["details"] == {"pending": False, "progressUrl": None}
        assert body["trades"]["state"] == "collected" and body["trades"]["failure"] is None
        assert len({i["complexId"] for i in items}) == len(items)

    async def test_중간까지만_받고_실패했으면_failed(self, api: Api) -> None:
        await api.regions_ready()
        body = (await api.get("/api/realestate/complexes", umd=GARAK)).json()
        api.portal.overrides.append(
            lambda a, q: Response(fixture("gateway_22.xml"), 429)
            if q.get("DEAL_YMD") == "202107" else None)
        await api.run(body["trades"]["jobId"], "trade", "11710")
        trades = (await api.get("/api/realestate/complexes", umd=GARAK)).json()["trades"]
        assert trades["state"] == "failed"
        assert trades["failure"]["kind"] == "rate_limited"
        assert KEY not in trades["failure"]["reason"]
        assert trades["jobId"] is None

    async def test_단지_목록을_받지_못하면_실거래_단지와_사유(self, api: Api) -> None:
        await api.regions_ready()
        body = (await api.get("/api/realestate/complexes", umd=GARAK)).json()
        await api.run(body["trades"]["jobId"], "trade", "11710")
        api.now = NOW_UTC + dt.timedelta(days=31)  # 동의 단지 목록을 다시 받을 때
        api.portal.overrides.append(
            lambda a, q: Response(fixture("gateway_30.xml"), 403) if a == "complex_list" else None)
        again = (await api.get("/api/realestate/complexes", umd=GARAK)).json()
        assert again["listError"]["kind"] == "auth" and KEY not in again["listError"]["reason"]
        assert len(again["items"]) >= 56  # 받아 둔 단지는 그대로 보인다

    async def test_처음부터_단지_목록을_못_받으면_빈_목록_대신_사유(self, api: Api) -> None:
        await api.regions_ready()
        api.portal.overrides.append(
            lambda a, q: Response(fixture("gateway_30.xml"), 403) if a == "complex_list" else None)
        body = (await api.get("/api/realestate/complexes", umd=GARAK)).json()
        assert body["items"] == [] and body["listError"]["kind"] == "auth"
        assert body["trades"]["state"] == "collecting"

    async def test_합쳐진_단지는_목록에_없다(self, api: Api) -> None:
        body = await api.garak_ready()
        helio_id = body["items"][0]["complexId"]
        async with api.session_factory() as s:
            s.add(AptComplex(umd_code=GARAK, lawd_cd="11710", name="옛 행",
                             merged_into=helio_id))
            await s.commit()
        again = (await api.get("/api/realestate/complexes", umd=GARAK)).json()
        assert "옛 행" not in [i["name"] for i in again["items"]]

    async def test_모르는_동(self, api: Api) -> None:
        await api.regions_ready()
        for umd in ("9999999999", "1171000000", "x"):  # 없는 코드·시·군·구 코드·형식
            response = await api.get("/api/realestate/complexes", umd=umd)
            assert (response.status_code, response.json()["status"]) == (400, "unknown_region")


class Test평형:
    async def test_실거래를_받기_전에는_202(self, api: Api) -> None:
        await api.regions_ready()
        body = (await api.get("/api/realestate/complexes", umd=GARAK)).json()
        helio = next(i for i in body["items"] if i["name"] == "헬리오시티아파트")
        response = await api.get(f"/api/realestate/complexes/{helio['complexId']}/areas")
        assert response.status_code == 202
        assert (response.json()["kind"], response.json()["lawdCd"]) == ("trade", "11710")
        assert response.json()["jobId"] == body["trades"]["jobId"]

    async def test_일곱_구분과_거래_수(self, api: Api) -> None:
        body = await api.garak_ready()
        helio_id = body["items"][0]["complexId"]
        response = await api.get(f"/api/realestate/complexes/{helio_id}/areas")
        assert response.status_code == 200
        areas = response.json()
        assert (areas["complexId"], areas["taxRulesFrom"]) == (helio_id, "2006-01-01")
        got = {b["key"]: b for b in areas["buckets"]}
        assert list(got) == ["10", "20", "30k", "30l", "40", "50", "60"]
        # 2020-01 ~ 2023-09 헬리오시티 558건 중 해제 27건을 뺀 531건
        assert {k: b["trades"] for k, b in got.items()} == {
            "10": 101, "20": 72, "30k": 301, "30l": 27, "40": 30, "50": 0, "60": 0}
        assert got["30k"] == {
            "key": "30k", "label": "30평대(국평)", "minArea": "70", "maxArea": "85",
            "maxInclusive": True, "trades": 301, "firstMonth": "2020-02", "lastMonth": "2023-09",
            "startableFrom": "2020-02-01"}
        assert (got["10"]["minArea"], got["60"]["maxArea"]) == (None, None)
        assert (got["50"]["firstMonth"], got["50"]["startableFrom"]) == (None, None)

    async def test_사라진_거래는_세지_않는다(self, api: Api) -> None:
        body = await api.garak_ready()
        helio_id = body["items"][0]["complexId"]
        async with api.session_factory() as s:
            row = (await s.execute(select(AptTrade).where(
                AptTrade.apt_seq == "11710-8865", AptTrade.cancelled.is_(False)).limit(1))
            ).scalar_one()
            row.missing_since, row.missing_reason = NOW_UTC, "absent"
            await s.commit()
        areas = (await api.get(f"/api/realestate/complexes/{helio_id}/areas")).json()
        assert sum(b["trades"] for b in areas["buckets"]) == 530

    async def test_세법_표보다_이른_첫_거래는_2006_01_01부터(self, api: Api) -> None:
        """장미1(11710-170)의 첫 거래는 2005-12 — 시작 가능 날짜는 세법 표의 첫 날이다(FR-005)."""
        api.settings = apt_settings(apt_trade_probe_start=D("2005-10-01"))
        api.source = portal_client(api.portal, api.settings)
        await api.regions_ready()
        body = (await api.get("/api/realestate/complexes", umd="1171010200")).json()  # 신천동
        await api.run(body["trades"]["jobId"], "trade", "11710")
        items = (await api.get("/api/realestate/complexes", umd="1171010200")).json()["items"]
        jangmi = next(i for i in items if i["name"] == "장미1")
        areas = (await api.get(f"/api/realestate/complexes/{jangmi['complexId']}/areas")).json()
        bucket = next(b for b in areas["buckets"] if b["key"] == "30l")  # 99㎡
        assert (bucket["firstMonth"], bucket["startableFrom"]) == ("2005-12", "2006-01-01")

    async def test_합쳐진_단지의_옛_id도_같은_결과(self, api: Api) -> None:
        body = await api.garak_ready()
        helio_id = body["items"][0]["complexId"]
        async with api.session_factory() as s:
            old = AptComplex(umd_code=GARAK, lawd_cd="11710", name="옛 행", merged_into=helio_id)
            s.add(old)
            await s.commit()
            old_id = old.id
        new = (await api.get(f"/api/realestate/complexes/{helio_id}/areas")).json()
        via_old = (await api.get(f"/api/realestate/complexes/{old_id}/areas")).json()
        assert via_old == new

    async def test_모르는_단지(self, api: Api) -> None:
        response = await api.get("/api/realestate/complexes/987654/areas")
        assert (response.status_code, response.json()["status"]) == (400, "unknown_complex")
