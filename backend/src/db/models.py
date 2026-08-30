"""ORM 모델 (T019) — data-model.md의 논리 스키마를 SQLAlchemy로 구현한다.

헌법 원칙 VI: 금액·비율은 `Numeric(asdecimal=True)`로 선언한다. `Float` 사용 금지.
헌법 v4.0.0: DB 종속 문법(생성 컬럼·부분 인덱스)을 쓰지 않는다.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# 금액·비율 타입 — research R7이 정한 정밀도
RATE = Numeric(18, 6, asdecimal=True)
SPREAD = Numeric(9, 6, asdecimal=True)
TS = DateTime(timezone=False)


class Base(DeclarativeBase):
    """모든 ORM 모델의 기반. Alembic이 이 메타데이터로 마이그레이션을 생성한다."""


class JobStatus(StrEnum):
    """수집 작업 상태 (data-model.md 상태 전이)."""

    RUNNING = "running"
    SUCCEEDED = "succeeded"
    PARTIAL = "partial"
    FAILED = "failed"


class Currency(Base):
    """통화 마스터. 고시 단위를 값과 분리해 둔다 (FR-007)."""

    __tablename__ = "currency"

    code: Mapped[str] = mapped_column(String(3), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(50))
    quote_unit: Mapped[int] = mapped_column(SmallInteger)
    source_item_code: Mapped[str] = mapped_column(String(20))
    # 출처가 실제로 값을 제공하기 시작한 날 — 수집 중 발견해 기록한다 (research R3)
    first_available_date: Mapped[dt.date | None] = mapped_column(Date, nullable=True)


class FxRate(Base):
    """환율 시계열 레코드.

    `quote_unit`을 행에 복제하는 이유는, 출처가 고시 단위를 바꾸더라도 과거 행의 값이
    어떤 단위로 해석되어야 하는지 보존하기 위해서다 (헌법 원칙 V — 값의 의미 고정).
    """

    __tablename__ = "fx_rate"

    currency_code: Mapped[str] = mapped_column(
        String(3), ForeignKey("currency.code"), primary_key=True)
    quote_date: Mapped[dt.date] = mapped_column(Date, primary_key=True)
    base_rate: Mapped[Decimal] = mapped_column(RATE)
    quote_unit: Mapped[int] = mapped_column(SmallInteger)
    source: Mapped[str] = mapped_column(String(30))
    ingested_at: Mapped[dt.datetime] = mapped_column(TS, server_default=func.now())
    updated_at: Mapped[dt.datetime] = mapped_column(
        TS, server_default=func.now(), onupdate=func.now())


class FxRawResponse(Base):
    """원본 응답 기록. 기한 없이 보관한다 (FR-004a)."""

    __tablename__ = "fx_raw_response"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    currency_code: Mapped[str] = mapped_column(String(3), ForeignKey("currency.code"))
    requested_from: Mapped[dt.date] = mapped_column(Date)
    requested_to: Mapped[dt.date] = mapped_column(Date)
    http_status: Mapped[int] = mapped_column(SmallInteger)
    result_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    body: Mapped[str] = mapped_column(Text)
    received_at: Mapped[dt.datetime] = mapped_column(TS, server_default=func.now())
    job_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("fx_collection_job.id"), nullable=True)

    __table_args__ = (
        Index("ix_raw_currency_range", "currency_code", "requested_from", "requested_to"),
        Index("ix_raw_received_at", "received_at"),
    )


class FxCoverage(Base):
    """수집 커버리지. 통화당 한 행.

    "값이 있는지"와 별개로 "어디까지 수집을 시도해 완료했는지"를 기록한다. 이 구분이
    고시 없는 날을 미수집으로 오인해 반복 요청하는 것을 막는다 (FR-006, research R8).
    """

    __tablename__ = "fx_coverage"

    currency_code: Mapped[str] = mapped_column(
        String(3), ForeignKey("currency.code"), primary_key=True)
    covered_from: Mapped[dt.date] = mapped_column(Date)
    covered_through: Mapped[dt.date] = mapped_column(Date)
    last_updated_at: Mapped[dt.datetime] = mapped_column(
        TS, server_default=func.now(), onupdate=func.now())


class FxSpread(Base):
    """스프레드 설정. 통화당 한 행, 시스템 전역 (spec Assumptions).

    시점별 이력을 관리하지 않는다 (FR-026). 조회 결과에 적용된 값이 함께 담겨
    어떤 가정 위의 결과인지 드러난다 (FR-026a).
    """

    __tablename__ = "fx_spread"

    currency_code: Mapped[str] = mapped_column(
        String(3), ForeignKey("currency.code"), primary_key=True)
    cash_buy: Mapped[Decimal] = mapped_column(SPREAD)
    cash_sell: Mapped[Decimal] = mapped_column(SPREAD)
    remit_send: Mapped[Decimal] = mapped_column(SPREAD)
    remit_receive: Mapped[Decimal] = mapped_column(SPREAD)
    updated_at: Mapped[dt.datetime] = mapped_column(
        TS, server_default=func.now(), onupdate=func.now())


class FxCollectionJob(Base):
    """수집 작업 이력.

    실패·부분 성공은 영구 보관하고 성공만 보관 기간 경과 후 정리한다 (FR-038a/b).
    """

    __tablename__ = "fx_collection_job"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    currency_code: Mapped[str] = mapped_column(String(3), ForeignKey("currency.code"))
    range_start: Mapped[dt.date] = mapped_column(Date)
    range_end: Mapped[dt.date] = mapped_column(Date)
    status: Mapped[JobStatus] = mapped_column(Enum(JobStatus, native_enum=False, length=16))
    chunks_total: Mapped[int] = mapped_column(Integer)
    chunks_done: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[dt.datetime] = mapped_column(TS, server_default=func.now())
    finished_at: Mapped[dt.datetime | None] = mapped_column(TS, nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (Index("ix_job_currency_status", "currency_code", "status"),)


class FxCollectionLock(Base):
    """통화별 단일 수집 작업 잠금 (FR-015a, research R6).

    기본 키 INSERT 충돌이 곧 "이미 진행 중"을 뜻한다. 모든 RDBMS에서 동일하게 동작하는
    유일한 이식 가능 수단이며, 생성 컬럼이나 부분 인덱스 같은 DB 종속 문법을 쓰지 않는다.

    `heartbeat_at`은 청크 커밋 때마다 갱신된다. 프로세스가 비정상 종료해 잠금이 남으면
    이 값이 오래된 것을 근거로 회수한다.
    """

    __tablename__ = "fx_collection_lock"

    currency_code: Mapped[str] = mapped_column(
        String(3), ForeignKey("currency.code"), primary_key=True)
    job_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("fx_collection_job.id"))
    acquired_at: Mapped[dt.datetime] = mapped_column(TS, server_default=func.now())
    heartbeat_at: Mapped[dt.datetime] = mapped_column(TS, server_default=func.now())
