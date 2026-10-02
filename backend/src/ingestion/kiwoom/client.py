"""키움 REST API 클라이언트 (T010) — 006 research R6-1·R6-2·R6-3.

필요한 호출은 둘뿐이다 — 토큰 발급과 목록 조회. 공식 클라이언트를 쓰지 않는다. 그쪽은 토큰을
**파일에 저장하는** 경로가 있어 FR-061(토큰을 남기지 않는다)과 부딪힌다.

- **토큰은 메모리에만** 둔다. 만료 10분 전에 새로 받는다
- **연속조회**는 응답 헤더의 `cont-yn`·`next-key`로 잇는다(실측으로는 단위마다 한 쪽에 끝난다)
- 돌려주는 쪽(`KiwoomPage`)에는 **본문과 연속조회 정보만** 담는다. 헤더를 넘기면 원본 보관에
  인증 헤더가 섞인다(FR-061)
- 동기 호출을 쓰지 않는다(헌법 원칙 I)
"""

from __future__ import annotations

import asyncio
import datetime as dt
import json
from collections.abc import Callable
from dataclasses import dataclass
from types import TracebackType
from typing import Final, Self

import aiohttp

from src.config.settings import Settings
from src.ingestion.kiwoom.errors import (
    KiwoomAuthError,
    KiwoomError,
    KiwoomInvalidResponse,
    KiwoomUnavailable,
    classify_failure,
    is_token_problem,
)

DOMAINS: Final = {"real": "https://api.kiwoom.com", "mock": "https://mockapi.kiwoom.com"}
TOKEN_PATH: Final = "/oauth2/token"

#: 단위 → (api-id, 경로, 요청 본문). research R6-2의 단위 표(T005 실측으로 5개).
UNIT_REQUESTS: Final[dict[str, tuple[str, str, dict[str, str]]]] = {
    "KOSPI": ("ka10099", "/api/dostk/stkinfo", {"mrkt_tp": "0"}),
    "KOSDAQ": ("ka10099", "/api/dostk/stkinfo", {"mrkt_tp": "10"}),
    "NYSE": ("usa10099", "/api/us/stkinfo", {"stex_tp": "NY"}),
    "NASDAQ": ("usa10099", "/api/us/stkinfo", {"stex_tp": "ND"}),
    "AMEX": ("usa10099", "/api/us/stkinfo", {"stex_tp": "NA"}),
}
US_UNITS: Final = frozenset({"NYSE", "NASDAQ", "AMEX"})

#: 토큰 만료 시각은 한국 시간으로 온다(`expires_dt`, `YYYYMMDDHHMMSS`).
_KST: Final = dt.timezone(dt.timedelta(hours=9))
_REFRESH_BUFFER: Final = dt.timedelta(minutes=10)
_JSON_HEADER: Final = {"Content-Type": "application/json;charset=UTF-8"}
_TIMEOUT_SECONDS: Final = 30


@dataclass(frozen=True, slots=True)
class KiwoomPage:
    """목록 한 쪽. **헤더를 담지 않는다** — 인증 헤더가 섞이면 원본 보관에 토큰이 남는다."""

    page_no: int
    status: int
    body: str
    cont_yn: str
    next_key: str


def _utc_now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def _as_json(raw: str) -> object:
    try:
        parsed: object = json.loads(raw)
    except ValueError:
        return None
    return parsed


