"""가상자산 출처 클라이언트 계약 (T004) — 007 FR-016, FR-018, FR-020, research R7-1.

**네트워크를 쓰지 않는다**(헌법 원칙 III). 세션·시계·대기를 흉내 내고 응답은 실제 응답
픽스처(T001)를 쓴다.

- 기본 사용자 에이전트는 403이다 — 설정의 브라우저형 문자열을 모든 요청에 싣는다. 일봉 요청은
  `domain-id` 헤더도 필요하다
- **403은 차단**이다 — 재시도로 풀리지 않으므로 바로 실패한다. 429·5xx·연결 오류만 백오프+지터로
  재시도한다
- 목록 갱신과 시세 수집이 **같은 클라이언트의 간격 제한기**를 함께 쓴다 — 요청 사이 최소 간격을
  지킨다
"""
from __future__ import annotations

import dataclasses
import datetime as dt
from pathlib import Path
from typing import Self

import aiohttp
import pytest
from src.ingestion.investing.client import InvestingClient
from src.ingestion.investing.errors import (
    InvestingBlocked,
    InvestingFormatError,
    InvestingNetworkError,
)

from src.config.settings import Settings, load_settings

FIXTURES = Path(__file__).parent / "fixtures" / "crypto"
D = dt.date.fromisoformat
UA = "Mozilla/5.0 (테스트) Chrome/154.0.0.0 Safari/537.36"
#: 계산 끝(UTC 어제). 마감 전인 2026-10-03의 일봉은 버린다
LAST = D("2026-10-02")


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
    """정해 둔 응답을 차례로 돌려준다(예외를 넣으면 그 예외를 낸다). 요청을 기록한다."""

    def __init__(self, replies: list[Resp | Exception]) -> None:
        self.replies = list(replies)
        self.requests: list[tuple[str, dict[str, str], dict[str, str]]] = []
        self.closed = False

    def get(self, url: str, *, params: dict[str, str] | None = None,
            headers: dict[str, str] | None = None, **_: object) -> Resp:
        self.requests.append((url, dict(params or {}), dict(headers or {})))
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply

    async def close(self) -> None:
        self.closed = True


class Clock:
    """멈춘 시계와 기록하는 대기. 간격 제한기가 얼마를 기다렸는지 본다."""

    def __init__(self) -> None:
        self.now = 1000.0
        self.sleeps: list[float] = []

    def monotonic(self) -> float:
        return self.now

    async def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)


def settings(**over: object) -> Settings:
    base = dict(investing_user_agent=UA, investing_domain_id="www", investing_min_interval_ms=1500,
                investing_max_retries=3, investing_backoff_base_ms=2000)
    base.update(over)
    return dataclasses.replace(load_settings(), **base)  # type: ignore[arg-type]


def client(session: Session, clock: Clock, **over: object) -> InvestingClient:
    return InvestingClient(settings(**over), session=session,  # type: ignore[arg-type]
                           monotonic=clock.monotonic, sleep=clock.sleep)


class Test목록:
    async def test_커서로_끝까지_넘긴다(self) -> None:
        session = Session([Resp(fixture("coins_en_p1.json")), Resp(fixture("coins_en_last.json"))])
        async with client(session, Clock()) as c:
            pages = [p async for p in c.fetch_coin_pages("en")]
        assert [len(p.page.coins) for p in pages] == [100, 54]
        assert [p.page_no for p in pages] == [1, 2]
        (url1, p1, h1), (url2, p2, _) = session.requests
        assert url1.endswith("/v1/crypto/coins")
        assert p1 == {"sort": "rank", "order": "asc", "limit": "100", "domain_id": "1"}
        assert p2["cursor"] == pages[0].page.next_cursor
        assert h1["User-Agent"] == UA

    async def test_한국어_판은_domain_id_18이다(self) -> None:
        session = Session([Resp(fixture("coins_en_last.json"))])
        async with client(session, Clock()) as c:
            [p async for p in c.fetch_coin_pages("ko")]
        assert session.requests[0][1]["domain_id"] == "18"

    async def test_원본_본문과_상태를_함께_돌려준다(self) -> None:
        body = fixture("coins_en_last.json")
        session = Session([Resp(body)])
        async with client(session, Clock()) as c:
            [page] = [p async for p in c.fetch_coin_pages("en")]
        assert (page.raw, page.status) == (body, 200)

    async def test_모르는_판은_거절한다(self) -> None:
        async with client(Session([]), Clock()) as c:
            with pytest.raises(ValueError):
                [p async for p in c.fetch_coin_pages("jp")]


class Test일봉:
    async def test_요청_형식(self) -> None:
        session = Session([Resp(fixture("btc_2020_2021.json"))])
        async with client(session, Clock()) as c:
            got = await c.fetch_daily("1057391", D("2020-01-01"), D("2021-12-31"), last_day=LAST)
        url, params, headers = session.requests[0]
        assert url.endswith("/api/financialdata/historical/1057391")
        assert params == {"start-date": "2020-01-01", "end-date": "2021-12-31",
                          "time-frame": "Daily", "add-missing-rows": "false"}
        assert headers["User-Agent"] == UA
        assert headers["domain-id"] == "www"
        assert len(got.bars) == 731
        assert (got.requested_from, got.requested_to, got.status) == (
            D("2020-01-01"), D("2021-12-31"), 200)
        assert got.raw == fixture("btc_2020_2021.json")

    async def test_마감_전_일봉은_버린다(self) -> None:
        session = Session([Resp(fixture("btc_recent.json"))])
        async with client(session, Clock()) as c:
            got = await c.fetch_daily("1057391", D("2026-09-13"), D("2026-10-03"), last_day=LAST)
        assert got.bars[-1].day == D("2026-10-02")


