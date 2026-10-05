"""시뮬레이션 API (T033) — 009 FR-002, FR-005~FR-007, FR-010, FR-011, FR-014, FR-018, FR-023,
FR-025~FR-030, SC-006, SC-008, contracts/rest-api `GET /api/realestate/simulation`.

- **받아 둔 시·군·구**가 아니면 202 — 받지 않은 달, 최근 3개월을 오늘 확인 전, 4~12개월 전 달을 이번
  달 확인
  전이면 202(같은 시·군·구 작업이 진행 중이면 그 `jobId`). 받아 둔 시·군·구에서 오늘의 실패가 잠정
  다시 받기뿐이면 200 + `summary.recheckFailed`(같은 날 202를 되풀이하지 않는다). 받지 않은 확정
  달이 있으면 실패가 있었어도 202다 — 부분 결과는 없다
- 200은 계산 모듈(`simulate_holding`)의 결과를 계약 모양으로 — 금액은 원 정수 문자열, 수익률은 소수
  6자리, 세금은
  납부 달 행에만(다른 달은 `null`). 해제 거래는 그 달 건수·평균에 없다(SC-006)
- 실행 날짜 2023-10-05(한국 시간) — 픽스처는 송파구 2020-01~2023-09(`apt_support`)
"""
from __future__ import annotations

import dataclasses
import datetime as dt
import gzip
from decimal import Decimal

import pytest
from httpx2 import ASGITransport, AsyncClient
from sqlalchemy import select

from src.api.main import create_app
from src.api.services import realestate_lists
from src.db.models import AptComplex, JobStatus
from src.db.session import get_session
from src.ingestion.datagokr.trade_parse import number_trades, parse_trades
from src.repository import apt_job
from src.simulation.apt_area import bucket_by_key
from src.simulation.apt_holding import simulate_holding
from src.simulation.apt_price import Trade, aggregate
from src.simulation.apt_tax_rules import RuleNotCovered
from src.worker import apt_worker
from src.worker.apt_queue import AptWork, get_apt_list_queue, get_apt_trade_queue
from tests.integration.apt_support import (
    FIXTURES,
    NOW_UTC,
    TODAY,
    FakePortal,
    Response,
    apt_settings,
    fixture,
    portal_client,
)

D = dt.date.fromisoformat
GARAK = "1171010700"
SETTINGS = apt_settings(apt_trade_probe_start=D("2020-01-01"))


def at(day: str) -> dt.datetime:
    return dt.datetime.combine(D(day), dt.time(3, 0))


class Api:
    def __init__(self, http: AsyncClient, portal: FakePortal, session_factory) -> None:  # type: ignore[no-untyped-def]
        self.http, self.portal, self.session_factory = http, portal, session_factory
        self.now, self.settings = NOW_UTC, SETTINGS
        self.source = portal_client(portal, SETTINGS)

    async def get(self, path: str, **params: str):  # type: ignore[no-untyped-def]
        return await self.http.get(path, params=params)

    async def simulate(self, **params: str):  # type: ignore[no-untyped-def]
        return await self.get("/api/realestate/simulation", **params)

    async def run(self, job_id: int, kind: str, target: str) -> JobStatus:
        runner = apt_worker.run_trade_job if kind == "trade" else apt_worker.run_list_job
        status = await runner(self.session_factory, self.source, AptWork(job_id, kind, target),
                              settings=self.settings, now=self.now)
        (get_apt_trade_queue() if kind == "trade" else get_apt_list_queue()).done(kind, target)
        return status

    async def running(self, kind: str, target: str) -> int | None:
        async with self.session_factory() as s:
            return await apt_job.running_job_id(s, kind, target)

    async def regions(self) -> None:
        first = await self.get("/api/realestate/regions")
        await self.run(first.json()["jobId"], "region", "regions")

    async def complexes(self, umd: str = GARAK) -> dict[str, object]:
        body = (await self.get("/api/realestate/complexes", umd=umd)).json()
        return body  # type: ignore[no-any-return]

    async def collected(self, umd: str = GARAK) -> dict[str, int]:
        """행정구역·그 동 단지·송파구 실거래를 받고 이름 → 단지 id."""
        await self.regions()
        body = await self.complexes(umd)
        await self.run(body["trades"]["jobId"], "trade", "11710")  # type: ignore[index]
        details = await self.running("complex_details", umd)
        if details is not None:
            await self.run(details, "complex_details", umd)
        items = (await self.complexes(umd))["items"]
        return {i["name"]: i["complexId"] for i in items}  # type: ignore[union-attr,index]


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


