"""수집 이벤트 값 객체 검증 (T009) — data-model.md `kind` 표.

두 가지가 핵심이다.

1. 9종 `kind`를 모두 표현한다. 특히 `chunk_empty`와 `chunk_failed`가 **분리**되어야
   한다 — 합치면 나중에 시계열에 공백이 생겼을 때 출처의 결측인지 수집 실패인지
   구별할 수 없다 (FR-021).
2. 인증 정보가 어떤 필드에도 담기지 않는다 (FR-020). 차단은 포매터가 아니라 이벤트를
   만드는 지점에서 한다 — 포매터에서 걸러내려면 어떤 필드가 비밀인지 아는 지식이
   두 곳에 흩어진다 (research R3-10).
"""
from __future__ import annotations

import dataclasses
import datetime as dt

import pytest

from src.observability.events import (
    ALL_KINDS,
    CHUNK_EMPTY,
    CHUNK_FAILED,
    CHUNK_REQUESTED,
    CHUNK_STORED,
    JOB_FINISHED,
    JOB_STARTED,
    LOG_SINK_FAILED,
    RATE_LIMITED,
    RETRY,
    CollectionEvent,
)


class Test종류:
    def test_아홉_종류가_정의됐다(self) -> None:
        assert len(ALL_KINDS) == 9

    def test_명세가_정한_이름과_일치한다(self) -> None:
        assert set(ALL_KINDS) == {
            "job_started", "chunk_requested", "chunk_stored", "chunk_empty",
            "chunk_failed", "retry", "rate_limited", "job_finished", "log_sink_failed",
        }

    def test_결측과_실패가_다른_종류다(self) -> None:
        """이 둘을 합치면 시계열 공백의 원인을 되짚을 수 없다 (FR-021)."""
        assert CHUNK_EMPTY != CHUNK_FAILED

    def test_상수가_모두_목록에_있다(self) -> None:
        for k in (JOB_STARTED, CHUNK_REQUESTED, CHUNK_STORED, CHUNK_EMPTY,
                  CHUNK_FAILED, RETRY, RATE_LIMITED, JOB_FINISHED, LOG_SINK_FAILED):
            assert k in ALL_KINDS

    def test_길이가_컬럼_한계_안이다(self) -> None:
        """`kind` 컬럼이 VARCHAR(30)이다."""
        assert all(len(k) <= 30 for k in ALL_KINDS)


class Test값_객체:
    def test_최소_필드만으로_만들_수_있다(self) -> None:
        e = CollectionEvent(job_id=1, currency="USD", kind=JOB_STARTED)
        assert e.chunk_from is None and e.rows_stored is None

    def test_불변이다(self) -> None:
        """사건은 일어난 사실이다. 만든 뒤 바뀌면 두 싱크가 다른 값을 본다."""
        e = CollectionEvent(job_id=1, currency="USD", kind=JOB_STARTED)
        with pytest.raises(dataclasses.FrozenInstanceError):
            e.kind = CHUNK_STORED  # type: ignore[misc]

    def test_알_수_없는_종류를_거부한다(self) -> None:
        with pytest.raises(ValueError, match="알 수 없는 사건 종류"):
            CollectionEvent(job_id=1, currency="USD", kind="무언가")

    def test_구간_사건은_범위를_싣는다(self) -> None:
        e = CollectionEvent(
            job_id=1, currency="USD", kind=CHUNK_STORED,
            chunk_from=dt.date(2024, 1, 1), chunk_to=dt.date(2024, 12, 31),
            rows_stored=261,
        )
        assert e.chunk_from == dt.date(2024, 1, 1)
        assert e.rows_stored == 261

    def test_행_매핑이_컬럼명과_맞는다(self) -> None:
        e = CollectionEvent(
            job_id=7, currency="JPY", kind=CHUNK_FAILED,
            chunk_from=dt.date(2024, 1, 1), chunk_to=dt.date(2024, 1, 31),
            detail="응답 오류",
        )
        row = e.as_row()
        assert row == {
            "job_id": 7, "currency_code": "JPY", "kind": "chunk_failed",
            "chunk_from": dt.date(2024, 1, 1), "chunk_to": dt.date(2024, 1, 31),
            "rows_stored": None, "detail": "응답 오류",
        }

    def test_로그_필드가_사람이_읽을_수_있다(self) -> None:
        e = CollectionEvent(job_id=1, currency="USD", kind=CHUNK_STORED, rows_stored=261)
        fields = e.as_log_fields()
        assert fields["currency"] == "USD"
        assert fields["kind"] == "chunk_stored"
        assert fields["rows_stored"] == 261


class Test비밀값_차단:
    def test_인증_필드를_받지_않는다(self) -> None:
        """이벤트에 키를 담을 자리가 애초에 없어야 한다 (FR-020)."""
        names = {f.name for f in dataclasses.fields(CollectionEvent)}
        assert not any(
            t in n.lower() for n in names
            for t in ("key", "secret", "token", "password", "auth", "credential")
        )

    def test_detail에_들어온_인증_키를_가린다(self) -> None:
        """출처 오류 메시지에 키가 섞여 들어오는 경로를 막는다."""
        e = CollectionEvent(
            job_id=1, currency="USD", kind=CHUNK_FAILED,
            detail="요청 실패: https://ecos.bok.or.kr/api/X/ABCD1234EFGH5678/json",
        )
        assert "ABCD1234EFGH5678" not in (e.detail or "")
        assert "***" in (e.detail or "")

    def test_정상_메시지는_건드리지_않는다(self) -> None:
        e = CollectionEvent(job_id=1, currency="USD", kind=CHUNK_FAILED,
                            detail="응답이 유효하지 않습니다")
        assert e.detail == "응답이 유효하지 않습니다"
