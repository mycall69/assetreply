"""키움 응답 실패 판정 (T010) — 006 research R6-1·R6-3.

**HTTP 200인 실패**가 가장 큰 함정이다. 실제 오류 응답은 HTTP 200에 `return_code: 3`(넓은
분류)이고, 세부 코드는 `return_msg`의 `[8001:…]`에만 있다(T005 실측). 상태 코드만 보면 실패를
빈 목록으로 읽어 전 종목을 "목록에서 빠짐"으로 바꾸고, `return_code`만 보면 인증 실패와 한도
초과를 가를 수 없다.

실패를 **넷으로 나누는** 이유는 다시 시도할지가 다르기 때문이다(R6-3).

| 종류 | 다시 시도 |
|------|-----------|
| `auth` | 하지 않는다 — 설정을 고치기 전에는 낫지 않는다 |
| `rate_limit` | 그 자리에서 하지 않는다 — 간격을 두고 다음 갱신에서 |
| `network` | 한 요청 안에서 설정한 횟수까지 |
| `invalid` | 하지 않는다 |

오류 메시지에 출처 응답 문구를 싣지 않는다. 출처가 문구를 바꾸면 우리 기록이 따라 바뀌고,
요청에 실은 값이 섞여 돌아올 수 있다(FR-060).
"""

from __future__ import annotations

import re

#: `return_msg` 안의 세부 코드 — `"인증에 실패했습니다[8001:App Key와 …]"`.
_DETAIL = re.compile(r"\[(\d{3,5}):")

#: 인증 정보·토큰·모드 불일치·단말기 인증·모의 미지원. 설정을 고치기 전에는 낫지 않는다.
AUTH_CODES = frozenset({
    8001, 8002, 8011, 8012,                    # 앱 키·시크릿
    8003, 8005, 8006, 8009, 8015, 8016,        # 접근 토큰
    8030, 8031,                                # 실전·모의 모드 불일치
    8010, 8040, 8050, 8103,                    # 단말기 인증
    8104,                                      # 모의투자 미지원 API
})
#: 토큰만 다시 받으면 나을 수 있는 코드. 한 번은 토큰을 새로 받아 다시 부른다.
TOKEN_CODES = frozenset({8003, 8005, 8006, 8009, 8015, 8016})
RATE_LIMIT_CODES = frozenset({1700, 1701, 1702})


class KiwoomError(Exception):
    """목록 출처 실패의 뿌리. `reason`은 화면이 사유를 말할 때 쓴다(contracts `lists[].reason`)."""

    kind = "invalid"
    reason = "invalid"

    def __init__(self, message: str, *, detail_code: int | None = None) -> None:
        super().__init__(message)
        self.detail_code = detail_code


class KiwoomAuthError(KiwoomError):
    kind = "auth"
    reason = "auth_failed"

    def __init__(self, message: str, *, detail_code: int | None = None,
                 missing: bool = False) -> None:
        super().__init__(message, detail_code=detail_code)
        # 인스턴스 속성으로 덮는다 — "인증 정보 미설정"과 "인증 실패"는 할 일이 다르다.
        self.reason = "auth_missing" if missing else "auth_failed"


class KiwoomRateLimited(KiwoomError):
    kind = "rate_limit"
    reason = "rate_limit"


class KiwoomUnavailable(KiwoomError):
    kind = "network"
    reason = "network"


class KiwoomInvalidResponse(KiwoomError):
    kind = "invalid"
    reason = "invalid"


def detail_code(body: object) -> int | None:
    """세부 코드. `return_msg`의 `[NNNN:]`이 있으면 그것, 없으면 `return_code`."""
    if not isinstance(body, dict):
        return None
    message = body.get("return_msg")
    if isinstance(message, str):
        match = _DETAIL.search(message)
        if match:
            return int(match.group(1))
    code = body.get("return_code")
    if isinstance(code, int) and code != 0:
        return code
    if isinstance(code, str) and code.isdigit() and int(code) != 0:
        return int(code)
    return None


def _succeeded(body: dict[object, object]) -> bool:
    code = body.get("return_code")
    return code is None or code == 0 or code == "0"


def classify_failure(status: int, body: object) -> KiwoomError | None:
    """상태 코드와 본문을 함께 보고 실패를 판정한다. 성공이면 `None`."""
    if status in (401, 403):
        return KiwoomAuthError(f"목록 출처가 인증을 거절했습니다 (HTTP {status}).")
    if status >= 500:
        return KiwoomUnavailable(f"목록 출처가 응답하지 않습니다 (HTTP {status}).")
    if not isinstance(body, dict):
        return KiwoomInvalidResponse(f"목록 출처의 응답이 JSON이 아닙니다 (HTTP {status}).")
    if status == 200 and _succeeded(body):
        return None

    code = detail_code(body)
    suffix = f" (코드 {code})" if code is not None else f" (HTTP {status})"
    if code in RATE_LIMIT_CODES:
        return KiwoomRateLimited(f"목록 출처의 호출 한도를 넘었습니다{suffix}.", detail_code=code)
    if code in AUTH_CODES:
        return KiwoomAuthError(f"목록 출처가 인증을 거절했습니다{suffix}.", detail_code=code)
    return KiwoomInvalidResponse(f"목록 출처가 요청을 처리하지 못했습니다{suffix}.",
                                 detail_code=code)


def is_token_problem(exc: KiwoomError) -> bool:
    """토큰만 새로 받으면 나을 수 있는 실패인가."""
    return isinstance(exc, KiwoomAuthError) and exc.detail_code in TOKEN_CODES
