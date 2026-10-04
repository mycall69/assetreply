"""예금 금리 클라이언트 계약 테스트 (T004) — 008 FR-014, FR-016, research R8-5.

가짜 세션으로 요청 모양과 재시도를 본다(네트워크 없음). **인증키가 URL 경로에 들어간다** —
그래서 돌려주는 원본에 URL이 없어야 하고, 연결 오류 문구에 URL이 섞여 와도 키가 지워져야 한다
(FR-014, SC-011).
"""
from __future__ import annotations

import dataclasses
import datetime as dt

import aiohttp
import pytest

from src.config.settings import Settings, _Secret, load_settings
from src.ingestion.ecos.deposit_client import EcosDepositClient
from src.ingestion.ecos.errors import SourceAuthError, SourceRateLimited, SourceUnavailable

from .conftest import StubResponse, StubSession, load

FAKE_KEY = "TESTKEY1234567890abcd"


def _settings() -> Settings:
    return dataclasses.replace(load_settings(), ecos_api_key=_Secret(FAKE_KEY))


class _ClosingSession(StubSession):
    def __init__(self, *responses: StubResponse) -> None:
        super().__init__(*responses)
        self.closed = 0

    async def close(self) -> None:
        self.closed += 1


class _RaisingSession:
    """연결 오류 — aiohttp는 오류 문구에 요청 URL을 넣는다."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def get(self, url: str, **_: object) -> object:
        self.calls.append(url)
        raise aiohttp.ClientConnectionError(f"Cannot connect to host for {url}")


def _client(session: object) -> EcosDepositClient:
    return EcosDepositClient(_settings(), session=session)  # type: ignore[arg-type]


class Test요청_모양:
    async def test_항목_목록(self) -> None:
        session = StubSession(StubResponse(load("deposit/items_121Y004.json")))
        result = await _client(session).fetch_items("121Y004")
        assert session.calls == [
            f"https://ecos.bok.or.kr/api/StatisticItemList/{FAKE_KEY}/json/kr/1/10000/121Y004/"]
        assert set(result.items) == {"savings_bank", "credit_union", "mutual_finance", "saemaul"}
        assert result.raw_body == load("deposit/items_121Y004.json")
        assert result.raw_status == 200

    async def test_월_시계열(self) -> None:
        session = StubSession(StubResponse(load("deposit/items_121Y004.json")),
                              StubResponse(load("deposit/series_savings_bank.json")))
        client = _client(session)
        item = (await client.fetch_items("121Y004")).items["savings_bank"]
        result = await client.fetch_series(item, dt.date(1997, 8, 1), dt.date(2026, 10, 1))
        assert session.calls[1] == (
            f"https://ecos.bok.or.kr/api/StatisticSearch/{FAKE_KEY}/json/kr/1/10000/"
            "121Y004/M/199708/202610/BEBBBE01")
        assert len(result.rates) == 349

    async def test_돌려주는_원본에_URL이_없다(self) -> None:
        session = StubSession(StubResponse(load("deposit/items_121Y002.json")),
                              StubResponse(load("deposit/series_commercial_bank.json")))
        client = _client(session)
        items = await client.fetch_items("121Y002")
        result = await client.fetch_series(
            items.items["commercial_bank"], dt.date(2012, 1, 1), dt.date(2026, 10, 1))
        for raw in (items.raw_body, result.raw_body):
            assert FAKE_KEY not in raw
        assert not any("url" in f.name for f in dataclasses.fields(result))

    async def test_항목은_통계표마다_한_번만_받는다(self) -> None:
        session = StubSession(StubResponse(load("deposit/items_121Y004.json")))
        client = _client(session)
        first = await client.items_for("savings_bank")
        second = await client.items_for("saemaul")
        assert len(session.calls) == 1
        assert first.fetched is not None and second.fetched is None
        assert (first.item.item_code, second.item.item_code) == ("BEBBBE01", "BEBBA000")


class Test오류:
    async def test_연결_오류_문구에_인증키가_없다(self) -> None:
        session = _RaisingSession()
        with pytest.raises(SourceUnavailable) as info:
            await _client(session).fetch_items("121Y004")
        assert FAKE_KEY in session.calls[0]
        assert FAKE_KEY not in str(info.value)

    async def test_한도_초과는_설정_횟수만큼_다시_시도한다(self, no_sleep: list[float]) -> None:
        session = StubSession(StubResponse(load("info_300_rate_limit.json")))
        with pytest.raises(SourceRateLimited) as info:
            await _client(session).fetch_items("121Y004")
        assert len(session.calls) == load_settings().ecos_retry_max_attempts
        assert len(no_sleep) >= 2 and no_sleep[-1] > no_sleep[0]
        assert FAKE_KEY not in str(info.value)

    async def test_인증_실패는_다시_시도하지_않는다(self, no_sleep: list[float]) -> None:
        session = StubSession(StubResponse(load("info_100_bad_key.json")))
        with pytest.raises(SourceAuthError):
            await _client(session).fetch_items("121Y004")
        assert len(session.calls) == 1
        assert no_sleep == []

    async def test_넘겨받은_세션은_닫지_않는다(self) -> None:
        session = _ClosingSession(StubResponse(load("deposit/items_121Y004.json")))
        async with _client(session) as client:
            await client.fetch_items("121Y004")
        assert session.closed == 0
