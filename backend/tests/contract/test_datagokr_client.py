"""공공데이터포털 클라이언트 계약 테스트 (T006) — 009 FR-012~FR-014, SC-011, research
R9-1·R9-3·R9-5.

가짜 세션으로 요청 모양·재시도·오류를 본다(네트워크 없음).

- **인증키가 URL 질의(`serviceKey`)에 들어간다.** 돌려주는 원본에 URL이 없어야 하고, aiohttp 예외
  문구에 URL이 섞여 와도 키가
  지워져야 한다 — 키 그대로와 퍼센트 인코딩된 키 둘 다. `mask_secrets`는 16자 이상 영숫자 덩어리만
  가리므로 `+`·`/`·`=`가 든 예전 형식 키는 직접 지우지 않으면 조각이 남는다
- 키는 디코딩 키를 **한 번만** 인코딩한다 — 다시 인코딩하면 `%2B`가 `%252B`가 되어 인증 실패(사유
  30)로 보인다
- 재시도는 연결 실패·HTTP 5xx만, `DATA_API_RETRY_MAX_ATTEMPTS`만큼, 지연은
  `DATA_API_RETRY_BASE_DELAY_MS` × 2ⁿ + 지터
- 포털 게이트웨이 오류(HTTP 4xx + `OpenAPI_ServiceResponse`): 사유 20·30·31·32 = 인증(재시도 안 함),
  22 = 한도(재시도 안 하고
  관문을 막는다), 12 = 서비스 없음(형식 — 엔드포인트가 바뀌었다)
"""
from __future__ import annotations

import dataclasses
import datetime as dt
import gzip

import aiohttp
import pytest

from src.config.settings import Settings, _Secret, load_settings
from src.ingestion.datagokr.client import DataGoKrClient
from src.ingestion.datagokr.errors import (
    DataGoKrAuthError,
    DataGoKrFormatError,
    DataGoKrRateLimited,
    DataGoKrUnavailable,
)
from src.ingestion.datagokr.gate import DataGoKrGate

from .conftest import FIXTURES, StubResponse, StubSession, load

#: 64자 영숫자 — 지금 형식의 키.
PLAIN_KEY = "abcdefABCDEF0123456789abcdefABCDEF0123456789abcdefABCDEF01234567"
SLASHED_KEY = "TEST+KEY/1234567890abcd=="  # 예전 형식(디코딩 키) — +·/·=가 든다
SLASHED_ENCODED = "TEST%2BKEY%2F1234567890abcd%3D%3D"
GATEWAY_22 = (load("apt/gateway_30.xml")
              .replace("SERVICE_KEY_IS_NOT_REGISTERED_ERROR",
                       "LIMITED_NUMBER_OF_SERVICE_REQUESTS_EXCEEDS_ERROR")
              .replace("<returnReasonCode>30</returnReasonCode>",
                       "<returnReasonCode>22</returnReasonCode>"))
GATEWAY_12 = load("apt/gateway_30.xml").replace("<returnReasonCode>30</returnReasonCode>",
                                                "<returnReasonCode>12</returnReasonCode>")


class FakeCounter:
    def __init__(self) -> None:
        self.taken = 0

    async def take(self, api: str, day: dt.date, limit: int) -> bool:
        self.taken += 1
        return True


def settings(key: str = PLAIN_KEY, attempts: int = 3) -> Settings:
    return dataclasses.replace(load_settings(), data_api_key=_Secret(key),
                               data_api_retry_max_attempts=attempts,
                               data_api_retry_base_delay_ms=1000)


def client(session: object, key: str = PLAIN_KEY, *, attempts: int = 3,
           counter: FakeCounter | None = None) -> tuple[DataGoKrClient, DataGoKrGate]:
    door = DataGoKrGate(3, counter or FakeCounter(), {"trade": 9000, "region": 9000, "kapt": 4500},
                        today=lambda: dt.date(2026, 10, 5))
    api = DataGoKrClient(settings(key, attempts), door, session=session)  # type: ignore[arg-type]
    return api, door


class _RaisingSession:
    """연결 오류 — aiohttp는 오류 문구에 요청 URL을 넣는다(키가 든 질의 문자열 포함)."""

    def __init__(self, raw_key: str) -> None:
        self.calls: list[str] = []
        self._raw_key = raw_key

    def get(self, url: object, **_: object) -> object:
        self.calls.append(str(url))
        raise aiohttp.ClientConnectionError(
            f"Cannot connect to host for {url} (key={self._raw_key})")


