"""키움 REST API 클라이언트 계약 (T009) — 006 research R6-1·R6-3, FR-013b, FR-060, FR-061.

**네트워크를 쓰지 않는다**(헌법 원칙 III). 세션을 흉내 내고, 응답은 T005에서 받은 실제 응답
(`fixtures/kiwoom/`)을 쓴다. 토큰 발급 성공 응답만 가짜다 — 진짜를 저장하면 토큰이 남는다.

**HTTP 200인 실패**가 이 어댑터의 가장 큰 함정이다. 실제 오류 응답은 HTTP 200에
`return_code: 3`이고 세부 코드는 `return_msg`의 `[8001:…]`에만 있다. 상태 코드만 보면 실패를
빈 목록으로 읽어 전 종목을 "목록에서 빠짐"으로 바꾼다.
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Self

import aiohttp
import pytest

from src.config.settings import Settings, _Secret
from src.ingestion.kiwoom.client import KiwoomClient
from src.ingestion.kiwoom.errors import (
    KiwoomAuthError,
    KiwoomInvalidResponse,
    KiwoomRateLimited,
    KiwoomUnavailable,
)

FIXTURES = Path(__file__).parent / "fixtures" / "kiwoom"
KST = dt.timezone(dt.timedelta(hours=9))
NOW = dt.datetime(2026, 10, 2, 3, 0, tzinfo=dt.UTC)  # KST 12:00

TOKEN_OK = json.dumps({"return_code": 0, "return_msg": "정상", "token": "FAKE-TOKEN-0001",
                       "token_type": "bearer", "expires_dt": "20261003120000"})


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


class Resp:
    def __init__(self, body: str, status: int = 200, headers: dict[str, str] | None = None) -> None:
        self._body = body
        self.status = status
        self.headers = headers or {}

    async def text(self) -> str:
        return self._body

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *exc: object) -> None:
        return None


class Session:
    """경로별로 정해 둔 응답을 순서대로 돌려준다. 요청을 기록한다."""

    def __init__(self, routes: dict[str, list[Resp | Exception]]) -> None:
        self.routes = {k: list(v) for k, v in routes.items()}
        self.requests: list[tuple[str, dict[str, str], object]] = []

    def post(self, url: str, *, json: object = None, headers: dict[str, str] | None = None,
             **_: object) -> Resp:
        path = url.split(".com", 1)[1]
        self.requests.append((path, dict(headers or {}), json))
        queue = self.routes[path]
        item = queue.pop(0) if len(queue) > 1 else queue[0]
        if isinstance(item, Exception):
            raise item
        return item

    async def close(self) -> None:
        return None

    def count(self, path: str) -> int:
        return sum(1 for p, _, _ in self.requests if p == path)


def settings(**over: object) -> Settings:
    base: dict[str, object] = {
        "ecos_api_key": _Secret("ecos"),
        "kiwoom_app_key": _Secret("APPKEY-SENTINEL"),
        "kiwoom_app_secret": _Secret("APPSECRET-SENTINEL"),
        "kiwoom_max_retries": 3,
    }
    base.update(over)
    return Settings(**base)  # type: ignore[arg-type]


def client(session: Session, **over: object) -> KiwoomClient:
    return KiwoomClient(settings(**over), session=session, now=lambda: NOW)  # type: ignore[arg-type]


TOKEN = "/oauth2/token"
KR = "/api/dostk/stkinfo"
US = "/api/us/stkinfo"


class Test토큰:
    async def test_토큰을_한_번_받아_재사용한다(self, no_sleep: list[float]) -> None:
        s = Session({TOKEN: [Resp(TOKEN_OK)], KR: [Resp(fixture("KOSPI_p01.json"))]})
        async with client(s) as c:
            await c.fetch_unit("KOSPI")
            await c.fetch_unit("KOSDAQ")
        assert s.count(TOKEN) == 1

    async def test_만료_10분_전이면_다시_받는다(self, no_sleep: list[float]) -> None:
        soon = (NOW.astimezone(KST) + dt.timedelta(minutes=5)).strftime("%Y%m%d%H%M%S")
        expiring = json.dumps({"return_code": 0, "token": "FAKE-1", "expires_dt": soon})
        s = Session({TOKEN: [Resp(expiring), Resp(TOKEN_OK)], KR: [Resp(fixture("KOSPI_p01.json"))]})
        async with client(s) as c:
            await c.fetch_unit("KOSPI")
            await c.fetch_unit("KOSDAQ")
        assert s.count(TOKEN) == 2

    async def test_목록_요청에_api_id와_Bearer_토큰을_싣는다(self, no_sleep: list[float]) -> None:
        s = Session({TOKEN: [Resp(TOKEN_OK)], US: [Resp(fixture("NYSE_p01.json"))]})
        async with client(s) as c:
            await c.fetch_unit("NYSE")
        path, headers, body = s.requests[-1]
        assert path == US
        assert headers["api-id"] == "usa10099"
        assert headers["authorization"] == "Bearer FAKE-TOKEN-0001"
        assert body == {"stex_tp": "NY"}

    async def test_결과에_토큰과_헤더가_섞이지_않는다(self, no_sleep: list[float]) -> None:
        """FR-061 — 원본 보관 대상은 본문뿐이다. 헤더를 넘기면 인증 헤더가 섞인다."""
        s = Session({TOKEN: [Resp(TOKEN_OK)], KR: [Resp(fixture("KOSPI_p01.json"))]})
        async with client(s) as c:
            pages = await c.fetch_unit("KOSPI")
        for page in pages:
            assert "FAKE-TOKEN" not in page.body
            assert not hasattr(page, "headers")
        assert "FAKE-TOKEN" not in repr(c) and "SENTINEL" not in repr(c)


class Test연속조회:
    async def test_cont_yn이_Y면_next_key로_이어_받는다(self, no_sleep: list[float]) -> None:
        rows = json.loads(fixture("KOSDAQ_p01.json"))["list"]
        first = json.dumps({"return_code": 0, "list": rows[:1000]})
        second = json.dumps({"return_code": 0, "list": rows[1000:]})
        s = Session({TOKEN: [Resp(TOKEN_OK)],
                     KR: [Resp(first, headers={"cont-yn": "Y", "next-key": "K-1000"}),
                          Resp(second, headers={"cont-yn": "N"})]})
        async with client(s) as c:
            pages = await c.fetch_unit("KOSDAQ")
        assert len(pages) == 2
        _, headers, _ = s.requests[-1]
        assert headers["cont-yn"] == "Y" and headers["next-key"] == "K-1000"
        assert pages[0].cont_yn == "Y" and pages[1].cont_yn == "N"

    async def test_실제_응답은_한_쪽에_끝난다(self, no_sleep: list[float]) -> None:
        """T005 실측 — 단위마다 한 쪽에 전부 온다."""
        meta = json.loads(fixture("NASDAQ_p01.meta.json"))
        s = Session({TOKEN: [Resp(TOKEN_OK)],
                     US: [Resp(fixture("NASDAQ_p01.json"), headers={"cont-yn": meta["cont_yn"]})]})
        async with client(s) as c:
            pages = await c.fetch_unit("NASDAQ")
        assert len(pages) == 1
        assert len(json.loads(pages[0].body)["list"]) == 5211

    async def test_미국은_쪽_사이에_설정한_간격을_둔다(self, no_sleep: list[float]) -> None:
        rows = json.loads(fixture("AMEX_p01.json"))["list"]
        s = Session({TOKEN: [Resp(TOKEN_OK)],
                     US: [Resp(json.dumps({"return_code": 0, "list": rows[:10]}),
                               headers={"cont-yn": "Y", "next-key": "K"}),
                          Resp(json.dumps({"return_code": 0, "list": rows[10:]}))]})
        async with client(s, kiwoom_us_page_delay_seconds=12) as c:
            await c.fetch_unit("AMEX")
        assert 12 in no_sleep


class Test실패_판정:
    async def test_HTTP_200이어도_return_code가_0이_아니면_실패다(self, no_sleep: list[float]) -> None:
        bad = json.dumps({"return_code": 2, "return_msg": "처리할 수 없습니다"})
        s = Session({TOKEN: [Resp(TOKEN_OK)], KR: [Resp(bad)]})
        async with client(s) as c:
            with pytest.raises(KiwoomInvalidResponse):
                await c.fetch_unit("KOSPI")

    async def test_토큰_발급_실패의_세부_코드를_메시지에서_뽑는다(self, no_sleep: list[float]) -> None:
        """실제 응답: HTTP 200, return_code 3, 세부 코드 8001은 메시지 안에만 있다."""
        s = Session({TOKEN: [Resp(fixture("error_auth_token.json"))]})
        async with client(s) as c:
            with pytest.raises(KiwoomAuthError) as info:
                await c.fetch_unit("KOSPI")
        assert info.value.detail_code == 8001
        assert info.value.reason == "auth_failed"
        assert s.count(KR) == 0

    async def test_무효_토큰이면_한_번_다시_받고_그래도_안되면_인증_실패다(
        self, no_sleep: list[float]
    ) -> None:
        s = Session({TOKEN: [Resp(TOKEN_OK)], KR: [Resp(fixture("error_invalid_token.json"))]})
        async with client(s) as c:
            with pytest.raises(KiwoomAuthError) as info:
                await c.fetch_unit("KOSPI")
        assert info.value.detail_code == 8005
        assert s.count(TOKEN) == 2
        assert s.count(KR) == 2

    async def test_한도_초과는_다시_시도하지_않는다(self, no_sleep: list[float]) -> None:
        """research R6-3 — 한도 초과는 갱신 실패로 넘기고 간격 뒤에 다시 한다. 그 자리에서 두드리지 않는다."""
        s = Session({TOKEN: [Resp(TOKEN_OK)], US: [Resp(fixture("error_rate_limit.json"))]})
        async with client(s) as c:
            with pytest.raises(KiwoomRateLimited) as info:
                await c.fetch_unit("NYSE")
        assert info.value.detail_code == 1700
        assert s.count(US) == 1

    async def test_연결_실패는_설정한_횟수만큼_다시_시도한다(self, no_sleep: list[float]) -> None:
        s = Session({TOKEN: [Resp(TOKEN_OK)], KR: [aiohttp.ClientConnectionError("끊김")]})
        async with client(s, kiwoom_max_retries=3) as c:
            with pytest.raises(KiwoomUnavailable):
                await c.fetch_unit("KOSPI")
        assert s.count(KR) == 3

    async def test_5xx는_네트워크_실패다(self, no_sleep: list[float]) -> None:
        s = Session({TOKEN: [Resp(TOKEN_OK)], KR: [Resp("upstream error", status=503)]})
        async with client(s, kiwoom_max_retries=2) as c:
            with pytest.raises(KiwoomUnavailable):
                await c.fetch_unit("KOSPI")

    async def test_HTTP_401은_인증_실패다(self, no_sleep: list[float]) -> None:
        s = Session({TOKEN: [Resp("", status=401)]})
        async with client(s) as c:
            with pytest.raises(KiwoomAuthError):
                await c.fetch_unit("KOSPI")

    async def test_JSON이_아니면_invalid다(self, no_sleep: list[float]) -> None:
        s = Session({TOKEN: [Resp(TOKEN_OK)], KR: [Resp("<html>점검 중</html>")]})
        async with client(s) as c:
            with pytest.raises(KiwoomInvalidResponse):
                await c.fetch_unit("KOSPI")


class Test모드와_인증_정보:
    def test_모드에_따라_도메인이_바뀐다(self) -> None:
        assert KiwoomClient(settings(kiwoom_mode="real")).base_url == "https://api.kiwoom.com"
        assert KiwoomClient(settings(kiwoom_mode="mock")).base_url == "https://mockapi.kiwoom.com"

    async def test_인증_정보가_없으면_부르지_않는다(self, no_sleep: list[float]) -> None:
        """FR-028a — 사유는 `auth_missing`이다. 부르면 실패할 것이 분명한 호출로 한도만 쓴다."""
        s = Session({TOKEN: [Resp(TOKEN_OK)]})
        async with client(s, kiwoom_app_key=_Secret(""), kiwoom_app_secret=_Secret("")) as c:
            with pytest.raises(KiwoomAuthError) as info:
                await c.fetch_unit("KOSPI")
        assert info.value.reason == "auth_missing"
        assert s.requests == []

    def test_모르는_단위는_거절한다(self) -> None:
        with pytest.raises(ValueError):
            KiwoomClient(settings()).request_for("KR_ETF")
