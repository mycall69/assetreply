"""공공데이터포털 클라이언트 (009 T012, FR-012~FR-014, research R9-1·R9-3·R9-5).

- 요청은 관문(`gate.DataGoKrGate`)을 지난다 — 동시 수와 자료별 하루 호출 수를 네 자료가 함께 지킨다
- **인증키가 URL 질의(`serviceKey`)에 들어간다.** 돌려주는 결과에는 응답 본문만 담고 URL은 담지
  않는다. 오류 문구에서는
  키 그대로·퍼센트 인코딩된 키·디코딩된 키를 **직접 지운 뒤** `mask_secrets`를 거친다 —
  `mask_secrets`는 16자 이상 영숫자 덩어리만 가려 `+`·`/`·`=`가 든 예전 형식 키의 조각을
  남긴다(FR-013)
- 키는 디코딩 키를 **한 번만** 인코딩한다. 이미 인코딩된 키(`%`가 든)는 그대로 쓴다 — 두 번
  인코딩하면 인증 실패(사유 30)로
  보인다. URL은 인코딩된 그대로 보낸다(`yarl.URL(…, encoded=True)`)
- 재시도는 연결 실패·HTTP 5xx·본문이 JSON/XML이 아닌 경우만(`DATA_API_RETRY_MAX_ATTEMPTS`, 지수
  백오프 + 지터). 인증·한도·
  형식은 다시 시도하지 않는다. 포털이 한도 사유 22를 주면 관문이 그날 그 자료를 막는다
- 포털 게이트웨이 오류는 HTTP 4xx + `OpenAPI_ServiceResponse`(XML)다: 사유 20·30·31·32 = 인증, 22 =
  한도, 12 = 서비스 없음
  (형식 — 엔드포인트가 바뀌었다), 그 밖은 연결
"""

from __future__ import annotations

import asyncio
import random
import re
import urllib.parse
from collections.abc import Callable
from dataclasses import dataclass
from types import TracebackType
from typing import Final, Self

import aiohttp
from yarl import URL

from src.config.settings import Settings
from src.ingestion.datagokr.errors import (
    DataGoKrAuthError,
    DataGoKrError,
    DataGoKrFormatError,
    DataGoKrRateLimited,
    DataGoKrUnavailable,
)
from src.ingestion.datagokr.gate import DataGoKrGate
from src.ingestion.datagokr.kapt_parse import (
    ComplexListPage,
    parse_complex_basis,
    parse_complex_list,
)
from src.ingestion.datagokr.region_parse import RegionPage, parse_regions
from src.ingestion.datagokr.trade_parse import TradePage, parse_trades
from src.ingestion.protocols import ComplexBasis
from src.observability.events import mask_secrets

BASE_URL: Final = "https://apis.data.go.kr"
TRADE_PATH: Final = "/1613000/RTMSDataSvcAptTradeDev/getRTMSDataSvcAptTradeDev"
REGION_PATH: Final = "/1741000/StanReginCd/getStanReginCdList"
COMPLEX_LIST_PATH: Final = "/1613000/AptListService4/getLegaldongAptList4"
COMPLEX_BASIS_PATH: Final = "/1613000/AptBasisInfoServiceV5/getAphusBassInfoV5"
#: 한 쪽의 행 수(포털 최대). 실거래는 송파구 한 달 최대 1,173건 — 2쪽이다(R9-1).
ROWS: Final = 1000
TIMEOUT: Final = aiohttp.ClientTimeout(total=60)

#: 게이트웨이 사유 → 실패 종류(research R9-5).
_AUTH_REASONS: Final = frozenset({"20", "30", "31", "32"})
_RATE_REASONS: Final = frozenset({"22"})
_GONE_REASONS: Final = frozenset({"12"})
_REASON = re.compile(r"<returnReasonCode>\s*(\d+)\s*</returnReasonCode>")
_RESULT_CODE = re.compile(r'"resultCode"\s*:\s*"([^"]+)"|<resultCode>([^<]+)</resultCode>')