class Test차단과_재시도:
    async def test_403은_재시도_없이_차단이다(self) -> None:
        clock = Clock()
        session = Session([Resp(fixture("blocked_403.txt"), status=403)])
        async with client(session, clock) as c:
            with pytest.raises(InvestingBlocked):
                await c.fetch_daily("1057391", D("2026-09-28"), D("2026-10-02"), last_day=LAST)
        assert len(session.requests) == 1

    async def test_HTML_확인_페이지도_차단이다(self) -> None:
        session = Session([Resp("<!DOCTYPE html><html>Just a moment...</html>", status=403)])
        async with client(session, Clock()) as c:
            with pytest.raises(InvestingBlocked):
                await c.fetch_daily("1057391", D("2026-09-28"), D("2026-10-02"), last_day=LAST)

    async def test_400은_재시도_없이_형식_오류다(self) -> None:
        session = Session([Resp('{"@errors":["Domain required"]}', status=400)])
        async with client(session, Clock()) as c:
            with pytest.raises(InvestingFormatError):
                await c.fetch_daily("1057391", D("2026-09-28"), D("2026-10-02"), last_day=LAST)
        assert len(session.requests) == 1

    async def test_429와_5xx는_백오프로_재시도한다(self) -> None:
        clock = Clock()
        session = Session([Resp("", status=429), Resp("", status=503),
                           Resp(fixture("btc_2011_06.json"))])
        async with client(session, clock) as c:
            got = await c.fetch_daily("1057391", D("2011-06-01"), D("2011-07-31"), last_day=LAST)
        assert len(got.bars) == 61
        assert len(session.requests) == 3
        backoffs = [s for s in clock.sleeps if s >= 2.0]
        # 지수 백오프 + 지터: 2초·4초를 바닥으로, 지터는 기준(2초)보다 작다
        assert len(backoffs) == 2
        assert 2.0 <= backoffs[0] < 4.0
        assert 4.0 <= backoffs[1] < 6.0

    async def test_연결_오류도_재시도하고_끝내_실패하면_네트워크_오류다(self) -> None:
        session = Session([aiohttp.ClientConnectionError("x")] * 3)
        async with client(session, Clock()) as c:
            with pytest.raises(InvestingNetworkError):
                await c.fetch_daily("1057391", D("2011-06-01"), D("2011-07-31"), last_day=LAST)
        assert len(session.requests) == 3

    async def test_5xx가_끝까지_이어지면_네트워크_오류다(self) -> None:
        session = Session([Resp("", status=502)] * 3)
        async with client(session, Clock()) as c:
            with pytest.raises(InvestingNetworkError):
                [p async for p in c.fetch_coin_pages("en")]


class Test간격:
    async def test_요청_사이_최소_간격을_지킨다(self) -> None:
        clock = Clock()
        session = Session([Resp(fixture("coins_en_p1.json")), Resp(fixture("coins_en_last.json"))])
        async with client(session, clock) as c:
            [p async for p in c.fetch_coin_pages("en")]
        # 시계가 멈춰 있으므로 둘째 요청 앞에서 간격 전부를 기다린다. 첫 요청은 기다리지 않는다
        assert clock.sleeps == [1.5]

    async def test_목록과_일봉이_같은_간격을_공유한다(self) -> None:
        """두 줄이 한 클라이언트를 쓴다 — 출처 입장에서는 한 클라이언트다."""
        clock = Clock()
        session = Session([Resp(fixture("coins_en_last.json")), Resp(fixture("btc_2011_06.json"))])
        async with client(session, clock) as c:
            [p async for p in c.fetch_coin_pages("en")]
            await c.fetch_daily("1057391", D("2011-06-01"), D("2011-07-31"), last_day=LAST)
        assert clock.sleeps == [1.5]

    async def test_시간이_지났으면_기다리지_않는다(self) -> None:
        clock = Clock()

        class Advancing(Session):
            def get(self, *a: object, **k: object) -> Resp:  # type: ignore[override]
                clock.now += 5
                return super().get(*a, **k)  # type: ignore[arg-type]

        session = Advancing([Resp(fixture("coins_en_p1.json")),
                             Resp(fixture("coins_en_last.json"))])
        async with client(session, clock) as c:
            [p async for p in c.fetch_coin_pages("en")]
        assert clock.sleeps == []


class Test세션과_설정:
    async def test_넘겨받은_세션은_닫지_않는다(self) -> None:
        session = Session([Resp(fixture("coins_en_last.json"))])
        async with client(session, Clock()) as c:
            [p async for p in c.fetch_coin_pages("en")]
        assert session.closed is False

    async def test_사용자_에이전트가_비면_보내지_않는다(self) -> None:
        """비우면 aiohttp 기본값이 나가 403이 된다 — quickstart 17이 이 경로로 차단을 재현한다."""
        session = Session([Resp(fixture("coins_en_last.json"))])
        async with client(session, Clock(), investing_user_agent="") as c:
            [p async for p in c.fetch_coin_pages("en")]
        assert "User-Agent" not in session.requests[0][2]
