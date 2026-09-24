"""수집 이벤트 값 객체와 종류 상수 (T010) — data-model.md `kind` 표.

**이벤트를 만드는 지점은 하나다.** 화면 기록과 파일 로그가 각자 문자열을 만들면 시간이
지나며 내용이 갈라진다. 사건을 값으로 먼저 만들고 표현만 달리해야 FR-018이 요구하는
"같은 사건에서 생성"이 구조로 보장된다.

비밀값 차단도 여기서 한다 (FR-020, research R3-10). 포매터에서 걸러내려면 어떤 필드가
비밀인지 아는 지식이 두 곳에 흩어지고, 새 싱크가 늘 때마다 같은 처리를 반복해야 한다.
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass, field, fields

# ── 사건 종류 (9종) ────────────────────────────────────────────────
JOB_STARTED = "job_started"
CHUNK_REQUESTED = "chunk_requested"
CHUNK_STORED = "chunk_stored"
#: 출처가 값을 제공하지 않은 구간(휴일 등). **`CHUNK_FAILED`와 반드시 구별한다** —
#: 합치면 나중에 시계열에 공백이 생겼을 때 원인이 결측인지 실패인지 알 수 없다 (FR-021).
CHUNK_EMPTY = "chunk_empty"
CHUNK_FAILED = "chunk_failed"
RETRY = "retry"
RATE_LIMITED = "rate_limited"
JOB_FINISHED = "job_finished"
#: 파일 기록에 실패했음을 DB에 남기는 사건 (FR-018b, research R3-4).
LOG_SINK_FAILED = "log_sink_failed"

ALL_KINDS: frozenset[str] = frozenset({
    JOB_STARTED, CHUNK_REQUESTED, CHUNK_STORED, CHUNK_EMPTY, CHUNK_FAILED,
    RETRY, RATE_LIMITED, JOB_FINISHED, LOG_SINK_FAILED,
})

# 키처럼 보이는 토큰: 16자 이상이면서 영문과 숫자가 섞인 연속 문자열.
# **특정 출처의 URL 형태를 알지 않는다** — 그 지식은 어댑터 안에만 있어야 한다
# (헌법 원칙 II). 경로에 키를 담는 출처든 질의 문자열에 담는 출처든 같은 규칙으로
# 걸린다.
_KEY_LIKE = re.compile(r"\b(?=[A-Za-z0-9]*[A-Za-z])(?=[A-Za-z0-9]*\d)[A-Za-z0-9]{16,}\b")


def mask_secrets(text: str | None) -> str | None:
    """문자열에 섞인 인증 키로 보이는 토큰을 가린다.

    출처가 돌려준 오류 메시지에 요청 URL이 통째로 섞여 들어오는 경로를 끊는다
    (FR-020). 사람이 쓴 정상 메시지는 이 패턴에 걸리지 않는다.

    해시처럼 키가 아닌 토큰까지 가려질 수 있으나, 로그에서 해시가 가려지는 것은
    해가 없다. 반대 방향의 실수—키가 그대로 남는 것—가 훨씬 비싸다.
    """
    if text is None:
        return None
    return _KEY_LIKE.sub("***", text)


@dataclass(frozen=True, slots=True)
class CollectionEvent:
    """수집 과정에서 일어난 하나의 사건.

    **불변이다.** 사건은 일어난 사실이라 만든 뒤 바뀌어서는 안 된다. 가변이면 두 싱크가
    서로 다른 값을 볼 수 있고, 그 어긋남은 오류를 내지 않아 발견되지 않는다.
    """

    job_id: int
    currency: str
    kind: str
    chunk_from: dt.date | None = None
    chunk_to: dt.date | None = None
    rows_stored: int | None = None
    detail: str | None = None
    occurred_at: dt.datetime = field(default_factory=dt.datetime.now)

    def __post_init__(self) -> None:
        if self.kind not in ALL_KINDS:
            raise ValueError(f"알 수 없는 사건 종류입니다: {self.kind}")
        # frozen이라 우회 대입이 필요하다. 생성 시점에 한 번만 일어난다.
        object.__setattr__(self, "detail", mask_secrets(self.detail))

    def as_row(self) -> dict[str, object]:
        """DB 적재용 매핑. 키는 `fx_collection_event`의 컬럼명이다."""
        return {
            "job_id": self.job_id,
            "currency_code": self.currency,
            "kind": self.kind,
            "chunk_from": self.chunk_from,
            "chunk_to": self.chunk_to,
            "rows_stored": self.rows_stored,
            "detail": self.detail,
        }

    def as_log_fields(self) -> dict[str, object]:
        """파일 로그용 필드. `None`은 빼서 한 줄을 짧게 유지한다."""
        out: dict[str, object] = {"job_id": self.job_id, "currency": self.currency,
                                  "kind": self.kind}
        for name in ("chunk_from", "chunk_to", "rows_stored", "detail"):
            value = getattr(self, name)
            if value is not None:
                out[name] = value.isoformat() if isinstance(value, dt.date) else value
        return out

    def message(self) -> str:
        """파일 로그의 사람이 읽는 한 줄."""
        span = ""
        if self.chunk_from is not None and self.chunk_to is not None:
            span = f" {self.chunk_from}~{self.chunk_to}"
        return f"[{self.currency}] {self.kind}{span}"


def event_field_names() -> frozenset[str]:
    """정적 검사용. 비밀값을 담을 필드가 없는지 확인하는 데 쓴다 (T075)."""
    return frozenset(f.name for f in fields(CollectionEvent))
