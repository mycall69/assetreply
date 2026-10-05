"""공공데이터포털 어댑터 오류 (009 T011, FR-014, research R9-5).

실패 종류는 넷이고 종류마다 할 일이 다르다 — 인증은 설정(인증키·활용신청)을 고치고, 한도는 내일 다시
하고, 형식은 어댑터를 고치고, 연결은 다시 하면 된다. 종류(`kind`)는 작업의 `last_error` 앞머리와
진행 스트림의 `failed.kind`가 된다.

**한도 초과는 재시도하지 않는다.** 포털의 하루 한도(사유 22)든 자체 한도든, 다시 보내면 키가
막힌다(SC-012).
"""

from __future__ import annotations


class DataGoKrError(Exception):
    """공공데이터포털 오류의 기반."""

    kind: str = "network"
    retryable: bool = True


class DataGoKrAuthError(DataGoKrError):
    """인증 실패 — 인증키가 없거나 틀렸거나, 그 자료에 활용신청이 되지 않았다(게이트웨이 사유
    20·30·31·32)."""

    kind = "auth"
    retryable = False


class DataGoKrRateLimited(DataGoKrError):
    """하루 한도 — 자체 계수(설정)가 막았거나 포털이 사유 22를 줬다. 받은 데까지 남기고 멈춘다."""

    kind = "rate_limited"
    retryable = False


class DataGoKrFormatError(DataGoKrError):
    """응답 형식이 예상과 다르다 — 결과 코드 이상, 잘림, 읽을 수 없는 값, 서비스 없음(사유 12 —
    엔드포인트가 바뀜).

    재시도해도 같다. 읽지 못한 행만 버리면 그 달이 거래 없음으로 위장된다(FR-019).
    """

    kind = "format"
    retryable = False


class DataGoKrUnavailable(DataGoKrError):
    """연결 실패·HTTP 5xx·JSON/XML이 아닌 본문(점검 안내 등). 지수 백오프 뒤 다시 시도한다."""

    kind = "network"
    retryable = True