@dataclass(frozen=True, slots=True)
class Fetched[T]:
    """한 번의 요청 결과 — 원본 본문을 함께 담는다(URL은 없다). `request_ref`는 원본 표의 불투명한
    참조다."""

    result: T
    endpoint: str
    request_ref: str
    raw_body: str
    raw_status: int
    result_code: str | None


def result_code(body: str) -> str | None:
    """원본 표에 남길 결과 코드 — 출처의 결과 코드 또는 게이트웨이 사유."""
    reason = _REASON.search(body)
    if reason:
        return reason.group(1)
    found = _RESULT_CODE.search(body)
    return (found.group(1) or found.group(2)) if found else None


class DataGoKrClient:
    """공공데이터포털 네 자료의 어댑터. `async with`로 세션 수명을 관리한다."""

    def __init__(self, settings: Settings, gate: DataGoKrGate, *,
                 session: aiohttp.ClientSession | None = None) -> None:
        self._settings = settings
        self._gate = gate
        self._session = session
        self._owns_session = session is None

    async def __aenter__(self) -> Self:
        if self._session is None:
            self._session = aiohttp.ClientSession(timeout=TIMEOUT)
        return self

    async def __aexit__(self, exc_type: type[BaseException] | None, exc: BaseException | None,
                        tb: TracebackType | None) -> None:
        if self._owns_session and self._session is not None:
            await self._session.close()
            self._session = None

    # ── 내부 ────────────────────────────────────────────────────────

    def _key(self) -> str:
        key = self._settings.data_api_key.reveal().strip()
        if not key:
            raise DataGoKrAuthError("공공데이터포털 인증키(DATA_API_KEY)가 설정되지 않았습니다")
        return key

    def _url(self, path: str, params: dict[str, str]) -> str:
        key = self._key()
        encoded = key if "%" in key else urllib.parse.quote(key, safe="")
        query = urllib.parse.urlencode(params)
        return f"{BASE_URL}{path}?serviceKey={encoded}" + (f"&{query}" if query else "")

    def _scrub(self, text: str) -> str:
        """오류 문구에 섞여 온 인증키를 지운다 — 날 것·인코딩·디코딩 세 형태 모두, 그다음 키처럼
        보이는 토큰."""
        key = self._settings.data_api_key.reveal().strip()
        if key:
            for form in sorted({key, urllib.parse.quote(key, safe=""), urllib.parse.unquote(key)},
                               key=len, reverse=True):
                text = text.replace(form, "***")
        return mask_secrets(text) or ""

    async def _get(self, url: str, api: str) -> tuple[str, int]:
        if self._session is None:
            raise RuntimeError("DataGoKrClient를 async with로 열어야 합니다.")
        async with self._gate.slot(api):
            try:
                async with self._session.get(URL(url, encoded=True)) as response:
                    return await response.text(), response.status
            except (aiohttp.ClientError, TimeoutError) as exc:
                message = self._scrub(f"출처에 연결하지 못했습니다: {exc}")
                raise DataGoKrUnavailable(message) from exc

    @staticmethod
    def _check(body: str, status: int) -> None:
        """게이트웨이 오류·HTTP 오류를 실패 종류로 바꾼다. 통과하면 본문을 파서가 읽는다."""
        if "OpenAPI_ServiceResponse" in body:
            found = _REASON.search(body)
            reason = found.group(1) if found else "?"
            if reason in _AUTH_REASONS:
                raise DataGoKrAuthError(
                    f"공공데이터포털 인증 실패(사유 {reason}) — 인증키와 활용신청을 확인하세요")
            if reason in _RATE_REASONS:
                raise DataGoKrRateLimited(f"공공데이터포털 호출 한도 초과(사유 {reason})")
            if reason in _GONE_REASONS:
                raise DataGoKrFormatError(
                    f"공공데이터포털 서비스 없음(사유 {reason}) — 엔드포인트가 바뀌었습니다")
            raise DataGoKrUnavailable(f"공공데이터포털 게이트웨이 오류(사유 {reason})")
        if status >= 500:
            raise DataGoKrUnavailable(f"출처 HTTP {status}")
        if status >= 400:
            raise DataGoKrFormatError(f"출처 HTTP {status}")

    async def _backoff(self, attempt: int) -> None:
        base = self._settings.data_api_retry_base_delay_ms / 1000
        await asyncio.sleep(base * (2 ** attempt) + random.uniform(0, base))

    async def _request[T](self, api: str, url: str,
                          read: Callable[[str], T]) -> tuple[T, str, int]:
        """재시도할 수 있는 오류만 다시 시도한다. 오류 문구에서 인증키를 지운다."""
        last: DataGoKrError | None = None
        for attempt in range(self._settings.data_api_retry_max_attempts):
            try:
                body, status = await self._get(url, api)
                self._check(body, status)
                return read(body), body, status
            except DataGoKrError as exc:
                exc.args = (self._scrub(str(exc)),)
                if isinstance(exc, DataGoKrRateLimited):
                    self._gate.block(api)
                if not exc.retryable:
                    raise
                last = exc
                if attempt + 1 < self._settings.data_api_retry_max_attempts:
                    await self._backoff(attempt)
        assert last is not None
        raise last

    async def _fetch[T](self, api: str, endpoint: str, ref: str, path: str, params: dict[str, str],
                        read: Callable[[str], T]) -> Fetched[T]:
        url = self._url(path, params)
        result, body, status = await self._request(api, url, read)
        return Fetched(result, endpoint, ref, body, status, result_code(body))

    # ── 공개 ────────────────────────────────────────────────────────

    async def fetch_trades(self, lawd_cd: str, ym: str, page: int) -> Fetched[TradePage]:
        """시·군·구(5자리)의 계약 월(`YYYYMM`) 한 쪽(1,000행). 순번은 그 달의 쪽을 모두 받은 뒤
        `trade_parse.number_trades`로 매긴다 — 같은 키의 행이 쪽을 건너 온다(R9-4)."""
        params = {"LAWD_CD": lawd_cd, "DEAL_YMD": ym, "pageNo": str(page), "numOfRows": str(ROWS)}

        def read(body: str) -> TradePage:
            return parse_trades(body, lawd_cd=lawd_cd, ym=ym)

        return await self._fetch("trade", "trade", f"{lawd_cd}/{ym}/p{page}", TRADE_PATH, params,
                                 read)

    async def fetch_regions(self, page: int) -> Fetched[RegionPage]:
        """법정동코드 전국 목록의 한 쪽(1,000행). 전국은 약 21쪽이다."""
        params = {"type": "json", "pageNo": str(page), "numOfRows": str(ROWS)}
        return await self._fetch("region", "region", f"regions/p{page}", REGION_PATH, params,
                                 parse_regions)

    async def fetch_complex_list(self, bjd_code: str) -> Fetched[ComplexListPage]:
        """법정동의 단지 목록(한 쪽 — 받은 수가 전체와 다르면 형식 오류)."""
        params = {"bjdCode": bjd_code, "pageNo": "1", "numOfRows": str(ROWS)}
        return await self._fetch("kapt", "complex_list", bjd_code, COMPLEX_LIST_PATH, params,
                                 parse_complex_list)

    async def fetch_complex_basis(self, kapt_code: str) -> Fetched[ComplexBasis | None]:
        """단지 하나의 기본 정보. 없는 코드면 결과가 None이다."""
        return await self._fetch("kapt", "complex_basis", kapt_code, COMPLEX_BASIS_PATH,
                                 {"kaptCode": kapt_code}, parse_complex_basis)