def helio_monthly(area: str):  # type: ignore[no-untyped-def]
    """같은 원본을 계산 모듈로 — API가 이 결과를 계약 모양으로만 바꾸는지 본다."""
    trades = []
    for path in sorted(FIXTURES.glob("trade_11710_20*_p1.xml.gz")):
        ym = path.name.split("_")[2]
        rows = []
        for page in sorted(FIXTURES.glob(f"trade_11710_{ym}_p*.xml.gz")):
            rows.extend(parse_trades(gzip.decompress(page.read_bytes()).decode("utf-8"),
                                     lawd_cd="11710", ym=ym).rows)
        bucket = bucket_by_key(area)
        trades.extend(Trade(t.deal_date, t.amount, cancelled=t.cancelled)
                      for t in number_trades(rows)
                      if t.apt_seq == "11710-8865" and bucket.contains(t.excl_area))
    return aggregate(trades)


class Test수집_대기:
    async def test_받은_적_없으면_202와_수집_요청(self, api: Api) -> None:
        await api.regions()
        body = await api.complexes()
        names = {i["name"]: i["complexId"] for i in body["items"]}  # type: ignore[union-attr,index]
        params = {"complexId": str(names["헬리오시티아파트"]), "area": "30k",
                  "buyDate": "2021-03-15"}
        first = await api.simulate(**params)
        assert first.status_code == 202
        got = first.json()
        assert (got["status"], got["kind"], got["lawdCd"]) == ("collecting", "trade", "11710")
        assert (got["monthsDone"], got["monthsTotal"]) == (0, 46)
        assert got["progressUrl"] == f"/api/realestate/progress?jobId={got['jobId']}"
        again = await api.simulate(**params)
        assert (again.status_code, again.json()["jobId"]) == (202, got["jobId"])
        assert get_apt_trade_queue().is_active("trade", "11710")

    async def test_받은_뒤_200_다음_날은_최근_3개월_확인_전_202(self, api: Api) -> None:
        names = await api.collected()
        params = {"complexId": str(names["헬리오시티아파트"]), "area": "30k",
                  "buyDate": "2021-03-15"}
        assert (await api.simulate(**params)).status_code == 200
        api.now = at("2023-10-20")
        waiting = await api.simulate(**params)
        assert waiting.status_code == 202
        await api.run(waiting.json()["jobId"], "trade", "11710")
        assert (await api.simulate(**params)).status_code == 200  # 4~12개월 달은 이번 달에 확인했다

    async def test_새_달의_첫_요청은_4_12개월_확인_전이라_202(self, api: Api) -> None:
        names = await api.collected()
        params = {"complexId": str(names["헬리오시티아파트"]), "area": "30k",
                  "buyDate": "2021-03-15"}
        api.now = at("2023-11-02")
        waiting = await api.simulate(**params)
        assert waiting.status_code == 202
        assert waiting.json()["monthsTotal"] == 13  # 2022-11 ~ 2023-11

    async def test_받아_둔_시군구의_잠정_확인만_실패하면_200과_recheckFailed(
            self, api: Api) -> None:
        names = await api.collected()
        params = {"complexId": str(names["헬리오시티아파트"]), "area": "30k",
                  "buyDate": "2021-03-15"}
        api.now = at("2023-10-06")
        waiting = await api.simulate(**params)
        api.portal.overrides.append(lambda a, q: Response(fixture("gateway_30.xml"), 403))
        await api.run(waiting.json()["jobId"], "trade", "11710")
        done = await api.simulate(**params)
        assert done.status_code == 200
        failed = done.json()["summary"]["recheckFailed"]
        assert failed["kind"] == "auth" and "인증" in failed["reason"]
        assert await api.running("trade", "11710") is None  # 같은 날 202를 되풀이하지 않는다

    async def test_받지_않은_확정_달이_있으면_실패해도_202(self, api: Api) -> None:
        await api.regions()
        body = await api.complexes()
        names = {i["name"]: i["complexId"] for i in body["items"]}  # type: ignore[union-attr,index]
        api.portal.overrides.append(
            lambda a, q: Response(fixture("gateway_22.xml"), 429)
            if q.get("DEAL_YMD") == "202107" else None)
        await api.run(body["trades"]["jobId"], "trade", "11710")  # type: ignore[index]
        params = {"complexId": str(names["헬리오시티아파트"]), "area": "30k",
                  "buyDate": "2021-03-15"}
        again = await api.simulate(**params)
        assert again.status_code == 202  # 부분 결과는 없다 — 새 작업이 이어 받는다


