"""부동산 통합 테스트 공용 — 가짜 공공데이터포털과 실행 날짜(009).

**실제 클라이언트(`DataGoKrClient`)와 관문을 그대로 쓰고 세션만 바꾼다.** 가짜 세션은 요청 URL의
질의를 읽어 T001의 실제 응답 픽스처를 돌려준다(헌법 원칙 III — 네트워크 없이). 키 지우기·실패
종류·재시도·하루 한도가 실제 경로로 돈다.

- 실거래: 픽스처가 있는 달(송파구 2005-11·12, 2020-01~2023-09, 춘천)은 그 본문, 없는 달은 거래
  없음(`000` +
  0건 — 출처가 실제로 그렇게 답한다)
- 법정동코드: 서울·수원·춘천 픽스처를 이은 **전국 한 쪽**(672행). 옛 강원도 코드(42…)를 춘천에서
  만들어
  넣을 수 있다 — 개편 뒤 갱신에서 사라지는 경우
- 단지 목록·기본 정보: 가락동 픽스처, 없는 동·코드는 빈 결과

실행 날짜는 **2023-10-05(한국 시간)**로 고정한다 — 픽스처 끝(2023-09)이 잠정 기간(최근 12개월 —
2022-11~2023-10) 안에 든다.
"""
from __future__ import annotations

import dataclasses
import datetime as dt
import gzip
import json
import urllib.parse
from collections.abc import Callable
from pathlib import Path
from typing import Self

from src.config.settings import Settings, _Secret, load_settings
from src.ingestion.datagokr.client import DataGoKrClient
from src.ingestion.datagokr.gate import DataGoKrGate, UsageCounter

FIXTURES = Path(__file__).resolve().parents[1] / "contract" / "fixtures" / "apt"
D = dt.date.fromisoformat

TODAY = D("2023-10-05")
NOW_UTC = dt.datetime(2023, 10, 5, 3, 0, 0)  # 한국 시간 12:00
#: 64자 영숫자 — 실패 사유·원본에 남지 않아야 한다.
KEY = "abcdefABCDEF0123456789abcdefABCDEF0123456789abcdefABCDEF01234567"
EMPTY_TRADES = ('<?xml version="1.0" encoding="utf-8" standalone="yes"?><response><header>'
                '<resultCode>000</resultCode><resultMsg>OK</resultMsg></header><body><items/>'
                '<numOfRows>1000</numOfRows><pageNo>{page}</pageNo><totalCount>0</totalCount>'
                '</body></response>')
NO_REGION = '{"RESULT":{"resultCode":"INFO-3","resultMsg":"데이터없음 에러"}}'


def fixture(name: str) -> str:
    path = FIXTURES / name
    raw = path.read_bytes()
    return (gzip.decompress(raw) if path.suffix == ".gz" else raw).decode("utf-8")


def trade_fixture(lawd_cd: str, ym: str, page: int) -> str | None:
    for suffix in (".xml", ".xml.gz"):
        path = FIXTURES / f"trade_{lawd_cd}_{ym}_p{page}{suffix}"
        if path.exists():
            return fixture(path.name)
    return None


def region_rows(*, old_gangwon: bool = False) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for name in ("region_seoul.json", "region_suwon.json", "region_chuncheon.json"):
        rows.extend(json.loads(fixture(name))["StanReginCd"][1]["row"])
    # 수원·춘천 픽스처는 시 아래만 받았다 — 시·도 행을 더한다(전국 목록에는 있다).
    for code, name in (("41", "경기도"), ("51", "강원특별자치도")):
        rows.append({"region_cd": f"{code}00000000", "sido_cd": code, "sgg_cd": "000",
                     "umd_cd": "000", "ri_cd": "00", "locatadd_nm": name,
                     "locathigh_cd": "0000000000", "locallow_nm": name})
    if old_gangwon:
        for row in json.loads(fixture("region_chuncheon.json"))["StanReginCd"][1]["row"]:
            old = dict(row)
            for key in ("region_cd", "locathigh_cd"):
                old[key] = "42" + str(row[key])[2:]
            old["sido_cd"] = "42"
            old["locatadd_nm"] = str(row["locatadd_nm"]).replace("강원특별자치도", "강원도")
            rows.append(old)
        rows.append({"region_cd": "4200000000", "sido_cd": "42", "sgg_cd": "000",
                     "umd_cd": "000", "ri_cd": "00", "locatadd_nm": "강원도",
                     "locathigh_cd": "0000000000", "locallow_nm": "강원도"})
    return rows


