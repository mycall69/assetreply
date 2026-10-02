"""006 목록 테스트 공용 도구 — 손으로 만든 목록 응답, 출처 스텁, 설정.

출처 스텁은 **쪽(`KiwoomPage`) 단위로** 돌려준다. 클라이언트가 실제로 넘기는 모양 그대로라야
교체 서비스가 받는 입력이 운영과 같다. 네트워크를 쓰지 않는다(헌법 원칙 III).
"""
from __future__ import annotations

import asyncio
import datetime as dt
import json
from collections.abc import Sequence

from src.config.settings import Settings, _Secret
from src.ingestion.kiwoom.client import KiwoomPage

#: 기준 시각. 저장 시각은 UTC(시간대 없는 값)다 — 2026-10-02 00:05:12 UTC = 한국 09:05:12.
NOW = dt.datetime(2026, 10, 2, 0, 5, 12)
YESTERDAY_NOW = NOW - dt.timedelta(days=1)
TODAY = dt.date(2026, 10, 2)

APP_KEY = "APPKEY-SENTINEL-1111"
APP_SECRET = "APPSECRET-SENTINEL-2222"


def listing_settings(*, credentials: bool = True) -> Settings:
    return Settings(
        ecos_api_key=_Secret("ecos"),
        kiwoom_app_key=_Secret(APP_KEY if credentials else ""),
        kiwoom_app_secret=_Secret(APP_SECRET if credentials else ""),
    )


def kr_row(code: str, name: str, market_name: str = "거래소",
           reg_day: str = "20000104") -> dict[str, str]:
    """실제 국내 응답의 한 행 모양(research R6-2). 가격·주식수도 실제처럼 싣는다."""
    return {
        "code": code, "name": name, "listCount": "0000000010000000", "auditInfo": "정상",
        "regDay": reg_day, "lastPrice": "00010000", "state": "증거금40%",
        "marketCode": "0", "marketName": market_name, "upName": "", "upSizeName": "",
        "companyClassName": "", "orderWarning": "0", "nxtEnable": "N", "kind": "A",
    }


def kr_body(rows: Sequence[dict[str, str]]) -> str:
    return json.dumps({"return_msg": "정상적으로 처리되었습니다", "list": list(rows),
                       "return_code": 0}, ensure_ascii=False)


def page(body: str, page_no: int = 1, *, cont_yn: str = "N") -> KiwoomPage:
    return KiwoomPage(page_no=page_no, status=200, body=body, cont_yn=cont_yn,
                      next_key="")


#: 삼성전자 등 실제 코드로 만든 작은 KOSPI 목록.
SAMSUNG = kr_row("005930", "삼성전자", reg_day="19750611")
SAMSUNG_PREF = kr_row("005935", "삼성전자우", reg_day="19890925")
KODEX200 = kr_row("069500", "KODEX 200", "ETF", "20021014")
DAESIN_REIT = kr_row("0030R0", "대신밸류리츠", "리츠", "20250710")
KOSPI_ROWS = [SAMSUNG, SAMSUNG_PREF, KODEX200, DAESIN_REIT]

ECOPRO = kr_row("247540", "에코프로비엠", "코스닥", "20190305")
KOSDAQ_ROWS = [ECOPRO]


Response = list[KiwoomPage] | Exception


class StubListingSource:
    """`ListingSource` 스텁. 단위마다 응답을 차례로 꺼낸다."""

    def __init__(self, responses: dict[str, list[Response]] | None = None) -> None:
        self._responses: dict[str, list[Response]] = {
            k: list(v) for k, v in (responses or {}).items()}
        self.calls: list[str] = []
        #: 설정하면 그 이벤트가 열릴 때까지 응답을 미룬다(동시 갱신 시험용).
        self.gate: asyncio.Event | None = None
        self.entered = asyncio.Event()

    def add(self, unit: str, response: Response) -> None:
        self._responses.setdefault(unit, []).append(response)

    async def fetch_unit(self, unit: str) -> list[KiwoomPage]:
        self.calls.append(unit)
        self.entered.set()
        if self.gate is not None:
            await self.gate.wait()
        queue = self._responses.get(unit) or []
        if not queue:
            raise AssertionError(f"스텁에 {unit} 응답이 없습니다")
        response = queue.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


async def seed(session_factory, unit: str, rows: Sequence[dict[str, str]], *,  # type: ignore[no-untyped-def]
               now: dt.datetime = NOW, settings: Settings | None = None):
    """목록을 **교체 서비스로** 넣는다. 테이블에 직접 넣으면 교체 규칙이 가려진다."""
    from src.api.services.listing_refresh import AuthBlocker, refresh_unit

    source = StubListingSource({unit: [[page(kr_body(rows))]]})
    return await refresh_unit(
        session_factory, source, unit, settings=settings or listing_settings(),
        now=lambda: now, blocker=AuthBlocker())


def reset_listing_state() -> None:
    """검색 색인·인증 실패 막힘·목록 갱신 큐를 비운다.

    셋 다 프로세스 메모리에 산다. 테스트마다 스키마를 새로 만들어도 남으며, 특히 색인은 **목록
    기준 시각**을 버전으로 삼으므로 같은 고정 시각을 쓰는 앞 테스트의 색인이 뒤 테스트의 다른
    데이터에 그대로 쓰인다. 목록을 다루는 테스트 모듈은 이것을 autouse 픽스처로 부른다.
    """
    from src.api.services.listing_index import reset_listing_index
    from src.api.services.listing_refresh import get_auth_blocker
    from src.worker.listing_queue import reset_listing_queue

    reset_listing_index()
    get_auth_blocker().reset()
    reset_listing_queue()