class Test결과:
    async def test_계산_모듈의_결과를_계약_모양으로(self, api: Api) -> None:
        names = await api.collected()
        helio = names["헬리오시티아파트"]
        response = await api.simulate(complexId=str(helio), area="30k", buyDate="2021-03-15")
        assert response.status_code == 200
        body = response.json()
        expected = simulate_holding(
            helio_monthly("30k"), buy_date=D("2021-03-15"), buy_price=None,
            area=bucket_by_key("30k"), today=TODAY, holding_tax_base_ratio=Decimal("0.6"),
            provisional_months=12)
        assert body["complex"] == {"complexId": helio, "name": "헬리오시티아파트",
                                   "umdName": "가락동"}
        assert body["area"] == {"key": "30k", "label": "30평대(국평)"}
        condition = body["condition"]
        assert (condition["buyDate"], condition["buyPrice"], condition["buyPriceSource"]) == (
            "2021-03-15", str(expected.buy_price), "market")
        assert condition["buyPriceWindow"] == {
            "months": expected.buy_price_window.window,  # type: ignore[union-attr]
            "trades": expected.buy_price_window.trades,  # type: ignore[union-attr]
            "estimated": expected.buy_price_window.estimated}  # type: ignore[union-attr]
        assert condition["holdingTaxBaseRatio"] == "0.600000"
        assert condition["assumptions"] == [
            "부부 5:5 공동 소유", "1세대 1주택", "세법: 시행일별 표"]
        acquisition = expected.acquisition
        assert body["acquisition"] == {
            "acquisitionTax": str(acquisition.acquisition_tax),
            "educationTax": str(acquisition.education_tax),
            "ruralTax": str(acquisition.rural_tax), "brokerageFee": str(acquisition.brokerage_fee),
            "total": str(acquisition.total),
            "rules": {"acquisition": acquisition.acquisition_rule_from.isoformat(),
                      "brokerage": acquisition.brokerage_rule_from.isoformat()}}
        summary = body["summary"]
        assert (summary["buyPrice"], summary["invested"], summary["asOf"]) == (
            str(expected.buy_price), str(expected.invested), "2023-10-05")
        assert summary["profit"] == str(expected.summary.profit)
        assert summary["returnRate"] == f"{expected.summary.return_rate:.6f}"
        assert summary["holdingTaxTotal"] == str(expected.summary.holding_tax_total)
        assert (summary["taxGaps"], summary["valueMonth"]) == ([], "2023-10")
        assert summary["provisionalFrom"] == "2022-11-01"  # 잠정 12개월(설정)의 첫 달
        assert "recheckFailed" not in summary
        rows = body["rows"]
        assert [r["month"] for r in rows] == [f"{r.month:%Y-%m}" for r in expected.rows]
        assert rows[0]["month"] == "2023-10" and rows[-1]["month"] == "2021-03"  # 최신순
        for row, want in zip(rows, expected.rows, strict=True):
            assert row["value"] == (None if want.value is None else str(want.value))
            assert row["cumulativeCost"] == str(want.cumulative_cost)
            for name, tax in (("propertyTax", want.property_tax),
                              ("comprehensiveTax", want.comprehensive_tax)):
                if tax is None:
                    assert row[name] is None, (row["month"], name)
                    continue
                assert (row[name]["amount"], row[name]["installment"], row[name]["rule"]) == (
                    str(tax.amount), tax.installment, tax.rule_date.isoformat())
                assert row[name]["basis"] == {
                    "month": f"{tax.basis.month:%Y-%m}", "price": str(tax.basis.price),
                    "window": tax.basis.window, "windowTrades": tax.basis.trades,
                    "estimated": tax.basis.estimated, "provisional": tax.basis.provisional}
            if row["profit"] is not None:
                assert int(row["profit"]) == (int(row["value"]) - expected.buy_price
                                              - int(row["cumulativeCost"]))
                assert len(row["returnRate"].split(".")[1]) == 6

    async def test_해제_거래는_그_달_건수와_평균에_없다(self, api: Api) -> None:
        """2021-08 30평대(국평) — 해제를 빼면 3건, 평균 2,093,333,333(T029의 손계산)."""
        names = await api.collected()
        body = (await api.simulate(complexId=str(names["헬리오시티아파트"]), area="30k",
                                   buyDate="2021-03-15")).json()
        august = next(r for r in body["rows"] if r["month"] == "2021-08")
        assert (august["trades"], august["monthAverage"]) == (3, "2093333333")
        assert (august["price"], august["window"], august["windowTrades"],
                august["estimated"]) == ("2093333333", 1, 3, False)

    async def test_세금은_납부_달_행에만(self, api: Api) -> None:
        names = await api.collected()
        body = (await api.simulate(complexId=str(names["헬리오시티아파트"]), area="30k",
                                   buyDate="2021-03-15")).json()
        rows = {r["month"]: r for r in body["rows"]}
        assert rows["2021-03"]["acquisition"] == body["acquisition"]
        assert all(r["acquisition"] is None for m, r in rows.items() if m != "2021-03")
        property_months = sorted(m for m, r in rows.items() if r["propertyTax"] is not None)
        assert property_months == ["2021-07", "2021-09", "2022-07", "2022-09", "2023-07",
                                   "2023-09"]
        assert [rows[m]["propertyTax"]["installment"] for m in ("2021-07", "2021-09")] == [
            "1/2", "2/2"]
        assert rows["2021-07"]["propertyTax"]["basis"]["month"] == "2021-06"
        comprehensive = sorted(m for m, r in rows.items() if r["comprehensiveTax"] is not None)
        assert comprehensive == ["2021-12", "2022-12"]  # 2023-12는 아직 오지 않았다
        assert all(r["comprehensiveTax"] is None for m, r in rows.items()
                   if not m.endswith("-12"))

    async def test_6월_시세가_추정이면_세금의_기준_시세가_추정(self, api: Api) -> None:
        """10평대는 2022-06에 거래가 없다 — 그해 재산세의 기준 시세는 넓은 창의 추정이다."""
        names = await api.collected()
        body = (await api.simulate(complexId=str(names["헬리오시티아파트"]), area="10",
                                   buyDate="2021-03-15")).json()
        rows = {r["month"]: r for r in body["rows"]}
        assert rows["2022-07"]["propertyTax"]["basis"]["estimated"] is True
        assert rows["2021-07"]["propertyTax"]["basis"]["estimated"] is False

    async def test_매입가를_넣으면_그_금액으로(self, api: Api) -> None:
        names = await api.collected()
        body = (await api.simulate(complexId=str(names["헬리오시티아파트"]), area="30k",
                                   buyDate="2021-03-15", buyPrice="2000000000")).json()
        assert (body["condition"]["buyPrice"], body["condition"]["buyPriceSource"],
                body["condition"]["buyPriceWindow"]) == ("2000000000", "input", None)

    async def test_같은_요청은_같은_응답(self, api: Api) -> None:
        names = await api.collected()
        params = {"complexId": str(names["헬리오시티아파트"]), "area": "30k",
                  "buyDate": "2021-03-15"}
        first, second = await api.simulate(**params), await api.simulate(**params)
        assert first.status_code == 200 and first.json() == second.json()

    async def test_합쳐진_단지의_옛_id도_같은_결과(self, api: Api) -> None:
        names = await api.collected()
        helio = names["헬리오시티아파트"]
        async with api.session_factory() as s:
            old = AptComplex(umd_code=GARAK, lawd_cd="11710", name="옛 행", merged_into=helio)
            s.add(old)
            await s.commit()
            old_id = old.id
        params = {"area": "30k", "buyDate": "2021-03-15"}
        new = await api.simulate(complexId=str(helio), **params)
        via_old = await api.simulate(complexId=str(old_id), **params)
        assert new.status_code == 200 and via_old.json() == new.json()