class KiwoomClient:
    """목록 조회 어댑터. `async with`로 세션 수명을 관리한다."""

    def __init__(
        self,
        settings: Settings,
        *,
        session: aiohttp.ClientSession | None = None,
        now: Callable[[], dt.datetime] = _utc_now,
    ) -> None:
        self._settings = settings
        self._session = session
        self._owns_session = session is None
        self._now = now
        self._token: str | None = None
        self._token_expires: dt.datetime | None = None

    def __repr__(self) -> str:
        # 키·시크릿·토큰을 싣지 않는다(FR-060).
        return f"KiwoomClient(mode={self._settings.kiwoom_mode!r})"

    @property
    def base_url(self) -> str:
        return DOMAINS[self._settings.kiwoom_mode]

    async def __aenter__(self) -> Self:
        if self._session is None:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=_TIMEOUT_SECONDS))
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if self._owns_session and self._session is not None:
            await self._session.close()
            self._session = None
        self._token = None
        self._token_expires = None

    @staticmethod
    def request_for(unit: str) -> tuple[str, str, dict[str, str]]:
        """단위의 요청. 모르는 단위는 거절한다 — 조용히 다른 시장을 받으면 목록이 뒤바뀐다."""
        try:
            return UNIT_REQUESTS[unit]
        except KeyError as exc:
            raise ValueError(f"알 수 없는 목록 단위입니다: {unit}") from exc

    async def fetch_unit(self, unit: str) -> list[KiwoomPage]:
        """한 단위의 **모든 쪽**을 받는다. 중간에 실패하면 예외를 낸다 — 일부만 돌려주지 않는다."""
        if not self._settings.kiwoom_credentials_present:
            raise KiwoomAuthError("목록 출처의 인증 정보가 설정되지 않았습니다.", missing=True)
        api_id, path, body = self.request_for(unit)
        delay = (self._settings.kiwoom_us_page_delay_seconds if unit in US_UNITS
                 else self._settings.kiwoom_kr_page_delay_seconds)

        pages: list[KiwoomPage] = []
        cont_yn, next_key = "N", ""
        while True:
            headers = {"api-id": api_id}
            if pages:
                headers["cont-yn"] = cont_yn
                headers["next-key"] = next_key
            status, text, cont_yn, next_key = await self._call_with_token(path, headers, body)
            pages.append(KiwoomPage(len(pages) + 1, status, text, cont_yn, next_key))
            if cont_yn != "Y":
                return pages
            await asyncio.sleep(delay)

    # ── 내부 ──────────────────────────────────────────────────────────

    async def _call_with_token(
        self, path: str, headers: dict[str, str], body: dict[str, str]
    ) -> tuple[int, str, str, str]:
        """토큰을 실어 부른다. 토큰 문제면 **한 번만** 새로 받아 다시 부른다."""
        for retried in (False, True):
            token = await self._ensure_token()
            try:
                return await self._post(
                    path, {**headers, "authorization": f"Bearer {token}"}, body)
            except KiwoomError as exc:
                if retried or not is_token_problem(exc):
                    raise
                self._token = None
                self._token_expires = None
        raise AssertionError("도달하지 않는다")  # pragma: no cover

    async def _ensure_token(self) -> str:
        now = self._now()
        if (self._token is not None and self._token_expires is not None
                and now < self._token_expires - _REFRESH_BUFFER):
            return self._token
        _, text, _, _ = await self._post(TOKEN_PATH, {}, {
            "grant_type": "client_credentials",
            "appkey": self._settings.kiwoom_app_key.reveal(),
            "secretkey": self._settings.kiwoom_app_secret.reveal(),
        })
        parsed = _as_json(text)
        token = parsed.get("token") if isinstance(parsed, dict) else None
        if not isinstance(token, str) or not token:
            raise KiwoomInvalidResponse("목록 출처가 접근 토큰을 주지 않았습니다.")
        expires = parsed.get("expires_dt") if isinstance(parsed, dict) else None
        self._token = token
        self._token_expires = self._parse_expiry(expires, now)
        return token

    @staticmethod
    def _parse_expiry(raw: object, now: dt.datetime) -> dt.datetime:
        """만료 시각(KST)을 UTC로. 모르면 지금으로 둔다 — 다음 호출에서 새로 받는다."""
        if isinstance(raw, str):
            try:
                return dt.datetime.strptime(raw, "%Y%m%d%H%M%S").replace(tzinfo=_KST)
            except ValueError:
                pass
        return now

    async def _post(
        self, path: str, headers: dict[str, str], body: dict[str, str]
    ) -> tuple[int, str, str, str]:
        """한 번 부른다. **네트워크 실패만** 설정한 횟수까지 다시 시도한다."""
        if self._session is None:
            raise KiwoomUnavailable("클라이언트 세션이 열려 있지 않습니다.")
        attempts = self._settings.kiwoom_max_retries
        last: KiwoomError = KiwoomUnavailable("목록 출처에 연결하지 못했습니다.")
        for attempt in range(attempts):
            try:
                async with self._session.post(
                    f"{self.base_url}{path}", json=body, headers={**_JSON_HEADER, **headers},
                ) as response:
                    status = response.status
                    text = await response.text()
                    cont_yn = response.headers.get("cont-yn") or "N"
                    next_key = response.headers.get("next-key") or ""
            except (aiohttp.ClientError, TimeoutError) as exc:
                last = KiwoomUnavailable("목록 출처에 연결하지 못했습니다.")
                last.__cause__ = exc
            else:
                failure = classify_failure(status, _as_json(text))
                if failure is None:
                    return status, text, cont_yn, next_key
                if not isinstance(failure, KiwoomUnavailable):
                    raise failure
                last = failure
            if attempt + 1 < attempts:
                await asyncio.sleep(min(2.0 ** attempt, 8.0))
        raise last
