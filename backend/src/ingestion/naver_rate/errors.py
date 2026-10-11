"""기준금리 출처 오류 (014 반복 2026-10-11d T207) — FR-043, contracts A0.

종류마다 화면의 까닭이 다르다(지표 출처와 같은 다섯 —
`connection`·`rate_limited`·`blocked`·`invalid_body`·`not_found`).
출처 응답 본문과 요청 머리를 메시지에 싣지 않는다.
"""

from __future__ import annotations

from typing import ClassVar, Literal

FailureKind = Literal["connection", "rate_limited", "blocked", "invalid_body", "not_found"]


class PolicyRateError(Exception):
    """기준금리 출처 오류의 뿌리."""

    kind: ClassVar[FailureKind] = "connection"


class PolicyRateConnectionError(PolicyRateError):
    """연결하지 못했다(연결 오류·시간 초과·5xx·그 밖의 4xx)."""

    kind = "connection"


class PolicyRateRateLimited(PolicyRateError):
    """요청 제한(429). 다시 시도하지 않는다 — 다음 바퀴에 다시 부른다."""

    kind = "rate_limited"


class PolicyRateBlocked(PolicyRateError):
    """출처가 막았다(401·403). 기다려도 풀리지 않는다 — 사용자 에이전트 설정."""

    kind = "blocked"


class PolicyRateInvalidBody(PolicyRateError):
    """본문을 읽을 수 없다(JSON 배열이 아니거나 결정 행의 금리를 읽을 수 없다)."""

    kind = "invalid_body"


class PolicyRateNotFound(PolicyRateError):
    """출처에 그 은행이 없다(404·목록에 없음)."""

    kind = "not_found"