def region_body(rows: list[dict[str, object]]) -> str:
    return json.dumps({"StanReginCd": [
        {"head": [{"totalCount": len(rows)}, {"numOfRows": "1000", "pageNo": "1", "type": "JSON"},
                  {"RESULT": {"resultCode": "INFO-0", "resultMsg": "NOMAL SERVICE"}}]},
        {"row": rows}]}, ensure_ascii=False)


class Response:
    def __init__(self, body: str, status: int = 200) -> None:
        self._body, self.status = body, status

    async def text(self) -> str:
        return self._body

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *exc: object) -> None:
        return None


#: 요청을 가로채는 함수 — (자료, 질의) → 응답 또는 None(기본 응답).
Override = Callable[[str, dict[str, str]], "Response | Exception | None"]


class FakePortal:
    """`aiohttp.ClientSession` 대신. 요청 URL을 기록하고 자료별로 픽스처를 돌려준다."""

    def __init__(self, *, old_gangwon: bool = False) -> None:
        self.urls: list[str] = []
        self.overrides: list[Override] = []
        self.old_gangwon = old_gangwon
        #: 실거래 본문을 바꾸는 함수 — (시군구, 년월, 쪽, 본문) → 본문. 다시 받기의 변화를 만든다.
        self.edit_trades: Callable[[str, str, int, str], str] | None = None

    def calls(self, api: str) -> list[dict[str, str]]:
        return [q for a, q in map(_split, self.urls) if a == api]

    def get(self, url: object, **_: object) -> Response:
        text = str(url)
        self.urls.append(text)
        api, query = _split(text)
        for override in self.overrides:
            found = override(api, query)
            if isinstance(found, Exception):
                raise found
            if found is not None:
                return found
        return self._default(api, query)

    def _default(self, api: str, query: dict[str, str]) -> Response:
        if api == "trade":
            lawd, ym, page = query["LAWD_CD"], query["DEAL_YMD"], int(query["pageNo"])
            body = trade_fixture(lawd, ym, page) or EMPTY_TRADES.format(page=page)
            if self.edit_trades is not None:
                body = self.edit_trades(lawd, ym, page, body)
            return Response(body)
        if api == "region":
            return Response(region_body(region_rows(old_gangwon=self.old_gangwon)))
        if api == "complex_list":
            if query["bjdCode"] == "1171010700":
                return Response(fixture("kapt_list_1171010700.json"))
            return Response(fixture("kapt_list_empty.json"))
        if api == "complex_basis":
            path = FIXTURES / f"kapt_basis_{query['kaptCode']}.json"
            return Response(fixture(path.name if path.exists() else "kapt_basis_unknown.json"))
        raise AssertionError(f"모르는 요청: {api}")

    async def close(self) -> None:
        return None


def _split(url: str) -> tuple[str, dict[str, str]]:
    parsed = urllib.parse.urlsplit(url)
    query = dict(urllib.parse.parse_qsl(parsed.query))
    path = parsed.path
    if "RTMSDataSvcAptTradeDev" in path:
        return "trade", query
    if "StanReginCd" in path:
        return "region", query
    if "AptListService4" in path:
        return "complex_list", query
    if "AptBasisInfoServiceV5" in path:
        return "complex_basis", query
    return path, query


class AlwaysCounter:
    async def take(self, api: str, day: dt.date, limit: int) -> bool:
        return True


def apt_settings(**changes: object) -> Settings:
    base = dataclasses.replace(
        load_settings(), data_api_key=_Secret(KEY), data_api_retry_max_attempts=2,
        data_api_retry_base_delay_ms=1, apt_trade_probe_start=D("2005-10-01"),
        apt_trade_provisional_months=12, apt_trade_daily_recheck_months=3,
        apt_list_refresh_days=30)
    return dataclasses.replace(base, **changes)  # type: ignore[arg-type]


def portal_client(portal: FakePortal, settings: Settings | None = None, *,
                  counter: UsageCounter | None = None,
                  limits: dict[str, int] | None = None,
                  today: dt.date = TODAY) -> DataGoKrClient:
    """가짜 포털로 보내는 실제 클라이언트. 관문은 부른 이벤트 루프에서 만든다. `today`는 하루 호출
    수를 세는 날(한국 시간)이다."""
    settings = settings or apt_settings()
    gate = DataGoKrGate(3, counter or AlwaysCounter(),
                        limits or {"trade": 9000, "region": 9000, "kapt": 4500},
                        today=lambda: today)
    return DataGoKrClient(settings, gate, session=portal)  # type: ignore[arg-type]


def months(first: str, last: str) -> list[str]:
    """`YYYYMM` 두 달 사이(양끝 포함)."""
    year, month = int(first[:4]), int(first[4:])
    out = []
    while f"{year:04d}{month:02d}" <= last:
        out.append(f"{year:04d}{month:02d}")
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    return out
