"""Npay 부동산 단지 자동완성 클라이언트 계약 (010 반복 3, T061) — FR-029, research R10-19.
**공개되지 않은 내부 API**(헌법 원칙 II 이탈).

**네트워크를 쓰지 않는다**(헌법 원칙 III). 세션·시계·대기를 흉내 내고 응답은 실제 응답 본문
픽스처(2026-10-06 관찰)를 쓴다.

- 요청: `{base}/search/autocomplete/complexes?keyword=…&size=10&page=0`, 브라우저형 사용자
  에이전트·`Referer`·`Accept`(기본 사용자 에이전트는 403)
- 후보: 번호·이름·법정동 코드·유형 — 출처 키 이름(`complexNumber` 등)은 어댑터 밖으로 나가지 않는다
- **403은 차단**(재시도 없음). 429·5xx·연결 오류는 지수 백오프 + 지터로 재시도하고, 429가 끝까지
  이어지면 `rate_limited`다
- 요청 사이 최소 간격을 지킨다 — 짧은 시간에 여러 번 부르면 출처가 429를 준다(관찰)
"""

from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import Self

import aiohttp
import pytest

from src.config.settings import Settings, load_settings
from src.ingestion.naver_land.client import NaverLandClient
from src.ingestion.naver_land.errors import (
    NaverLandBlocked,
    NaverLandFormatError,
    NaverLandNetworkError,
    NaverLandRateLimited,
)
from src.ingestion.naver_land.parse import NaverComplexCandidate, parse_complexes

FIXTURES = Path(__file__).parent / "fixtures" / "naver_land"
UA = "Mozilla/5.0 (테스트) Chrome/154.0.0.0 Safari/537.36"
REFERER = "https://fin.land.naver.com/map"


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


class Resp:
    def __init__(self, body: str, status: int = 200) -> None:
        self._body = body
        self.status = status

    async def text(self) -> str:
        return self._body

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *exc: object) -> None:
        return None


class Session:
    def __init__(self, replies: list[Resp | Exception]) -> None:
        self.replies = list(replies)
        self.requests: list[tuple[str, dict[str, str], dict[str, str]]] = []

    def get(
        self,
        url: str,
        *,
        params: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
        **_: object,
    ) -> Resp:
        self.requests.append((url, dict(params or {}), dict(headers or {})))
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply

    async def close(self) -> None:
        return None


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0
        self.sleeps: list[float] = []

    def monotonic(self) -> float:
        return self.now

    async def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)


def settings(**over: object) -> Settings:
    base = dict(
        naver_land_base_url="https://fin.land.naver.com/front-api/v1",
        naver_land_accept_language="ko-KR,ko;q=0.9",
        naver_land_user_agent=UA,
        naver_land_referer=REFERER,
        naver_land_min_interval_ms=2000,
        naver_land_max_retries=3,
        naver_land_backoff_base_ms=3000,
    )
    base.update(over)
    return dataclasses.replace(load_settings(), **base)  # type: ignore[arg-type]


def client(session: Session, clock: Clock, **over: object) -> NaverLandClient:
    return NaverLandClient(
        settings(**over),
        session=session,  # type: ignore[arg-type]
        monotonic=clock.monotonic,
        sleep=clock.sleep,
    )


class Test파싱:
    def test_후보는_번호_이름_법정동_코드_유형이다(self) -> None:
        assert parse_complexes(fixture("autocomplete_helio.json")) == [
            NaverComplexCandidate(
                number=111515, name="헬리오시티", legal_division_code="1171010700", type="A01"
            )
        ]

    def test_재건축_단지도_후보다(self) -> None:
        assert parse_complexes(fixture("autocomplete_mirung.json")) == [
            NaverComplexCandidate(
                number=596, name="미륭", legal_division_code="1171010700", type="A04"
            )
        ]

    def test_여러_후보는_응답_순서대로(self) -> None:
        assert [
            (c.number, c.name) for c in parse_complexes(fixture("autocomplete_gaepo_xi.json"))
        ] == [(128527, "개포자이프레지던스"), (8928, "개포자이"), (145017, "개포자이르네")]
        assert [
            (c.number, c.type) for c in parse_complexes(fixture("autocomplete_ricenz.json"))
        ] == [(22746, "A01"), (572526, "A06")]

    def test_빈_결과는_빈_목록이다(self) -> None:
        body = ('{"isSuccess":true,"detailCode":"success","message":"",'
                '"result":{"hasNextPage":false,"totalCount":0,"list":[]}}')
        assert parse_complexes(body) == []

    @pytest.mark.parametrize(
        "body",
        [
            "<html>not json</html>",
            '{"isSuccess":false,"detailCode":"BAD_REQUEST","message":""}',
            '{"isSuccess":true,"result":{"list":[{"complexName":"번호 없음",'
            '"legalDivisionNumber":"1171010700"}]}}',
            '{"isSuccess":true,"result":{"list":[{"complexNumber":1,"complexName":"코드 짧음",'
            '"legalDivisionNumber":"11710"}]}}',
            '{"isSuccess":true,"result":{}}',
        ],
        ids=["HTML", "실패 표시", "번호 없음", "법정동 코드 형식", "목록 없음"],
    )
    def test_모양이_다르면_형식_오류다(self, body: str) -> None:
        with pytest.raises(NaverLandFormatError):
            parse_complexes(body)


