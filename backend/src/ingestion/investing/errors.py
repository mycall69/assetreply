"""가상자산 출처 오류 (007 FR-020).

**종류를 나누는 이유는 할 일이 다르기 때문이다.** 차단(`blocked`)은 기다려도 풀리지 않아 설정을
고쳐야 하고, 형식 오류(`format`)는 출처가 응답 모양을 바꾼 것이라 어댑터를 고쳐야 하고, 네트워크
오류(`network`)는 다시 시도하면 된다. 수집 작업의 실패 사유는 `kind`를 앞에 둔다 — 화면이 사유별로
다른 문구를 낸다.

출처 응답 본문과 요청 헤더를 메시지에 싣지 않는다(FR-019) — 사용자 에이전트 값이 로그에 남는다.
"""

from __future__ import annotations

from typing import ClassVar


class InvestingError(Exception):
    """가상자산 출처 오류의 뿌리."""

    kind: ClassVar[str] = "network"


class InvestingBlocked(InvestingError):
    """출처가 접근을 막았다(403). 다시 시도해도 풀리지 않는다 — 바로 실패한다(research R7-1)."""

    kind = "blocked"


class InvestingFormatError(InvestingError):
    """응답 모양이 예상과 다르다. **그 행만 버리지 않는다** — 그날이 출처 결측으로 위장된다(analyze
    M2)."""

    kind = "format"


class InvestingNetworkError(InvestingError):
    """연결 실패·시간 초과, 또는 429·5xx가 재시도 끝까지 이어졌다."""

    kind = "network"