class Test요청_모양:
    async def test_법정동코드(self) -> None:
        session = StubSession(StubResponse(load("apt/region_seoul.json")))
        api, _ = client(session)
        fetched = await api.fetch_regions(2)
        assert [str(u) for u in session.calls] == [
            "https://apis.data.go.kr/1741000/StanReginCd/getStanReginCdList"
            f"?serviceKey={PLAIN_KEY}&type=json&pageNo=2&numOfRows=1000"]
        assert fetched.result.total_count == 493
        assert (fetched.raw_status, fetched.request_ref) == (200, "regions/p2")

    async def test_단지_목록(self) -> None:
        session = StubSession(StubResponse(load("apt/kapt_list_1171010700.json")))
        api, _ = client(session)
        fetched = await api.fetch_complex_list("1171010700")
        assert [str(u) for u in session.calls] == [
            "https://apis.data.go.kr/1613000/AptListService4/getLegaldongAptList4"
            f"?serviceKey={PLAIN_KEY}&bjdCode=1171010700&pageNo=1&numOfRows=1000"]
        assert len(fetched.result.complexes) == 23
        assert fetched.request_ref == "1171010700"

    async def test_기본_정보(self) -> None:
        session = StubSession(StubResponse(load("apt/kapt_basis_A10025850.json")))
        api, _ = client(session)
        fetched = await api.fetch_complex_basis("A10025850")
        assert [str(u) for u in session.calls] == [
            "https://apis.data.go.kr/1613000/AptBasisInfoServiceV5/getAphusBassInfoV5"
            f"?serviceKey={PLAIN_KEY}&kaptCode=A10025850"]
        assert fetched.result is not None and fetched.result.households == 9510

    async def test_실거래(self) -> None:
        """상세 자료, 계약 월의 한 쪽. 원본 참조는 `시군구/년월/p쪽`."""
        body = gzip.decompress((FIXTURES / "apt/trade_11710_202006_p2.xml.gz").read_bytes())
        session = StubSession(StubResponse(body.decode("utf-8")))
        api, _ = client(session)
        fetched = await api.fetch_trades("11710", "202006", 2)
        assert [str(u) for u in session.calls] == [
            "https://apis.data.go.kr/1613000/RTMSDataSvcAptTradeDev/getRTMSDataSvcAptTradeDev"
            f"?serviceKey={PLAIN_KEY}&LAWD_CD=11710&DEAL_YMD=202006&pageNo=2&numOfRows=1000"]
        assert (fetched.endpoint, fetched.request_ref, fetched.result_code) == (
            "trade", "11710/202006/p2", "000")
        assert (fetched.result.total_count, len(fetched.result.rows)) == (1173, 173)

    async def test_키는_한_번만_인코딩한다(self) -> None:
        session = StubSession(StubResponse(load("apt/kapt_basis_A10025850.json")))
        api, _ = client(session, SLASHED_KEY)
        await api.fetch_complex_basis("A10025850")
        url = str(session.calls[0])
        assert f"serviceKey={SLASHED_ENCODED}&" in url
        assert "%25" not in url

    async def test_이미_인코딩된_키는_그대로_쓴다(self) -> None:
        session = StubSession(StubResponse(load("apt/kapt_basis_A10025850.json")))
        api, _ = client(session, SLASHED_ENCODED)
        await api.fetch_complex_basis("A10025850")
        assert f"serviceKey={SLASHED_ENCODED}&" in str(session.calls[0])

    async def test_돌려주는_원본에_URL이_없다(self) -> None:
        session = StubSession(StubResponse(load("apt/kapt_list_1171010700.json")))
        api, _ = client(session)
        fetched = await api.fetch_complex_list("1171010700")
        assert PLAIN_KEY not in fetched.raw_body
        assert fetched.raw_body == load("apt/kapt_list_1171010700.json")
        assert not any("url" in f.name for f in dataclasses.fields(fetched))

    async def test_하루_호출_수를_보내기_전에_센다(self) -> None:
        counter = FakeCounter()
        session = StubSession(StubResponse(load("apt/kapt_basis_A10025850.json")))
        api, _ = client(session, counter=counter)
        await api.fetch_complex_basis("A10025850")
        await api.fetch_complex_basis("A10025850")
        assert counter.taken == 2

    async def test_인증키가_없으면_보내지_않는다(self) -> None:
        session = StubSession(StubResponse(load("apt/kapt_basis_A10025850.json")))
        api, _ = client(session, "")
        with pytest.raises(DataGoKrAuthError):
            await api.fetch_complex_basis("A10025850")
        assert session.calls == []


