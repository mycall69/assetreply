"""Npay 부동산 출처 오류 (010 반복 3, FR-029).

**종류를 나누는 이유는 할 일이 다르기 때문이다.** 차단(`blocked`)은 기다려도 풀리지 않아 설정(사용자
에이전트)을 고쳐야 하고, 요청 제한(`rate_limited`)은 시간이 지나면 풀리고, 형식 오류(`format`)는
출처가 응답 모양을 바꾼 것이라 어댑터를 고쳐야 한다. 어느 것이든 단지 링크는 네이버 검색으로
물러나고, 실패는 저장하지 않아 다음 요청에서 다시 찾는다.

출처 응답 본문과 요청 헤더를 메시지에 싣지 않는다 — 사용자 에이전트 값이 로그에 남는다.
"""

from __future__ import annotations

from typing import ClassVar


class NaverLandError(Exception):
    """Npay 부동산 출처 오류의 뿌리."""

    kind: ClassVar[str] = "network"


class NaverLandBlocked(NaverLandError):
    """출처가 접근을 막았다(403). 다시 시도해도 풀리지 않는다 — 바로 실패한다."""

    kind = "blocked"


class NaverLandRateLimited(NaverLandError):
    """요청 제한(429)이 재시도 끝까지 이어졌다 — 짧은 시간에 여러 번 부른 것이다."""

    kind = "rate_limited"


class NaverLandFormatError(NaverLandError):
    """응답 모양이 예상과 다르다(또는 4xx). 어댑터를 고쳐야 한다."""

    kind = "format"


class NaverLandNetworkError(NaverLandError):
    """연결 실패·시간 초과, 또는 5xx가 재시도 끝까지 이어졌다."""

    kind = "network"