class Test거절:
    async def test_시작_가능_날짜보다_이르면_409와_근거(self, api: Api) -> None:
        names = await api.collected()
        response = await api.simulate(complexId=str(names["헬리오시티아파트"]), area="30k",
                                      buyDate="2020-01-15")
        assert response.status_code == 409
        assert (response.json()["status"], response.json()["startableFrom"],
                response.json()["basis"]) == ("before_first_trade", "2020-02-01", "first_trade")

    async def test_2005_12_첫_거래는_세법_표_근거로_2006_01_01(self, api: Api) -> None:
        api.settings = apt_settings(apt_trade_probe_start=D("2005-10-01"))
        api.source = portal_client(api.portal, api.settings)
        names = await api.collected("1171010200")  # 신천동 — 장미1(11710-170)
        response = await api.simulate(complexId=str(names["장미1"]), area="30l",
                                      buyDate="2005-12-26")
        assert (response.status_code, response.json()["startableFrom"],
                response.json()["basis"]) == (409, "2006-01-01", "tax_rules")
        no_price = await api.simulate(complexId=str(names["장미1"]), area="30l",
                                      buyDate="2010-01-01")  # 36개월 안에 거래가 없다
        assert (no_price.status_code, no_price.json()["status"], no_price.json()["month"]) == (
            409, "no_price_at_purchase", "2010-01")

    async def test_그_평형_거래가_없다(self, api: Api) -> None:
        names = await api.collected()
        response = await api.simulate(complexId=str(names["헬리오시티아파트"]), area="50",
                                      buyDate="2021-03-15")
        assert (response.status_code, response.json()["status"]) == (409, "no_trades_in_area")

    async def test_세법_표가_덮지_않는_해(self, api: Api, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        names = await api.collected()

        def not_covered(year: int, base_price: int):  # type: ignore[no-untyped-def]
            raise RuleNotCovered("property", dt.date(year, 6, 1))

        monkeypatch.setattr("src.simulation.apt_holding.property_tax", not_covered)
        response = await api.simulate(complexId=str(names["헬리오시티아파트"]), area="30k",
                                      buyDate="2021-03-15")
        assert response.status_code == 409
        assert (response.json()["status"], response.json()["tax"], response.json()["date"]) == (
            "tax_rule_not_covered", "property", "2021-06-01")

    @pytest.mark.parametrize(("params", "status"), [
        ({"principalCurrency": "USD"}, "currency_not_allowed"),
        ({"buyDate": "2023-10-06"}, "start_after_end"),
        ({"buyPrice": "0"}, "invalid_query"), ({"buyPrice": "-1"}, "invalid_query"),
        ({"buyPrice": "1,000,000"}, "invalid_query"), ({"buyPrice": "abc"}, "invalid_query"),
        ({"area": "99"}, "invalid_query"), ({"buyDate": "2021-13-01"}, "invalid_query"),
    ])
    async def test_입력_거절(self, api: Api, params: dict[str, str], status: str) -> None:
        names = await api.collected()
        query = {"complexId": str(names["헬리오시티아파트"]), "area": "30k",
                 "buyDate": "2021-03-15", **params}
        response = await api.simulate(**query)
        assert (response.status_code, response.json()["status"]) == (400, status)
        if status == "currency_not_allowed":
            assert response.json()["allowed"] == ["KRW"]
        if status == "start_after_end":
            assert response.json()["lastDay"] == "2023-10-05"

    async def test_모르는_단지(self, api: Api) -> None:
        response = await api.simulate(complexId="987654", area="30k", buyDate="2021-03-15")
        assert (response.status_code, response.json()["status"]) == (400, "unknown_complex")

    async def test_사라진_시군구에_남은_단지는_409_새_코드로_받으면_같은_id로_200(  # type: ignore[no-untyped-def]
            self, api: Api) -> None:
        """옛 강원도(42110)로 남은 단지 — 같은 `aptSeq`의 거래를 새 코드(51110)로 받으면
        이어진다."""
        api.portal.old_gangwon = True
        await api.regions()
        page = fixture("trade_51110_202001_p1.xml.gz")
        seq = page.split("<aptSeq>")[1].split("</aptSeq>")[0]
        area = page.split("<excluUseAr>")[1].split("</excluUseAr>")[0]
        async with api.session_factory() as s:
            row = AptComplex(umd_code="4211010100", lawd_cd="42110", apt_seq=seq, name="옛")
            s.add(row)
            await s.commit()
            complex_id = row.id
        api.portal.old_gangwon = False
        api.now = at("2023-11-06")
        await api.run(await _job(api, "region", "regions"), "region", "regions")
        key = bucket_key(area)
        params = {"complexId": str(complex_id), "area": key, "buyDate": "2020-01-15"}
        retired = await api.simulate(**params)
        assert (retired.status_code, retired.json()["status"], retired.json()["lawdCd"]) == (
            409, "region_retired", "42110")
        areas = await api.get(f"/api/realestate/complexes/{complex_id}/areas")
        assert areas.status_code == 409
        api.settings = dataclasses.replace(api.settings,
                                           apt_trade_probe_start=D("2020-01-01"))
        await api.run(await _job(api, "trade", "51110"), "trade", "51110")
        async with api.session_factory() as s:
            moved = (await s.execute(select(AptComplex).where(AptComplex.id == complex_id))
                     ).scalar_one()
        assert moved.lawd_cd == "51110"
        reopened = await api.simulate(**params)
        assert reopened.status_code == 200


def bucket_key(area: str) -> str:
    from src.simulation.apt_area import area_bucket

    return area_bucket(Decimal(area)).key


async def _job(api: Api, kind: str, target: str) -> int:
    async with api.session_factory() as s:
        job_id, _ = await apt_job.acquire_or_get_running(s, kind, target, total=0)
        await s.commit()
    return job_id
