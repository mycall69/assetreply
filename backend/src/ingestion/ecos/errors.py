"""ECOS 어댑터 오류 계층 (T024).

출처가 오류를 HTTP 200으로 반환하므로 본문 판별이 필수다. 상태 코드만 보면 오류를
성공으로 오인해 빈 데이터를 저장하게 된다 (contracts/ecos-adapter.md).
"""

from __future__ import annotations


class SourceError(Exception):
    """데이터 소스 오류의 기반. 기본적으로 재시도 대상이다."""

    retryable: bool = True


class SourceAuthError(SourceError):
    """인증키 오류. 재시도해도 달라지지 않으므로 즉시 중단한다."""

    retryable = False


class SourceRateLimited(SourceError):
    """호출 한도 초과. 지수 백오프 후 재시도한다 (FR-007, FR-012)."""


class SourceUnavailable(SourceError):
    """응답이 JSON이 아니다 — 차단 페이지 또는 점검 안내.

    JSON 파싱 실패와 구분해 기록해야 원인을 나중에 추적할 수 있다.
    """


class SourceResponseTruncated(SourceError):
    """출처가 요청 구간의 일부만 돌려줬다.

    응답의 전체 건수(`list_total_count`)가 실제 수신 행 수보다 크면 1회 요청 행 한도에
    걸린 것이다. 재시도해도 같으므로 청크 크기를 줄여야 한다.

    **조용히 넘어가면 데이터가 유실된 채로 커버리지만 갱신되어**, 이후 재수집도 하지
    않게 된다 (헌법 원칙 V).
    """

    retryable = False


class ItemMappingChanged(SourceError):
    """출처의 통화 항목 식별 체계가 바뀌었고 재탐색도 실패했다.

    잘못된 통화의 값을 저장하는 것보다 중단이 낫다 (FR-015).
    """

    retryable = False
