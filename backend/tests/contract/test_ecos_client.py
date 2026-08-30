"""ECOS 클라이언트 계약 테스트 (T044).

헌법 원칙 III: 저장된 응답 픽스처로 검증하며 네트워크를 쓰지 않는다.
FR-007·FR-012: 재시도 가능한 오류만 지수 백오프로 다시 시도한다.
"""
from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest

from src.config.settings import load_settings
from src.ingestion.ecos.client import EcosClient
from src.ingestion.ecos.errors import SourceAuthError, SourceRateLimited
from src.ingestion.protocols import FetchOutcome

from .conftest import StubResponse, StubSession, load

RANGE = (dt.date(2005, 3, 15), dt.date(2005, 3, 17))


def _client(*responses: StubResponse) -> tuple[EcosClient, StubSession]:
    session = StubSession(*responses)
    client = EcosClient(load_settings(), session=session,  # type: ignore[arg-type]
                        item_codes={"USD": "0000001", "JPY": "0000002"})
    return client, session


class Test정상_조회:
    async def test_도메인_타입을_돌려준다(self) -> None:
        client, _ = _client(StubResponse(load("search_ok.json")))
        result = await client.fetch_daily_rates("USD", *RANGE)
        assert result.outcome is FetchOutcome.OK
        assert result.quotes[0].base_rate == Decimal("999.9")

    async def test_인증키가_URL에_들어간다(self) -> None:
        client, session = _client(StubResponse(load("search_ok.json")))
        await client.fetch_daily_rates("USD", *RANGE)
        assert load_settings().ecos_api_key.reveal() in session.calls[0]

    async def test_통계표코드와_주기가_들어간다(self) -> None:
        client, session = _client(StubResponse(load("search_ok.json")))
        await client.fetch_daily_rates("USD", *RANGE)
        assert "731Y001" in session.calls[0]
        assert "/D/" in session.calls[0]

    async def test_날짜가_YYYYMMDD로_들어간다(self) -> None:
        client, session = _client(StubResponse(load("search_ok.json")))
        await client.fetch_daily_rates("USD", *RANGE)
        assert "20050315" in session.calls[0]
        assert "20050317" in session.calls[0]

    async def test_데이터_없음도_정상_결과다(self) -> None:
        client, _ = _client(StubResponse(load("info_200_no_data.json")))
        assert (await client.fetch_daily_rates("USD", *RANGE)).outcome is FetchOutcome.NO_DATA


class Test재시도:
    async def test_인증_오류는_재시도하지_않는다(self, no_sleep: list[float]) -> None:
        client, session = _client(StubResponse(load("info_100_bad_key.json")))
        with pytest.raises(SourceAuthError):
            await client.fetch_daily_rates("USD", *RANGE)
        assert len(session.calls) == 1, "재시도가 무의미한데 다시 호출했다"
        assert no_sleep == [], "백오프 대기가 발생했다"

    async def test_한도_초과는_재시도한다(self, no_sleep: list[float]) -> None:
        client, session = _client(StubResponse(load("info_300_rate_limit.json")))
        with pytest.raises(SourceRateLimited):
            await client.fetch_daily_rates("USD", *RANGE)
        assert len(session.calls) == load_settings().ecos_retry_max_attempts

    async def test_백오프_간격이_점점_늘어난다(self, no_sleep: list[float]) -> None:
        """FR-012: 재시도 간격을 점진적으로 늘린다."""
        client, _ = _client(StubResponse(load("info_300_rate_limit.json")))
        with pytest.raises(SourceRateLimited):
            await client.fetch_daily_rates("USD", *RANGE)
        assert len(no_sleep) >= 2
        assert no_sleep[-1] > no_sleep[0], f"간격이 늘지 않음: {no_sleep}"

    async def test_재시도_중_성공하면_결과를_준다(self, no_sleep: list[float]) -> None:
        client, session = _client(
            StubResponse(load("info_300_rate_limit.json")),
            StubResponse(load("search_ok.json")))
        result = await client.fetch_daily_rates("USD", *RANGE)
        assert result.outcome is FetchOutcome.OK
        assert len(session.calls) == 2


class Test항목_매핑:
    async def test_항목_목록을_조회해_매핑한다(self) -> None:
        client, session = _client(StubResponse(load("item_list_ok.json")))
        mapping = await client.verify_item_mapping("USD")
        assert mapping.source_item_code == "0000001"
        assert "StatisticItemList" in session.calls[0]

    async def test_코드가_바뀌면_재탐색한_코드를_기억한다(self) -> None:
        client, _ = _client(StubResponse(load("item_list_changed.json")))
        assert (await client.verify_item_mapping("USD")).source_item_code == "9900001"