class Test요청:
    async def test_경로_질의_헤더(self) -> None:
        session = Session([Resp(fixture("autocomplete_helio.json"))])
        async with client(session, Clock()) as c:
            got = await c.search_complexes("가락동 헬리오시티")
        url, params, headers = session.requests[0]
        assert url == "https://fin.land.naver.com/front-api/v1/search/autocomplete/complexes"
        assert params == {"keyword": "가락동 헬리오시티", "size": "10", "page": "0"}
        assert (headers["User-Agent"], headers["Referer"]) == (UA, REFERER)
        assert "application/json" in headers["Accept"]
        # Accept-Language가 없으면 출처가 곧바로 429를 준다(2026-10-06 실측 — 요청 제한이 아니라 브라우저답지 않은
        # 요청을 거르는 것이다). 설정값을 싣는다.
        assert headers["Accept-Language"] == "ko-KR,ko;q=0.9"
        assert [c.number for c in got.candidates] == [111515]
        assert (got.raw, got.status, got.keyword) == (
            fixture("autocomplete_helio.json"),
            200,
            "가락동 헬리오시티",
        )

    async def test_사용자_에이전트를_비우면_싣지_않는다(self) -> None:
        """차단(403) 경로를 재현하는 수단이다(quickstart 15)."""
        session = Session([Resp(fixture("autocomplete_helio.json"))])
        async with client(session, Clock(), naver_land_user_agent="") as c:
            await c.search_complexes("헬리오시티")
        assert "User-Agent" not in session.requests[0][2]

    async def test_요청_사이_최소_간격을_지킨다(self) -> None:
        clock = Clock()
        session = Session(
            [Resp(fixture("autocomplete_helio.json")), Resp(fixture("autocomplete_mirung.json"))]
        )
        async with client(session, clock) as c:
            await c.search_complexes("가락동 헬리오시티")
            await c.search_complexes("가락동 가락미륭")
        assert clock.sleeps == [2.0]


class Test차단과_재시도:
    async def test_403은_재시도_없이_차단이다(self) -> None:
        session = Session([Resp("<html>403 Forbidden</html>", status=403)])
        async with client(session, Clock()) as c:
            with pytest.raises(NaverLandBlocked):
                await c.search_complexes("헬리오시티")
        assert len(session.requests) == 1

    async def test_429와_5xx는_백오프로_재시도한다(self) -> None:
        clock = Clock()
        session = Session(
            [
                Resp('{"detailCode":"TOO_MANY_REQUESTS","message":""}', status=429),
                Resp("", status=503),
                Resp(fixture("autocomplete_helio.json")),
            ]
        )
        async with client(session, clock) as c:
            got = await c.search_complexes("헬리오시티")
        assert [c.number for c in got.candidates] == [111515]
        backoffs = [s for s in clock.sleeps if s >= 3.0]
        # 지수 백오프 + 지터: 3초·6초를 바닥으로, 지터는 기준(3초)보다 작다
        assert len(backoffs) == 2
        assert 3.0 <= backoffs[0] < 6.0
        assert 6.0 <= backoffs[1] < 9.0

    async def test_429가_끝까지_이어지면_요청_제한이다(self) -> None:
        session = Session([Resp('{"detailCode":"TOO_MANY_REQUESTS"}', status=429)] * 3)
        async with client(session, Clock()) as c:
            with pytest.raises(NaverLandRateLimited):
                await c.search_complexes("헬리오시티")
        assert len(session.requests) == 3

    async def test_연결_오류가_끝까지_이어지면_네트워크_오류다(self) -> None:
        session = Session([aiohttp.ClientConnectionError("x")] * 3)
        async with client(session, Clock()) as c:
            with pytest.raises(NaverLandNetworkError):
                await c.search_complexes("헬리오시티")
        assert len(session.requests) == 3

    async def test_400은_재시도_없이_형식_오류다(self) -> None:
        session = Session([Resp('{"isSuccess":false}', status=400)])
        async with client(session, Clock()) as c:
            with pytest.raises(NaverLandFormatError):
                await c.search_complexes("헬리오시티")
        assert len(session.requests) == 1

    def test_오류의_종류(self) -> None:
        assert (
            NaverLandBlocked.kind,
            NaverLandRateLimited.kind,
            NaverLandNetworkError.kind,
            NaverLandFormatError.kind,
        ) == ("blocked", "rate_limited", "network", "format")
