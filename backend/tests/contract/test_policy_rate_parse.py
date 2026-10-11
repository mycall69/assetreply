"""네이버 증권 기준금리 계약 (014 반복 2026-10-11d T203) — FR-043, SC-026, research R14-32,
data-model 17.

**공개되지 않은 내부 API**(헌법 원칙 II 이탈 — plan Complexity Tracking, 사용자 승인 2026-10-11).
**네트워크를 쓰지 않는다**(원칙 III). 실측 본문(`fixtures/policy_rate/` — T202)을 쓴다.

- 금리는 `Decimal`, 하락은 음수, 결정일은 출처 시각(한국)의 **한국 날짜**, 자리 표시
  시각(`23:59:59`)은 시각 없음
- 발표 전 행(`isRelease:false`·`"-"`)은 결정이 아니다 — 다음 결정 예정이다
- 같은 날 두 행 — 같은 값이면 하나(실제 시각 행), 다른 값이면 고르지 않고 충돌
- 목록은 다섯 은행만 읽는다(은행 id로) — 금리·결정일·다음 결정일
- 요청: 목록 주소(설정)·결정 이력 `{nationType}/calendars?page=&pageSize=60`, 브라우저형
  UA·`Accept-Language: ko-KR`
- 실패: 403 `blocked`·429 `rate_limited`·404 `not_found`(다시 시도하지 않는다), 그 밖의 4xx
  `connection`(다시 시도하지 않는다),
  5xx·연결 오류 `connection`(다시 시도한다), 배열이 아닌 본문·JSON 아님 `invalid_body`
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import json
from decimal import Decimal
from pathlib import Path
from typing import Self

import aiohttp
import pytest

from src.config.settings import Settings, load_settings
from src.ingestion.naver_rate import parse
from src.ingestion.naver_rate.banks import nation_of
from src.ingestion.naver_rate.client import PAGE_SIZE, NaverRateClient
from src.ingestion.naver_rate.errors import (
    PolicyRateBlocked,
    PolicyRateConnectionError,
    PolicyRateInvalidBody,
    PolicyRateNotFound,
    PolicyRateRateLimited,
)

FIX = Path(__file__).parent / "fixtures" / "policy_rate"
UA = "Mozilla/5.0 (테스트) Chrome/154.0.0.0 Safari/537.36"
D = dt.date


def fixture(name: str) -> str:
    return (FIX / name).read_text(encoding="utf-8")


def utc(*args: int) -> dt.datetime:
    return dt.datetime(*args, tzinfo=dt.UTC)


class Test목록:
    def test_다섯_은행을_은행_id로_읽는다(self) -> None:
        entries = parse.parse_list(fixture("list.json"))
        assert sorted(entries) == ["boe", "boj", "bok", "ecb", "fed"]
        fed = entries["fed"]
        assert fed.decided_on == D(2026, 9, 17)
        assert fed.rate == Decimal("4.00")
        assert fed.next_meeting_on == D(2026, 10, 29)
        assert entries["bok"].next_meeting_on == D(2026, 10, 22)
        assert entries["boe"].rate == Decimal("3.75")

    def test_자리_표시_시각의_결정일은_한국_날짜다(self) -> None:
        # 일본은행 목록 시각은 `2026-09-18T23:59:59+09:00` — 날짜만 안다
        assert parse.parse_list(fixture("list.json"))["boj"].decided_on == D(2026, 9, 18)

    def test_다른_은행은_읽지_않는다(self) -> None:
        body = json.loads(fixture("list.json"))
        assert any(row["nationType"] == "ARG" for row in body)
        assert "arg" not in parse.parse_list(fixture("list.json"))

    def test_배열이_아니면_invalid_body다(self) -> None:
        with pytest.raises(PolicyRateInvalidBody):
            parse.parse_list(fixture("calendars_not_list.json"))
        with pytest.raises(PolicyRateInvalidBody):
            parse.parse_list("<html>점검 중</html>")


class Test결정_이력:
    def test_발표_전_행은_결정이_아니라_다음_결정_예정이다(self) -> None:
        page = parse.parse_calendars(fixture("calendars_bok_1.json"))
        assert page.row_count == 60
        assert page.upcoming == D(2026, 10, 22)
        assert len(page.decisions) == 59
        assert all(d.decided_on != D(2026, 10, 22) for d in page.decisions)

    def test_최신부터_금리_결정일_발표_시각(self) -> None:
        page = parse.parse_calendars(fixture("calendars_bok_1.json"))
        latest = page.decisions[0]
        assert latest.decided_on == D(2026, 8, 27)
        assert latest.rate == Decimal("3.00")
        assert latest.announced_at == utc(2026, 8, 27, 1, 0)  # 한국 10:00
        days = [d.decided_on for d in page.decisions]
        assert days == sorted(days, reverse=True)

    def test_하락은_음수_금리는_그대로다(self) -> None:
        page = parse.parse_calendars(fixture("calendars_bok_1.json"))
        cut = next(d for d in page.decisions if d.decided_on == D(2025, 5, 29))
        assert cut.rate == Decimal("2.50")

    def test_FOMC는_한국_날짜가_결정일이다(self) -> None:
        page = parse.parse_calendars(fixture("calendars_fed_1.json"))
        latest = page.decisions[0]
        # 한국 2026-09-17 03:00 = 미국 동부 09-16 14:00 — 결정일은 한국 날짜다(spec FR-040)
        assert latest.decided_on == D(2026, 9, 17)
        assert latest.announced_at == utc(2026, 9, 16, 18, 0)
        assert page.upcoming is None

    def test_자리_표시_시각은_시각_없음이다(self) -> None:
        page = parse.parse_calendars(fixture("calendars_bok_2.json"))
        oldest = page.decisions[-1]
        assert (oldest.decided_on, oldest.rate, oldest.announced_at) == (
            D(2016, 1, 14), Decimal("1.50"), None)

    def test_같은_날_같은_값은_한_행이다(self) -> None:
        page = parse.parse_calendars(fixture("calendars_bok_2.json"))
        assert page.row_count == 32
        days = [d.decided_on for d in page.decisions]
        assert days.count(D(2017, 5, 25)) == 1
        assert len(days) == len(set(days)) == 31
        assert page.conflicts == []

    def test_같은_날이면_실제_시각_행이_자리_표시보다_먼저다(self) -> None:
        page = parse.parse_calendars(fixture("calendars_boj_1.json"))
        by_day = {d.decided_on: d for d in page.decisions}
        assert by_day[D(2026, 9, 18)].announced_at == utc(2026, 9, 18, 2, 54, 4)
        assert by_day[D(2026, 6, 16)].announced_at == utc(2026, 6, 16, 3, 19, 4)
        assert len(page.decisions) == 24

    def test_마이너스_금리(self) -> None:
        page = parse.parse_calendars(fixture("calendars_boj_1.json"))
        by_day = {d.decided_on: d for d in page.decisions}
        assert by_day[D(2024, 1, 23)].rate == Decimal("-0.10")

    def test_같은_날_다른_값은_고르지_않고_충돌이다(self) -> None:
        page = parse.parse_calendars(fixture("calendars_conflict.json"))
        assert D(2026, 7, 30) not in {d.decided_on for d in page.decisions}
        clash = parse.Conflict(D(2026, 7, 30), (Decimal("3.75"), Decimal("3.50")))
        assert page.conflicts == [clash]
        assert D(2026, 9, 17) in {d.decided_on for d in page.decisions}

    def test_빈_쪽(self) -> None:
        page = parse.parse_calendars(fixture("calendars_empty.json"))
        assert (page.row_count, page.decisions, page.upcoming) == (0, [], None)

    def test_읽을_수_없으면_invalid_body다(self) -> None:
        with pytest.raises(PolicyRateInvalidBody):
            parse.parse_calendars(fixture("calendars_not_list.json"))
        with pytest.raises(PolicyRateInvalidBody):
            parse.parse_calendars("not json")
        broken = json.loads(fixture("calendars_fed_1.json"))
        broken[0]["closePrice"] = "사"
        with pytest.raises(PolicyRateInvalidBody):
            parse.parse_calendars(json.dumps(broken))


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


def settings(**over: object) -> Settings:
    base: dict[str, object] = {
        "news_user_agent": UA,
        "policy_rate_retry_max_attempts": 2,
        "policy_rate_min_interval_ms": 1000,
    }
    base.update(over)
    return dataclasses.replace(load_settings(), **base)  # type: ignore[arg-type]


class Clock:
    """요청 사이 간격을 보는 단조 시계 — 잠든 만큼 흐른다."""

    def __init__(self) -> None:
        self.now = 100.0
        self.sleeps: list[float] = []

    def __call__(self) -> float:
        return self.now

    async def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


def client(session: Session, clock: Clock | None = None, **over: object) -> NaverRateClient:
    tick = clock or Clock()
    return NaverRateClient(
        settings(**over),
        session=session,  # type: ignore[arg-type]
        sleep=tick.sleep,
        monotonic=tick,
    )


class Test요청:
    async def test_목록_주소와_머리(self) -> None:
        session = Session([Resp(fixture("list.json"))])
        async with client(session) as rates:
            fetched = await rates.fetch_list()
        url, params, headers = session.requests[0]
        assert url == load_settings().policy_rate_url
        assert params == {}
        assert headers["User-Agent"] == UA
        assert headers["Accept-Language"].startswith("ko-KR")
        assert fetched.raw == fixture("list.json")
        assert fetched.entries["bok"].rate == Decimal("3.00")

    async def test_결정_이력은_은행의_출처_국가_쪽_60(self) -> None:
        assert PAGE_SIZE == 60
        assert nation_of("bok") == "KOR"
        session = Session([Resp(fixture("calendars_bok_2.json"))])
        async with client(session) as rates:
            fetched = await rates.fetch_calendars("bok", 2)
        url, params, _ = session.requests[0]
        assert url == f"{load_settings().policy_rate_url}/KOR/calendars"
        assert params == {"page": "2", "pageSize": "60"}
        assert fetched.page.row_count == 32
        assert fetched.raw == fixture("calendars_bok_2.json")

    async def test_주소는_설정이다(self) -> None:
        session = Session([Resp(fixture("list.json"))])
        async with client(session, policy_rate_url="https://example.test/rates") as rates:
            await rates.fetch_list()
        assert session.requests[0][0] == "https://example.test/rates"

    async def test_요청_사이_간격을_지킨다(self) -> None:
        clock = Clock()
        session = Session([Resp(fixture("list.json")), Resp(fixture("calendars_empty.json"))])
        async with client(session, clock) as rates:
            await rates.fetch_list()
            await rates.fetch_calendars("fed", 1)
        assert clock.sleeps == [1.0]

    @pytest.mark.parametrize(
        ("status", "error"),
        [(403, PolicyRateBlocked), (401, PolicyRateBlocked), (429, PolicyRateRateLimited),
         (404, PolicyRateNotFound)],
    )
    async def test_다시_시도하지_않는_실패(self, status: int, error: type[Exception]) -> None:
        session = Session([Resp("x", status), Resp(fixture("list.json"))])
        async with client(session) as rates:
            with pytest.raises(error):
                await rates.fetch_list()
        assert len(session.requests) == 1

    async def test_쪽_크기_상한_400은_connection이고_다시_시도하지_않는다(self) -> None:
        session = Session([Resp(fixture("calendars_page_size_400.json"), 400), Resp("[]")])
        async with client(session) as rates:
            with pytest.raises(PolicyRateConnectionError) as caught:
                await rates.fetch_calendars("bok", 1)
        assert len(session.requests) == 1
        assert "400" in str(caught.value)
        # 본문을 오류 문구에 싣지 않는다
        assert "pageSize" not in str(caught.value)

    async def test_5xx는_다시_시도한_뒤_connection이다(self) -> None:
        session = Session([Resp("down", 503), Resp("down", 502)])
        async with client(session) as rates:
            with pytest.raises(PolicyRateConnectionError):
                await rates.fetch_list()
        assert len(session.requests) == 2

    async def test_연결_오류_뒤_성공(self) -> None:
        session = Session([aiohttp.ClientConnectionError("x"), Resp(fixture("list.json"))])
        async with client(session) as rates:
            fetched = await rates.fetch_list()
        assert len(fetched.entries) == 5

    async def test_시간_초과는_connection이다(self) -> None:
        session = Session([TimeoutError(), TimeoutError()])
        async with client(session) as rates:
            with pytest.raises(PolicyRateConnectionError):
                await rates.fetch_calendars("fed", 1)

    async def test_사용자_에이전트를_비우면_싣지_않는다(self) -> None:
        session = Session([Resp(fixture("list.json"))])
        async with client(session, news_user_agent="") as rates:
            await rates.fetch_list()
        assert "User-Agent" not in session.requests[0][2]

    async def test_실패의_종류(self) -> None:
        assert PolicyRateConnectionError.kind == "connection"
        assert PolicyRateRateLimited.kind == "rate_limited"
        assert PolicyRateBlocked.kind == "blocked"
        assert PolicyRateInvalidBody.kind == "invalid_body"
        assert PolicyRateNotFound.kind == "not_found"
