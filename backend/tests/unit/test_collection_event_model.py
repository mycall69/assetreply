"""`fx_collection_event` 스키마 검증 (T005) — data-model.md 1절.

컬럼 제약이 명세와 어긋나면 마이그레이션이 만들어 낸 테이블도 함께 어긋난다.
ORM 정의를 정본으로 보고 여기서 대조한다.
"""
from __future__ import annotations

from sqlalchemy import inspect

from src.db.models import FxCollectionEvent, FxCollectionJob


def _col(model: type, name: str):
    return inspect(model).columns[name]


class Test컬럼_정의:
    def test_테이블명이_fx_collection_event다(self) -> None:
        assert FxCollectionEvent.__tablename__ == "fx_collection_event"

    def test_필수_컬럼이_모두_있다(self) -> None:
        cols = set(inspect(FxCollectionEvent).columns.keys())
        assert cols == {
            "id", "job_id", "currency_code", "kind",
            "chunk_from", "chunk_to", "rows_stored", "detail", "occurred_at",
        }

    def test_id가_기본키다(self) -> None:
        assert _col(FxCollectionEvent, "id").primary_key is True

    def test_job_id와_currency_code는_NOT_NULL이다(self) -> None:
        """둘 다 조회·정리의 기준이라 비어 있으면 사건을 어디에도 귀속시킬 수 없다."""
        assert _col(FxCollectionEvent, "job_id").nullable is False
        assert _col(FxCollectionEvent, "currency_code").nullable is False

    def test_kind는_NOT_NULL이고_길이가_30이다(self) -> None:
        kind = _col(FxCollectionEvent, "kind")
        assert kind.nullable is False
        assert kind.type.length == 30

    def test_currency_code는_3자다(self) -> None:
        assert _col(FxCollectionEvent, "currency_code").type.length == 3

    def test_구간과_건수와_설명은_NULL_허용이다(self) -> None:
        """작업 시작·종료처럼 구간이 없는 사건이 있다."""
        for name in ("chunk_from", "chunk_to", "rows_stored", "detail"):
            assert _col(FxCollectionEvent, name).nullable is True, name

    def test_occurred_at은_NOT_NULL이고_기본값이_있다(self) -> None:
        col = _col(FxCollectionEvent, "occurred_at")
        assert col.nullable is False
        assert col.server_default is not None


class Test외래키:
    def test_job_id가_작업을_가리킨다(self) -> None:
        fks = {fk.column.table.name for fk in _col(FxCollectionEvent, "job_id").foreign_keys}
        assert "fx_collection_job" in fks

    def test_currency_code가_통화를_가리킨다(self) -> None:
        fks = {fk.column.table.name for fk in
               _col(FxCollectionEvent, "currency_code").foreign_keys}
        assert "currency" in fks


class Test인덱스:
    def test_작업별_시간순_조회_인덱스가_있다(self) -> None:
        idx = {tuple(c.name for c in i.columns) for i in FxCollectionEvent.__table__.indexes}
        assert ("job_id", "occurred_at") in idx

    def test_통화별_정리_인덱스가_있다(self) -> None:
        """보관 범위 정리가 통화별로 일어나므로 조인 없이 찾을 수 있어야 한다."""
        idx = {tuple(c.name for c in i.columns) for i in FxCollectionEvent.__table__.indexes}
        assert ("currency_code", "job_id") in idx


class Test작업_테이블_확장:
    def test_events_dropped가_추가됐다(self) -> None:
        assert "events_dropped" in inspect(FxCollectionJob).columns.keys()

    def test_events_dropped는_NOT_NULL이고_기본이_0이다(self) -> None:
        """기본이 없으면 기존 행이 NULL이 되어 '기록 완전함'과 구별되지 않는다."""
        col = _col(FxCollectionJob, "events_dropped")
        assert col.nullable is False
        assert col.default is not None and col.default.arg == 0

    def test_기존_컬럼이_그대로다(self) -> None:
        cols = set(inspect(FxCollectionJob).columns.keys())
        assert {"id", "currency_code", "range_start", "range_end", "status",
                "chunks_total", "chunks_done", "started_at", "finished_at",
                "last_error"} <= cols