class Test오류:
    @pytest.mark.parametrize(("raw_key", "encoded"),
                             [(PLAIN_KEY, PLAIN_KEY), (SLASHED_KEY, SLASHED_ENCODED)])
    async def test_연결_오류_문구에_키가_없다(self, no_sleep: list[float], raw_key: str,
                                    encoded: str) -> None:
        session = _RaisingSession(raw_key)
        api, _ = client(session, raw_key)
        with pytest.raises(DataGoKrUnavailable) as caught:
            await api.fetch_complex_basis("A10025850")
        message = str(caught.value)
        assert raw_key not in message and encoded not in message
        assert "KEY/1234567890abcd" not in message  # 예전 형식 키의 조각도 남지 않는다
        assert len(session.calls) == 3  # 연결 실패는 설정 횟수만큼 다시 시도한다

    async def test_연결_실패는_지수_백오프와_지터(self, no_sleep: list[float]) -> None:
        api, _ = client(_RaisingSession(PLAIN_KEY), attempts=4)
        with pytest.raises(DataGoKrUnavailable):
            await api.fetch_complex_basis("A10025850")
        assert len(no_sleep) == 3
        for attempt, delay in enumerate(no_sleep):
            assert 2 ** attempt <= delay < 2 ** attempt + 1  # 기준 1초 × 2ⁿ + [0, 1)초 지터

    async def test_5xx는_다시_시도한다(self, no_sleep: list[float]) -> None:
        session = StubSession(StubResponse("Service Unavailable", status=503),
                              StubResponse(load("apt/kapt_basis_A10025850.json")))
        api, _ = client(session)
        fetched = await api.fetch_complex_basis("A10025850")
        assert fetched.result is not None and len(session.calls) == 2

    async def test_인증_오류는_다시_시도하지_않는다(self, no_sleep: list[float]) -> None:
        session = StubSession(StubResponse(load("apt/gateway_30.xml"), status=403))
        api, _ = client(session)
        with pytest.raises(DataGoKrAuthError) as caught:
            await api.fetch_complex_basis("A10025850")
        assert len(session.calls) == 1
        assert "30" in str(caught.value)

    async def test_한도_사유_22는_관문을_막는다(self, no_sleep: list[float]) -> None:
        session = StubSession(StubResponse(GATEWAY_22, status=429),
                              StubResponse(load("apt/kapt_basis_A10025850.json")))
        api, _ = client(session)
        with pytest.raises(DataGoKrRateLimited):
            await api.fetch_complex_basis("A10025850")
        with pytest.raises(DataGoKrRateLimited):
            await api.fetch_complex_basis("A10025850")  # 그날 그 자료는 더 보내지 않는다
        assert len(session.calls) == 1
        region = StubSession(StubResponse(load("apt/region_seoul.json")))
        # 같은 관문, 다른 자료(법정동코드)는 계속 보낸다
        api._session = region  # type: ignore[assignment]
        assert (await api.fetch_regions(1)).result.total_count == 493

    async def test_서비스_없음_사유_12는_형식_오류(self, no_sleep: list[float]) -> None:
        session = StubSession(StubResponse(GATEWAY_12, status=403))
        api, _ = client(session)
        with pytest.raises(DataGoKrFormatError):
            await api.fetch_complex_basis("A10025850")
        assert len(session.calls) == 1

    async def test_넘겨받은_세션을_닫지_않는다(self) -> None:
        class Closing(StubSession):
            closed = 0

            async def close(self) -> None:
                Closing.closed += 1

        session = Closing(StubResponse(load("apt/kapt_basis_A10025850.json")))
        api, _ = client(session)
        async with api:
            await api.fetch_complex_basis("A10025850")
        assert Closing.closed == 0
