"""뉴스 출처 오류 (014 T072) — FR-024, contracts A5.

**종류를 나누는 이유는 화면의 까닭이 다르기 때문이다.** 연결 실패(`connection`)와 요청
제한(`rate_limited`)은
시간이 지나면 풀리고, 차단(`blocked`)은 사용자 에이전트 설정을 고쳐야 하고, 읽지
못함(`parse_empty`)은 출처 화면이
바뀌어 어댑터를 고쳐야 한다. **기사를 하나도 읽지 못한 것은 실패다** — 0건을 "뉴스 없음"으로
돌려주면 파서가 깨진
줄 아무도 모른다(FR-024).

출처 응답 본문과 요청 머리를 메시지에 싣지 않는다.
"""

from __future__ import annotations

from typing import ClassVar, Literal

FailureReason = Literal["connection", "blocked", "rate_limited", "parse_empty", "invalid_body"]


class NewsError(Exception):
    """뉴스 출처 오류의 뿌리."""

    reason: ClassVar[FailureReason] = "connection"


class NewsConnectionError(NewsError):
    """연결하지 못했다(연결 오류·시간 초과·5xx·그 밖의 상태)."""

    reason = "connection"


class NewsBlocked(NewsError):
    """출처가 접근을 막았다(403). 다시 시도해도 풀리지 않는다."""

    reason = "blocked"


class NewsRateLimited(NewsError):
    """요청 제한(429). 브라우저형 사용자 에이전트가 없어도 이것이다(R14-13 실측)."""

    reason = "rate_limited"


class NewsParseEmpty(NewsError):
    """기사를 하나도 읽지 못했다 — 목록 칸·상태 키가 없거나 비었다. 출처 화면이 바뀐 신호다."""

    reason = "parse_empty"


class NewsInvalidBody(NewsError):
    """본문을 읽을 수 없다(JSON이 아니거나 깨졌다)."""

    reason = "invalid_body"
