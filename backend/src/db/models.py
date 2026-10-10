"""ORM 모델 (T019) — data-model.md의 논리 스키마를 SQLAlchemy로 구현한다.

헌법 원칙 VI: 금액·비율은 `Numeric(asdecimal=True)`로 선언한다. `Float` 사용 금지.
헌법 v4.0.0: DB 종속 문법(생성 컬럼·부분 인덱스)을 쓰지 않는다.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import (
    CHAR,
    BigInteger,
    Boolean,
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
    UniqueConstraint,
    func,
    text,
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
    # 출처가 아직 확정하지 않은 값인지 (헌법 v5.0.0 원칙 V).
    # 확정값과 구분 없이 저장·표시하는 것은 MUST NOT이다. 기본값을 거짓으로 두는 이유는
    # 마이그레이션 이후 과거 데이터가 통째로 잠정으로 오인되지 않게 하기 위해서다.
    is_provisional: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("0"), default=False)
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
    # 한 해치 응답이 **TEXT(65,535바이트)를 넘는다.** 1964년이 197행에 57KB였고,
    # 거래일이 많은 해(약 260행)는 75KB에 이른다. 청크를 줄이면 호출 수가 늘어 일일
    # 한도를 더 쓰므로, 컬럼을 키우는 쪽이 맞다.
    #
    # `length`를 주면 SQLAlchemy가 MySQL에서 MEDIUMTEXT(16MB)를 고른다. 다른 DB에서는
    # 각자의 대용량 텍스트 타입이 선택되므로 이식성 규약을 지킨다(헌법 DB 운영 규약).
    body: Mapped[str] = mapped_column(Text(length=16_777_215))
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
    # 이 작업에서 DB 적재에 실패한 사건 수 (003 FR-018b). 0보다 크면 이 작업의
    # 기록에 구멍이 있다는 뜻이다. DB 적재 실패를 DB에 남길 수 없는 순환을
    # 건수로 끊는다 — 사건 본문 대신 개수만 남긴다 (research R3-4).
    events_dropped: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0"))

    __table_args__ = (Index("ix_job_currency_status", "currency_code", "status"),)


class FxCollectionEvent(Base):
    """수집 과정에서 일어난 하나의 사건 (003, data-model.md 1절).

    화면 조회와 파일 기록의 **공통 원천**이다. 두 경로가 각자 문자열을 만들면 시간이
    지나며 내용이 갈라지므로, 사건을 값으로 먼저 만들고 표현만 달리한다 (FR-018).

    `currency_code`를 `job_id`와 함께 두는 것은 비정규화다. 작업을 거쳐 조인하면 얻을
    수 있지만 **정리와 조회가 모두 통화별로 일어나** 매번 조인하게 된다 (FR-023).
    """

    __tablename__ = "fx_collection_event"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    job_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("fx_collection_job.id"), nullable=False)
    currency_code: Mapped[str] = mapped_column(
        String(3), ForeignKey("currency.code"), nullable=False)
    # 사건 종류. `observability/events.py`의 9종 상수를 쓴다. Enum 대신 문자열인 이유는
    # 종류가 늘 때 마이그레이션 없이 추가할 수 있어야 하기 때문이다 — 기록은 관찰
    # 수단이라 스키마 변경으로 막을 이유가 없다.
    kind: Mapped[str] = mapped_column(String(30), nullable=False)
    # 구간이 없는 사건(작업 시작·종료)이 있으므로 NULL을 허용한다.
    chunk_from: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    chunk_to: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    rows_stored: Mapped[int | None] = mapped_column(Integer, nullable=True)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    occurred_at: Mapped[dt.datetime] = mapped_column(
        TS, nullable=False, server_default=func.now())

    __table_args__ = (
        # 작업별 시간순 조회
        Index("ix_event_job_time", "job_id", "occurred_at"),
        # 통화별 보관 범위 정리 (research R3-9)
        Index("ix_event_currency_job", "currency_code", "job_id"),
    )


class FxCollectionLock(Base):
    """통화별 단일 수집 작업 잠금 (FR-015a, research R6).

    기본 키 INSERT 충돌이 곧 "이미 진행 중"을 뜻한다. 모든 RDBMS에서 동일하게 동작하는
    유일한 이식 가능 수단이며, 생성 컬럼이나 부분 인덱스 같은 DB 종속 문법을 쓰지 않는다.

    `heartbeat_at`은 청크 커밋 때마다 갱신된다. 프로세스가 비정상 종료해 잠금이 남으면
    이 값이 오래된 것을 근거로 회수한다.
    """

    __tablename__ = "fx_collection_lock"

    # 잠금 범위. `collection`(대량 수집)과 `today_refresh`(오늘 새로고침)가 같은 통화에서
    # 공존해야 하므로 기본 키에 포함한다 (FR-036a, research R2-8). 범위를 키에 넣지 않으면
    # 새로고침이 수집 잠금과 충돌해 백필 도는 동안 오늘 값을 못 받는다.
    scope: Mapped[str] = mapped_column(
        String(20), primary_key=True, default="collection",
        server_default=text("'collection'"))
    currency_code: Mapped[str] = mapped_column(
        String(3), ForeignKey("currency.code"), primary_key=True)
    job_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("fx_collection_job.id"))
    acquired_at: Mapped[dt.datetime] = mapped_column(TS, server_default=func.now())
    heartbeat_at: Mapped[dt.datetime] = mapped_column(TS, server_default=func.now())


# ─────────────────────────── 005: 주식 투자 시뮬레이션 ───────────────────────────
#
# 헌법 시계열 불변식을 따른다 — `(종목, 날짜)` 유니크 키와 upsert, `source`·`ingested_at`,
# 원본과 정규화의 분리 저장, **수정주가와 원주가의 구분**.
#
# `fx_*`와 테이블을 합치지 않는다. 그쪽은 통화 단위이고 여기는 종목 단위라, 한 테이블에
# 섞으면 키 설계가 둘 다 어색해지고 FX 질의가 주식 행을 걸러내야 한다 (005 research R5-7).

#: 주가·배당금 정밀도. 출처가 주는 자릿수를 깎지 않는다 (005 data-model 4절).
PRICE = Numeric(20, 6, asdecimal=True)


class Stock(Base):
    """종목. 사용자가 검색해 고른 것만 들어온다.

    전체 목록을 미리 쌓지 않는 이유는 갱신 시점을 관리해야 하고 그 관리가 틀리면
    **조용히 낡은 목록을 보여주기** 때문이다 (research R5-2).

    `currency`를 종목에 두는 이유는 시장과 통화가 1:1이 아닐 수 있어서다. 종목마다
    확정해 두면 환산 경로가 행 단위로 흔들리지 않는다.
    """

    __tablename__ = "stock"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    market: Mapped[str] = mapped_column(String(8))
    symbol: Mapped[str] = mapped_column(String(32))
    name: Mapped[str] = mapped_column(String(128))
    currency: Mapped[str] = mapped_column(String(3))
    # 출처가 실제로 값을 주기 시작한 날. 수집 중 발견해 기록한다 (FR-005).
    first_available_date: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    ingested_at: Mapped[dt.datetime] = mapped_column(TS, server_default=func.now())

    __table_args__ = (Index("ux_stock_market_symbol", "market", "symbol", unique=True),)


class StockPrice(Base):
    """일별 시세.

    **원주가와 수정주가를 나란히 두되 계산은 원주가만 쓴다** (FR-011, FR-012).
    수정주가는 배당·분할을 소급 반영한 값이라, 거기에 배당을 또 더하면 같은 배당이 두 번
    들어간다. 값은 그럴듯하고 차트도 매끄러워 알아챌 신호가 없다.

    수정주가는 **나중에 배당·분할이 생기면 과거 값이 바뀐다.** 원주가는 바뀌지 않는다 —
    재현성(FR-014)이 원주가에 기대는 근거다.

    **출처는 원주가를 주지 않는다**(006 T090 결함 5). 출처의 시가·종가는 받는 시점까지의 분할을
    소급 반영한 값이라, 어댑터가 그 뒤의 분할 비율을 곱해 **되살린 값**을 여기에 둔다(006 FR-034,
    research R6-18). 수정종가는 출처가 준 그대로다.
    """

    __tablename__ = "stock_price"

    stock_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("stock.id"), primary_key=True)
    quote_date: Mapped[dt.date] = mapped_column(Date, primary_key=True)
    open_raw: Mapped[Decimal] = mapped_column(PRICE)
    close_raw: Mapped[Decimal] = mapped_column(PRICE)
    close_adjusted: Mapped[Decimal | None] = mapped_column(PRICE, nullable=True)
    source: Mapped[str] = mapped_column(String(64))
    ingested_at: Mapped[dt.datetime] = mapped_column(TS, server_default=func.now())


class StockDividend(Base):
    """배당 이벤트. 배당락일을 지급 시점으로 다룬다.

    **세전 금액을 저장한다.** 세율은 설정이라 바뀌며(FR-016), 세후를 저장하면 세율을
    바꿨을 때 과거 행이 낡아 FR-017이 요구하는 재산출이 불가능해진다.
    """

    __tablename__ = "stock_dividend"

    stock_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("stock.id"), primary_key=True)
    ex_date: Mapped[dt.date] = mapped_column(Date, primary_key=True)
    amount_per_share: Mapped[Decimal] = mapped_column(PRICE)
    source: Mapped[str] = mapped_column(String(64))
    ingested_at: Mapped[dt.datetime] = mapped_column(TS, server_default=func.now())


class StockSplit(Base):
    """분할·병합 이벤트.

    **비율을 분자·분모 정수로 보관한다.** 소수로 저장하면 3:1 분할이 `0.333333…`이 되어
    보유 주식 수 계산에 오차가 들어간다. 병합(역분할)은 `numerator < denominator`다.

    이 테이블이 FR-010b가 요구하는 "적용한 이벤트의 기록"이다. 제공처를 그대로 믿기로
    했으므로(FR-010a), 틀렸을 때 되짚을 수단이 이것뿐이다.
    """

    __tablename__ = "stock_split"

    stock_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("stock.id"), primary_key=True)
    effective_date: Mapped[dt.date] = mapped_column(Date, primary_key=True)
    numerator: Mapped[int] = mapped_column(Integer)
    denominator: Mapped[int] = mapped_column(Integer)
    source: Mapped[str] = mapped_column(String(64))
    ingested_at: Mapped[dt.datetime] = mapped_column(TS, server_default=func.now())


class StockRawResponse(Base):
    """원본 응답 기록.

    주식 일봉은 한 번에 수천 행이 오므로 **처음부터 `MEDIUMTEXT`로 둔다.** 001이
    `fx_raw_response`에서 `TEXT`(65,535바이트)를 넘겨 마이그레이션을 한 번 더 했다.
    """

    __tablename__ = "stock_raw_response"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    # 검색 응답은 종목이 아직 없다.
    stock_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("stock.id"), nullable=True)
    kind: Mapped[str] = mapped_column(String(16))
    requested_from: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    requested_to: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    body: Mapped[str] = mapped_column(Text(length=16_777_215))
    status_code: Mapped[int] = mapped_column(SmallInteger)
    received_at: Mapped[dt.datetime] = mapped_column(TS, server_default=func.now())

    __table_args__ = (Index("ix_stock_raw_received", "received_at"),)


class StockCoverage(Base):
    """수집 구간. 종목당 한 행.

    FR-044의 "빠진 구간만 받는다"와 FR-045의 재개가 여기에 기댄다. `fx_coverage`와
    합치지 않는다 — 그쪽은 통화 단위이고 여기는 종목 단위다.
    """

    __tablename__ = "stock_coverage"

    stock_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("stock.id"), primary_key=True)
    covered_from: Mapped[dt.date] = mapped_column(Date)
    covered_through: Mapped[dt.date] = mapped_column(Date)
    updated_at: Mapped[dt.datetime] = mapped_column(
        TS, server_default=func.now(), onupdate=func.now())


class StockCollectionJob(Base):
    """수집 작업 이력. 컬럼은 `FxCollectionJob`과 같고 통화 자리에 종목이 들어간다."""

    __tablename__ = "stock_collection_job"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    stock_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("stock.id"))
    range_start: Mapped[dt.date] = mapped_column(Date)
    range_end: Mapped[dt.date] = mapped_column(Date)
    status: Mapped[JobStatus] = mapped_column(
        Enum(JobStatus, native_enum=False, length=16))
    chunks_total: Mapped[int] = mapped_column(Integer)
    chunks_done: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[dt.datetime] = mapped_column(TS, server_default=func.now())
    finished_at: Mapped[dt.datetime | None] = mapped_column(TS, nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (Index("ix_stock_job_status", "stock_id", "status"),)


class StockCollectionLock(Base):
    """종목별 단일 수집 작업 잠금.

    기본 키 INSERT 충돌이 곧 "이미 진행 중"을 뜻한다 (003이 FX에서 쓴 것과 같은 수단).

    **점유를 자산군을 가로질러 공유하지 않는다.** FX 수집 중에 주식 수집을 막을 이유가
    없고 출처가 달라 호출 한도도 따로다 (research R5-7).
    """

    __tablename__ = "stock_collection_lock"

    stock_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("stock.id"), primary_key=True)
    job_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("stock_collection_job.id"))
    acquired_at: Mapped[dt.datetime] = mapped_column(TS, server_default=func.now())
    heartbeat_at: Mapped[dt.datetime] = mapped_column(
        TS, server_default=func.now(), onupdate=func.now())


class StockSetting(Base):
    """수수료·세율. **전역 단일 행**이다.

    `fx_spread`는 통화별이지만 이쪽은 하나다. 시장별로 수수료가 다른 것이 현실이지만
    명세가 하나로 받는다 (FR-015).
    """

    __tablename__ = "stock_setting"

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, default=1)
    trade_fee_rate: Mapped[Decimal] = mapped_column(SPREAD)
    # : **국내** 배당 소득세(시장 KRX). 006 FR-055 이전에는 유일한 세율이었다 — 값과 이름을 그대로
    # 둔다.
    dividend_tax_rate: Mapped[Decimal] = mapped_column(SPREAD)
    #: 해외 배당 소득세(KRX 밖, 006 FR-055). 기본 15%.
    dividend_tax_rate_foreign: Mapped[Decimal] = mapped_column(
        SPREAD, server_default=text("0.150000"))
    #: 011 — 매도 세금(보드가 기준일에 모두 판다고 가정할 때). **NULL이면 기본값**이다(국내
    #: 0.20%·해외 22%·공제 2,500,000원 — `repository/stock_setting`의 상수). 수수료·배당 세율만
    #: 저장한 행도 그대로 읽힌다(010 반복 5 `residence_ratio`와 같은 규칙).
    sale_tax_rate_domestic: Mapped[Decimal | None] = mapped_column(SPREAD, nullable=True)
    capital_gains_rate_foreign: Mapped[Decimal | None] = mapped_column(SPREAD, nullable=True)
    #: 원 단위 정수 — 009의 `WON`과 같은 형(그 정의는 이 아래에 있다).
    capital_gains_deduction_foreign: Mapped[Decimal | None] = mapped_column(
        Numeric(15, 0, asdecimal=True), nullable=True)
    updated_at: Mapped[dt.datetime] = mapped_column(
        TS, server_default=func.now(), onupdate=func.now())


# ─────────────────────────── 006: 검색용 종목 목록 ───────────────────────────
#
# 시세를 담지 않는다. 시세는 005의 `stock_price`가 담는다 (006 FR-012).
# 시각은 UTC로 넣는다 — 기본값을 DB의 `now()`에 맡기면 DB 서버의 시간대가 끼어든다.


class StockListing(Base):
    """검색용 종목 (006 data-model 1절).

    **국가와 코드로 식별한다.** 단위는 키가 아니다 — 이전상장으로 단위가 바뀌어도 같은
    종목이다 (FR-019a). **지우지 않는다.** 최근 목록에 없으면 `missing`으로 표시한다 (FR-019).
    """

    __tablename__ = "stock_listing"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    country: Mapped[str] = mapped_column(String(2), nullable=False)
    code: Mapped[str] = mapped_column(String(16), nullable=False)
    unit: Mapped[str] = mapped_column(String(8), nullable=False)
    name_ko: Mapped[str | None] = mapped_column(String(128), nullable=True)
    name_en: Mapped[str | None] = mapped_column(String(256), nullable=True)
    kind: Mapped[str] = mapped_column(String(8), nullable=False)
    # 상장일. **시작 가능 날짜가 아니라 하한이다** (FR-005a, research R6-8).
    listed_on: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(
        String(8), nullable=False, default="listed", server_default=text("'listed'"))
    first_seen_at: Mapped[dt.datetime] = mapped_column(TS, nullable=False)
    last_seen_at: Mapped[dt.datetime] = mapped_column(TS, nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    ingested_at: Mapped[dt.datetime] = mapped_column(
        TS, nullable=False, server_default=func.now())

    __table_args__ = (
        Index("ux_stock_listing_country_code", "country", "code", unique=True),
        Index("ix_stock_listing_unit_status", "unit", "status"),
    )


class StockListingRefresh(Base):
    """목록 갱신 기록. 단위마다 한 행 (006 data-model 2절).

    `as_of`는 **온전히 받은 마지막 시각**이다. 실패하거나 일부만 받으면 바뀌지 않는다.
    `last_error`에는 키·토큰·인증 헤더를 담지 않는다 (FR-060).
    """

    __tablename__ = "stock_listing_refresh"

    unit: Mapped[str] = mapped_column(String(8), primary_key=True)
    as_of: Mapped[dt.datetime | None] = mapped_column(TS, nullable=True)
    as_of_date: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    row_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    attempt_date: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    # 하루 시도 횟수(FR-013a). 서버 기본값은 상수 리터럴이라 방언 차이가 없다 — ORM의
    # `default`만으로는 마이그레이션 밖에서 넣은 행이 NULL이 된다.
    attempts: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, default=0, server_default=text("0"))
    last_attempt_at: Mapped[dt.datetime | None] = mapped_column(TS, nullable=True)
    last_failed_at: Mapped[dt.datetime | None] = mapped_column(TS, nullable=True)
    last_error_kind: Mapped[str | None] = mapped_column(String(16), nullable=True)
    last_error: Mapped[str | None] = mapped_column(String(512), nullable=True)


class StockListingLock(Base):
    """갱신 점유 (006 data-model 3절).

    **기본 키 INSERT 충돌이 곧 "이미 갱신 중"이다** (헌법 DB 운영 규약). 005의 종목 점유와
    같은 수단이다.
    """

    __tablename__ = "stock_listing_lock"

    unit: Mapped[str] = mapped_column(String(8), primary_key=True)
    started_at: Mapped[dt.datetime] = mapped_column(TS, nullable=False)
    heartbeat_at: Mapped[dt.datetime] = mapped_column(TS, nullable=False)


class StockListingRawBody(Base):
    """원본 응답 본문. **같은 본문은 한 번만** 저장한다 (006 data-model 4a절, analyze C1).

    **지우지 않는다** — 헌법 원칙 V "원본 응답을 보존한다". 요청·응답 헤더를 담지 않는다 —
    인증 헤더가 섞인다 (FR-061).
    """

    __tablename__ = "stock_listing_raw_body"

    sha256: Mapped[str] = mapped_column(String(64), primary_key=True)
    body: Mapped[str] = mapped_column(Text(length=16_777_215), nullable=False)
    first_stored_at: Mapped[dt.datetime] = mapped_column(TS, nullable=False)


class StockListingRaw(Base):
    """원본 응답의 쪽 기록 (006 data-model 4절). 본문은 해시로 가리킨다."""

    __tablename__ = "stock_listing_raw"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    unit: Mapped[str] = mapped_column(String(8), nullable=False)
    batch_started_at: Mapped[dt.datetime] = mapped_column(TS, nullable=False)
    page_no: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    status_code: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    body_sha256: Mapped[str] = mapped_column(
        String(64), ForeignKey("stock_listing_raw_body.sha256"), nullable=False)
    fetched_at: Mapped[dt.datetime] = mapped_column(TS, nullable=False)


# ─────────────────────────── 007: 가상자산 ───────────────────────────
#
# 주식 테이블과 합치지 않는다 — 출처·식별·정밀도가 다르고 점유를 자산군끼리 공유하지 않는다
# (007 data-model). 시각은 UTC로 넣는다(006과 같다).

#: 가상자산 가격. 출처 원값이 소수 14자리로 온다 — 주식의 `PRICE`(소수 6자리)는 2e-12달러를 0으로
#: 만든다 (007 research R7-3·R7-13).
CPRICE = Numeric(36, 14, asdecimal=True)
#: 가상자산 거래량. SHIB 하루 2.6조 개.
CVOLUME = Numeric(38, 8, asdecimal=True)


class CryptoCoin(Base):
    """코인 (007 data-model 1절). 목록 한 줄이자 시뮬레이션의 대상이다.

    **(출처, 출처 식별자)로 식별한다.** 심볼은 유일하지 않다(169개 겹침, research R7-4) — 어떤
    조회도 심볼을 키로 쓰지 않는다(FR-004). **지우지 않는다** — 최근 목록에 없으면
    `missing`이다(FR-005a).
    """

    __tablename__ = "crypto_coin"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    source_id: Mapped[str] = mapped_column(String(32), nullable=False)
    slug: Mapped[str | None] = mapped_column(String(128), nullable=True)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    name_en: Mapped[str] = mapped_column(String(256), nullable=False)
    name_ko: Mapped[str | None] = mapped_column(String(256), nullable=True)
    quote_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    market_rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # `listed` / `missing`. 서버 기본값은 상수 리터럴뿐이다(006 `Stock`과 같다).
    status: Mapped[str] = mapped_column(
        String(8), nullable=False, default="listed", server_default=text("'listed'"))
    # 출처의 첫 일봉. **수집 중 발견한다**(research R7-10) — 상수가 아니다.
    first_available_date: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    first_seen_at: Mapped[dt.datetime] = mapped_column(TS, nullable=False)
    last_seen_at: Mapped[dt.datetime] = mapped_column(TS, nullable=False)
    ingested_at: Mapped[dt.datetime] = mapped_column(
        TS, nullable=False, server_default=func.now())

    __table_args__ = (
        Index("ux_crypto_coin_source_id", "source", "source_id", unique=True),
        Index("ix_crypto_coin_status", "status"),
    )


class CryptoCoinRefresh(Base):
    """목록 갱신 기록. 판(`en`·`ko`)마다 한 행 (007 data-model 2절). `as_of`는 온전히 받아 교체한
    마지막 시각이다."""

    __tablename__ = "crypto_coin_refresh"

    edition: Mapped[str] = mapped_column(String(4), primary_key=True)
    as_of: Mapped[dt.datetime | None] = mapped_column(TS, nullable=True)
    as_of_date: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    row_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    attempt_date: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    # 그날 시도 수. 서버 기본값은 상수 리터럴뿐이다.
    attempts: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, default=0, server_default=text("0"))
    last_attempt_at: Mapped[dt.datetime | None] = mapped_column(TS, nullable=True)
    last_failed_at: Mapped[dt.datetime | None] = mapped_column(TS, nullable=True)
    last_error_kind: Mapped[str | None] = mapped_column(String(16), nullable=True)
    last_error: Mapped[str | None] = mapped_column(String(512), nullable=True)


class CryptoListLock(Base):
    """목록 갱신 점유와 진행 (007 data-model 3절, FR-005b).

    기본 키 INSERT 충돌이 곧 "이미 갱신 중"이다. 갱신 줄이 쪽마다 진행 열을 고치고, 진행 스트림이
    프레임마다 읽는다. 갱신이 끝나면 행을 지운다 — 행이 없으면 갱신 중이 아니다.
    """

    __tablename__ = "crypto_list_lock"

    scope: Mapped[str] = mapped_column(String(16), primary_key=True)
    started_at: Mapped[dt.datetime] = mapped_column(TS, nullable=False)
    heartbeat_at: Mapped[dt.datetime] = mapped_column(TS, nullable=False)
    edition: Mapped[str | None] = mapped_column(String(4), nullable=True)
    # 진행 열. 서버 기본값은 상수 리터럴뿐이다.
    pages_done: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, default=0, server_default=text("0"))
    coins_seen: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0"))


class CryptoListRawBody(Base):
    """목록 원본 본문. **같은 본문은 한 번만**, 지우지 않는다(헌법 원칙 V). 헤더는 담지 않는다."""

    __tablename__ = "crypto_list_raw_body"

    sha256: Mapped[str] = mapped_column(String(64), primary_key=True)
    body: Mapped[str] = mapped_column(Text(length=16_777_215), nullable=False)
    first_stored_at: Mapped[dt.datetime] = mapped_column(TS, nullable=False)


class CryptoListRaw(Base):
    """목록 원본의 쪽 기록. 본문은 해시로 가리킨다."""

    __tablename__ = "crypto_list_raw"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    edition: Mapped[str] = mapped_column(String(4), nullable=False)
    batch_started_at: Mapped[dt.datetime] = mapped_column(TS, nullable=False)
    page_no: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    status_code: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    body_sha256: Mapped[str] = mapped_column(
        String(64), ForeignKey("crypto_list_raw_body.sha256"), nullable=False)
    fetched_at: Mapped[dt.datetime] = mapped_column(TS, nullable=False)


class CryptoDaily(Base):
    """일봉 (007 data-model 5절). **UTC 하루**다(research R7-3).

    마감된 UTC 하루만 들어온다 — 계산 끝(UTC 어제)보다 뒤의 행은 정규화에서 버린다(FR-022). 그래서
    잠정 열이 없다. 결측은 행이 없는 것으로 표현한다(헌법 원칙 V).
    """

    __tablename__ = "crypto_daily"

    coin_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("crypto_coin.id"), primary_key=True)
    day: Mapped[dt.date] = mapped_column(Date, primary_key=True)
    open: Mapped[Decimal] = mapped_column(CPRICE, nullable=False)
    high: Mapped[Decimal] = mapped_column(CPRICE, nullable=False)
    low: Mapped[Decimal] = mapped_column(CPRICE, nullable=False)
    close: Mapped[Decimal] = mapped_column(CPRICE, nullable=False)
    # 출처가 빈 값으로 준 날은 NULL이다 — 0이 아니다(FR-012a).
    volume: Mapped[Decimal | None] = mapped_column(CVOLUME, nullable=True)
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    ingested_at: Mapped[dt.datetime] = mapped_column(
        TS, nullable=False, server_default=func.now())


class CryptoRawResponse(Base):
    """일봉 원본. 응답 본문 그대로(오늘 일봉 포함) — 잠정에서 확정으로 바뀐 값을 사후에 되짚는
    근거다."""

    __tablename__ = "crypto_raw_response"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    coin_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("crypto_coin.id"), nullable=False)
    requested_from: Mapped[dt.date] = mapped_column(Date, nullable=False)
    requested_to: Mapped[dt.date] = mapped_column(Date, nullable=False)
    status_code: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    body: Mapped[str] = mapped_column(Text(length=16_777_215), nullable=False)
    received_at: Mapped[dt.datetime] = mapped_column(TS, nullable=False)

    __table_args__ = (Index("ix_crypto_raw_received", "received_at"),)


class CryptoCoverage(Base):
    """수집 구간. **요청한 구간**을 기록한다 — 일봉이 없던 구간도 다시 받으러 가지 않는다(005와
    같다)."""

    __tablename__ = "crypto_coverage"

    coin_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("crypto_coin.id"), primary_key=True)
    covered_from: Mapped[dt.date] = mapped_column(Date, nullable=False)
    covered_through: Mapped[dt.date] = mapped_column(Date, nullable=False)
    updated_at: Mapped[dt.datetime] = mapped_column(
        TS, server_default=func.now(), onupdate=func.now())


class CryptoCollectionJob(Base):
    """수집 작업. 열은 `StockCollectionJob`과 같고 종목 자리에 코인이 들어간다."""

    __tablename__ = "crypto_collection_job"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    coin_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("crypto_coin.id"), nullable=False)
    range_start: Mapped[dt.date] = mapped_column(Date, nullable=False)
    range_end: Mapped[dt.date] = mapped_column(Date, nullable=False)
    status: Mapped[JobStatus] = mapped_column(
        Enum(JobStatus, native_enum=False, length=16), nullable=False)
    chunks_total: Mapped[int] = mapped_column(Integer, nullable=False)
    chunks_done: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    started_at: Mapped[dt.datetime] = mapped_column(TS, server_default=func.now())
    finished_at: Mapped[dt.datetime | None] = mapped_column(TS, nullable=True)
    # 사유 종류(`blocked`·`format`·`network`·`empty`)를 앞에 둔다(FR-020).
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (Index("ix_crypto_job_status", "coin_id", "status"),)


class CryptoCollectionLock(Base):
    """코인별 단일 수집 작업 잠금. 기본 키 INSERT 충돌이 곧 "이미 진행 중"이다."""

    __tablename__ = "crypto_collection_lock"

    coin_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("crypto_coin.id"), primary_key=True)
    job_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("crypto_collection_job.id"), nullable=False)
    acquired_at: Mapped[dt.datetime] = mapped_column(TS, server_default=func.now())
    heartbeat_at: Mapped[dt.datetime] = mapped_column(
        TS, server_default=func.now(), onupdate=func.now())


class CryptoSetting(Base):
    """가상자산 설정. **전역 단일 행**, 주식 설정과 따로다(FR-032). 행이 없으면 기본값(0.1%)."""

    __tablename__ = "crypto_setting"

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, default=1)
    trade_fee_rate: Mapped[Decimal] = mapped_column(SPREAD, nullable=False)
    updated_at: Mapped[dt.datetime] = mapped_column(
        TS, server_default=func.now(), onupdate=func.now())


# ── 예금 (008) ────────────────────────────────────────────────────────────────
#
# 투자처는 테이블이 아니다 — 다섯으로 고정이고(FR-003) 출처의 통계표·항목 코드는 ECOS 어댑터 안에만
# 있다(헌법 원칙 II, research R8-1). DB에는 투자처 키(`commercial_bank` 등)만 둔다.
# **달은 그 달 1일의 DATE다** — 문자열(YYYYMM)이면 범위 비교가 문자열 비교가 된다.

# 금리는 연 % 그대로다(실측 최댓값 16.2, 소수 2자리 — 여유를 둔다, research R8-11).
RATE_PCT = Numeric(7, 4, asdecimal=True)


class DepositRate(Base):
    """월별 금리. **발표된 달만** 있다 — 잠정 금리는 저장하지 않는다(FR-024).
    이미 있는 달은 다시 받아도 바꾸지 않는다(research R8-4)."""

    __tablename__ = "deposit_rate"

    institution: Mapped[str] = mapped_column(String(24), primary_key=True)
    month: Mapped[dt.date] = mapped_column(Date, primary_key=True)
    rate: Mapped[Decimal] = mapped_column(RATE_PCT, nullable=False)
    source: Mapped[str] = mapped_column(String(16), nullable=False)
    ingested_at: Mapped[dt.datetime] = mapped_column(TS, nullable=False)


class DepositRawResponse(Base):
    """받은 원본. **요청 URL은 담지 않는다** — 인증키가 경로에 있다(FR-014).

    항목 목록은 통계표 하나가 여러 투자처를 덮으므로 투자처가 비고, `source_ref`는 어댑터가 준
    불투명한 참조다(analyze I2).
    """

    __tablename__ = "deposit_raw_response"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    institution: Mapped[str | None] = mapped_column(String(24), nullable=True)
    endpoint: Mapped[str] = mapped_column(String(24), nullable=False)
    source_ref: Mapped[str] = mapped_column(String(32), nullable=False)
    requested_from: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    requested_to: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    status_code: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    result_code: Mapped[str | None] = mapped_column(String(16), nullable=True)
    body: Mapped[str] = mapped_column(Text(length=16_777_215), nullable=False)
    received_at: Mapped[dt.datetime] = mapped_column(TS, nullable=False)

    __table_args__ = (Index("ix_deposit_raw_received", "received_at"),)


class DepositCoverage(Base):
    """받은 구간 `[first_month, latest_month]`과 마지막으로 확인한 날(한국 시간).

    그 안의 빈 달은 결측, 그 뒤의 달은 미발표다. `checked_on`은 확인이 **성공했을 때만**
    갱신한다(FR-010).
    """

    __tablename__ = "deposit_coverage"

    institution: Mapped[str] = mapped_column(String(24), primary_key=True)
    first_month: Mapped[dt.date] = mapped_column(Date, nullable=False)
    latest_month: Mapped[dt.date] = mapped_column(Date, nullable=False)
    checked_on: Mapped[dt.date] = mapped_column(Date, nullable=False)
    updated_at: Mapped[dt.datetime] = mapped_column(
        TS, server_default=func.now(), onupdate=func.now())


class DepositCollectionJob(Base):
    """수집 작업. 구간은 **그 실행에 필요한 구간**(시작 달 ~ 이번 달)이라 요청 때 늘 안다.

    진행(받은 달 / 받을 달)도 이 구간으로 센다(analyze I1·U2).
    """

    __tablename__ = "deposit_collection_job"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    institution: Mapped[str] = mapped_column(String(24), nullable=False)
    range_start: Mapped[dt.date] = mapped_column(Date, nullable=False)
    range_end: Mapped[dt.date] = mapped_column(Date, nullable=False)
    status: Mapped[JobStatus] = mapped_column(
        Enum(JobStatus, native_enum=False, length=16), nullable=False)
    months_total: Mapped[int] = mapped_column(Integer, nullable=False)
    months_done: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    started_at: Mapped[dt.datetime] = mapped_column(TS, server_default=func.now())
    finished_at: Mapped[dt.datetime | None] = mapped_column(TS, nullable=True)
    # 사유 종류(`auth`·`rate_limited`·`format`·`network`)를 앞에 둔다(FR-016).
    # 문구는 mask_secrets를 거친다.
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (Index("ix_deposit_job_status", "institution", "status"),)


class DepositCollectionLock(Base):
    """투자처별 단일 수집 작업 잠금. 기본 키 INSERT 충돌이 곧 "이미 진행 중"이다(FR-012)."""

    __tablename__ = "deposit_collection_lock"

    institution: Mapped[str] = mapped_column(String(24), primary_key=True)
    job_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("deposit_collection_job.id"), nullable=False)
    acquired_at: Mapped[dt.datetime] = mapped_column(TS, server_default=func.now())
    heartbeat_at: Mapped[dt.datetime] = mapped_column(
        TS, server_default=func.now(), onupdate=func.now())


class DepositSetting(Base):
    """예금 설정. **전역 단일 행**, 주식·가상자산 설정과 따로다(FR-030).

    행이 없으면 기본값(15.4%)이다.
    """

    __tablename__ = "deposit_setting"

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, default=1)
    interest_tax_rate: Mapped[Decimal] = mapped_column(SPREAD, nullable=False)
    updated_at: Mapped[dt.datetime] = mapped_column(
        TS, server_default=func.now(), onupdate=func.now())


# ── 009 부동산 — 아파트 매매 실거래 ───────────────────────────────────────────────────────────

#: 전용면적(㎡) — 출처는 소수 4자리까지 준다(`84.9725` — T001 실측). 반올림하면 85㎡ 경계와
#: 거래 키가 흔들리므로 받은 자릿수 그대로 둔다. 경계 비교는 Decimal로 한다(research R9-1·R9-2).
AREA = Numeric(9, 4, asdecimal=True)
#: 원 단위 금액 — 최고가 수백억도 담는다.
WON = Numeric(15, 0, asdecimal=True)


class AptRegion(Base):
    """행정구역(시·도·시·군·구·법정동). 갱신에서 사라진 코드는 지우지 않고 `retired_at`을 남긴다 —
    풀다운·요청에는 현존 코드만 쓴다(출처는 과거 거래도 새 코드로만 준다, research R9-3)."""

    __tablename__ = "apt_region"

    code: Mapped[str] = mapped_column(CHAR(10), primary_key=True)
    level: Mapped[str] = mapped_column(String(8), nullable=False)
    parent_code: Mapped[str | None] = mapped_column(CHAR(10), nullable=True)
    lawd_cd: Mapped[str | None] = mapped_column(CHAR(5), nullable=True)
    name: Mapped[str] = mapped_column(String(40), nullable=False)
    full_name: Mapped[str] = mapped_column(String(80), nullable=False)
    source: Mapped[str] = mapped_column(String(16), nullable=False)
    ingested_at: Mapped[dt.datetime] = mapped_column(TS, nullable=False)
    seen_at: Mapped[dt.datetime] = mapped_column(TS, nullable=False)
    retired_at: Mapped[dt.datetime | None] = mapped_column(TS, nullable=True)


class AptComplex(Base):
    """단지. 실거래(`apt_seq`)와 단지 목록(`kapt_code`)의 같은 단지는 한 행이다. **행을 지우지 않고
    id가 바뀌지 않는다** — 이력이 단지 id를 저장한다(FR-032). 합쳐진 행은 `merged_into`를 남긴다."""

    __tablename__ = "apt_complex"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    umd_code: Mapped[str] = mapped_column(CHAR(10), nullable=False)
    lawd_cd: Mapped[str] = mapped_column(CHAR(5), nullable=False)
    apt_seq: Mapped[str | None] = mapped_column(String(20), nullable=True, unique=True)
    kapt_code: Mapped[str | None] = mapped_column(String(20), nullable=True, unique=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    jibun: Mapped[str | None] = mapped_column(String(20), nullable=True)
    move_in_year: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    move_in_source: Mapped[str | None] = mapped_column(String(8), nullable=True)
    households: Mapped[int | None] = mapped_column(Integer, nullable=True)
    details_checked_at: Mapped[dt.datetime | None] = mapped_column(TS, nullable=True)
    merged_into: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    updated_at: Mapped[dt.datetime] = mapped_column(
        TS, server_default=func.now(), onupdate=func.now())


class AptComplexNaver(Base):
    """단지의 Npay 부동산 단지 번호(010 반복 3, FR-029, research R10-19). 단지 하나에 한 행 —
    공개되지 않은 단지 자동완성으로 **한 번** 찾아 저장해 다시 쓴다(헌법 원칙 II 이탈 — 출처를
    화면마다 부르지 않는다).

    `found`면 번호가 있고, `not_found`면 같은 법정동에서 고를 후보가 없거나 여럿이었다 —
    `checked_at`에서 정해진 날 수(설정)가 지나면 다시 찾는다. **실패(차단·요청 제한·연결·형식)는
    행을 만들지 않는다** — 일시 장애 하나로 그 단지가 영영 검색으로만 열리지 않게. 원본 응답을 함께
    둔다(헌법 원칙 V)."""

    __tablename__ = "apt_complex_naver"

    complex_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("apt_complex.id"), primary_key=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    naver_complex_no: Mapped[int | None] = mapped_column(Integer, nullable=True)
    naver_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    keyword: Mapped[str] = mapped_column(String(160), nullable=False)
    checked_at: Mapped[dt.datetime] = mapped_column(TS, nullable=False)
    raw_response: Mapped[str | None] = mapped_column(Text(length=16_777_215), nullable=True)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    ingested_at: Mapped[dt.datetime] = mapped_column(TS, server_default=func.now(), nullable=False)


class AptTrade(Base):
    """거래 하나. 유니크 키는 (자산 식별자, 날짜)를 **거래 사건**에 맞춘 것이다 — 같은 날 같은
    층·면적·금액의 다른 호가 있어 응답 안 순번까지 넣는다(research R9-4). 바뀌는
    필드(유형·해제·사라짐)만 upsert로 고친다. 해제·사라진 행은 지우지 않고 집계에서 뺀다."""

    __tablename__ = "apt_trade"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    lawd_cd: Mapped[str] = mapped_column(CHAR(5), nullable=False)
    deal_ym: Mapped[str] = mapped_column(CHAR(6), nullable=False)
    deal_date: Mapped[dt.date] = mapped_column(Date, nullable=False)
    apt_seq: Mapped[str] = mapped_column(String(20), nullable=False)
    umd_code: Mapped[str] = mapped_column(CHAR(10), nullable=False)
    jibun: Mapped[str] = mapped_column(String(20), nullable=False)
    apt_name: Mapped[str] = mapped_column(String(80), nullable=False)
    apt_dong: Mapped[str] = mapped_column(String(20), nullable=False)
    floor: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    excl_area: Mapped[Decimal] = mapped_column(AREA, nullable=False)
    amount: Mapped[Decimal] = mapped_column(WON, nullable=False)
    occurrence: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    dealing_type: Mapped[str | None] = mapped_column(String(8), nullable=True)
    cancelled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    cancelled_on: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    missing_since: Mapped[dt.datetime | None] = mapped_column(TS, nullable=True)
    # `absent`(다시 받은 응답에 없음) · `region_retired`(시·군·구 코드가 사라짐)
    missing_reason: Mapped[str | None] = mapped_column(String(16), nullable=True)
    source: Mapped[str] = mapped_column(String(16), nullable=False)
    ingested_at: Mapped[dt.datetime] = mapped_column(TS, nullable=False)
    updated_at: Mapped[dt.datetime] = mapped_column(
        TS, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("lawd_cd", "deal_date", "apt_seq", "apt_dong", "floor", "excl_area",
                         "amount", "occurrence", name="uq_apt_trade_event"),
        Index("ix_apt_trade_complex", "apt_seq", "deal_date"),
    )


class AptRawResponse(Base):
    """받은 원본. **요청 URL은 담지 않는다** — 인증키가 질의 문자열에 있다(FR-013). 같은 요청의
    마지막 원본과 본문이 같으면 새 행을 만들지 않는다(`body_sha256`) — 다른 판은 모두 남아 잠정→확정
    변화를 추적한다."""

    __tablename__ = "apt_raw_response"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    endpoint: Mapped[str] = mapped_column(String(24), nullable=False)
    request_ref: Mapped[str] = mapped_column(String(40), nullable=False)
    status_code: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    result_code: Mapped[str | None] = mapped_column(String(16), nullable=True)
    body: Mapped[str] = mapped_column(Text(length=16_777_215), nullable=False)
    body_sha256: Mapped[str] = mapped_column(CHAR(64), nullable=False)
    received_at: Mapped[dt.datetime] = mapped_column(TS, nullable=False)

    __table_args__ = (
        Index("ix_apt_raw_request", "endpoint", "request_ref", "received_at"),
        Index("ix_apt_raw_received", "received_at"),
    )


class AptTradeCoverage(Base):
    """받은 달(시·군·구 × 계약 월). 잠정(최근 12개월)은 다시 받는다 — 최근 3개월은 하루 한 번, 그
    앞은 한 달에 한 번. `checked_on`은 **성공했을 때만** 바뀐다(FR-010)."""

    __tablename__ = "apt_trade_coverage"

    lawd_cd: Mapped[str] = mapped_column(CHAR(5), primary_key=True)
    deal_ym: Mapped[str] = mapped_column(CHAR(6), primary_key=True)
    state: Mapped[str] = mapped_column(String(12), nullable=False)
    trade_rows: Mapped[int] = mapped_column(Integer, nullable=False)
    checked_on: Mapped[dt.date] = mapped_column(Date, nullable=False)
    updated_at: Mapped[dt.datetime] = mapped_column(
        TS, server_default=func.now(), onupdate=func.now())


class AptCollectionJob(Base):
    """수집 작업 — 실거래(시·군·구), 행정구역(전국), 단지 기본 정보(법정동). 진행은 종류마다 분모가
    달라도 `done`· `total` 한 쌍으로 읽는다(달·단지·쪽)."""

    __tablename__ = "apt_collection_job"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    target: Mapped[str] = mapped_column(String(20), nullable=False)
    total: Mapped[int] = mapped_column(Integer, nullable=False)
    done: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[JobStatus] = mapped_column(
        Enum(JobStatus, native_enum=False, length=16), nullable=False)
    started_at: Mapped[dt.datetime] = mapped_column(TS, server_default=func.now())
    finished_at: Mapped[dt.datetime | None] = mapped_column(TS, nullable=True)
    # 사유 종류(`auth`·`rate_limited`·`format`·`network`)를 앞에 둔다(FR-014). 문구는 키를 지운다.
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (Index("ix_apt_job_target", "kind", "target", "status"),)


class AptCollectionLock(Base):
    """같은 대상의 단일 수집 작업 잠금. 기본 키 INSERT 충돌이 곧 "이미 진행 중"이다(FR-012)."""

    __tablename__ = "apt_collection_lock"

    kind: Mapped[str] = mapped_column(String(16), primary_key=True)
    target: Mapped[str] = mapped_column(String(20), primary_key=True)
    job_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("apt_collection_job.id"), nullable=False)
    acquired_at: Mapped[dt.datetime] = mapped_column(TS, server_default=func.now())
    heartbeat_at: Mapped[dt.datetime] = mapped_column(
        TS, server_default=func.now(), onupdate=func.now())


class AptApiUsage(Base):
    """자료별 하루 호출 수(한국 시간 날짜). 보내기 **전에** 더하고 설정 한도를 넘으면 보내지
    않는다(SC-012)."""

    __tablename__ = "apt_api_usage"

    api: Mapped[str] = mapped_column(String(16), primary_key=True)
    kst_date: Mapped[dt.date] = mapped_column(Date, primary_key=True)
    calls: Mapped[int] = mapped_column(Integer, nullable=False)


class AptListState(Base):
    """목록 갱신 상태 — `regions`(전국), `umd:<법정동>`(그 동의 단지 목록), `sgg:<시·군·구>`(그
    시·군·구의 실거래, 처음 거래가 있는 달)."""

    __tablename__ = "apt_list_state"

    scope: Mapped[str] = mapped_column(String(20), primary_key=True)
    refreshed_at: Mapped[dt.datetime | None] = mapped_column(TS, nullable=True)
    first_trade_ym: Mapped[str | None] = mapped_column(CHAR(6), nullable=True)
    updated_at: Mapped[dt.datetime] = mapped_column(
        TS, server_default=func.now(), onupdate=func.now())


class AptSetting(Base):
    """부동산 설정. **전역 단일 행**, 다른 자산군 설정과 따로다(FR-034). 행이 없으면
    기본값(0.600000)이다."""

    __tablename__ = "apt_setting"

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, default=1)
    holding_tax_base_ratio: Mapped[Decimal] = mapped_column(SPREAD, nullable=False)
    #: 010 반복 5 — 거주 기간 비율(거주 기간 = 보유 기간 × 비율, 양도소득세의 비과세·장특공).
    #: NULL이면 기본값 1.000000(보유 내내 거주)이다 — 보유세 기준 비율만 저장한 행도 그대로 읽힌다.
    residence_ratio: Mapped[Decimal | None] = mapped_column(SPREAD, nullable=True)
    updated_at: Mapped[dt.datetime] = mapped_column(
        TS, server_default=func.now(), onupdate=func.now())


#: 012 — 이력의 자산군(`api/services/history_conditions.ASSET_CLASSES`와 같은 값).
HISTORY_ASSET_CLASSES = ("stock", "crypto", "deposit", "realestate")
#: 012 — 이력 보관 기간. NULL에 "기본값"과 "무기한" 두 뜻을 싣지 않으려 열거로 둔다(research R12-9).
HISTORY_RETENTIONS = ("days_7", "days_30", "days_90", "days_180", "days_365", "unlimited")


class SimulationHistory(Base):
    """최근 시뮬레이션 이력 한 항목 (012 FR-011, data-model 1.1). **조건만** 담는다 — 결과를 담지
    않는다(005 R5-9).

    `(asset_class, condition_key)`가 기본 키다 — 같은 조건은 한 행이다. `db/dialect.upsert`가 기본
    키로 충돌을 가른다. 조건은 서버가 정해진 차례로
    직렬화한 JSON 글이다 — JSON 열은 키 차례·숫자 표기를 바꿔 돌려줄 수 있다(원금 문자열이 수로
    바뀌는 길). 원금은 사용자가 친 입력의 기록이고 DB·서버가
    그것으로 계산하지 않는다(원칙 VI 해석 — plan Complexity Tracking).
    """

    __tablename__ = "simulation_history"
    __table_args__ = (Index("ix_simulation_history_list", "asset_class", "last_run_at"),)

    asset_class: Mapped[str] = mapped_column(
        Enum(*HISTORY_ASSET_CLASSES, native_enum=False, length=16, name="history_asset_class"),
        primary_key=True,
    )
    #: 조건 식별자 — 서버가 조건에서 계산한다(012 전 화면 lib 규칙과 같다). API의 `id`다.
    condition_key: Mapped[str] = mapped_column(String(255), primary_key=True)
    condition: Mapped[str] = mapped_column(Text, nullable=False)
    #: 마지막 실행 시각(UTC). 목록 차례다. 옮긴 항목은 브라우저의 `savedAt`이다.
    last_run_at: Mapped[dt.datetime] = mapped_column(TS, nullable=False)
    #: 보관 기준 시각(UTC) — 마지막 실행 시각, 옮긴 항목은 옮긴 시각(명확화 4). 보관 기간은 이것으로
    #: 잰다.
    retain_from: Mapped[dt.datetime] = mapped_column(TS, nullable=False)


class HistorySetting(Base):
    """이력 보관 기간 (012 FR-012). **전역 단일 행**이고 모든 자산군이 함께 쓴다. 행이 없으면 기본
    30일이다."""

    __tablename__ = "history_setting"

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, default=1)
    retention: Mapped[str] = mapped_column(
        Enum(*HISTORY_RETENTIONS, native_enum=False, length=16, name="history_retention"),
        nullable=False,
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        TS, server_default=func.now(), onupdate=func.now())


COMPARISON_ASSET_CLASSES = ("stock", "crypto", "deposit", "realestate")


class SavedComparison(Base):
    """저장한 비교 한 항목 (013 FR-016, data-model 1.1). **조건만** 담는다 — 결과를 담지 않는다.

    저장할 때마다 새 행이다(같은 조건·이름이어도 — 명확화 3). 보관 기간이 없다 — 지울 때까지
    남는다(012 이력 정리와 무관하다). 조건은 서버가 정해진 차례로 직렬화한 JSON 글이다(012
    `simulation_history`와 같은 까닭 — JSON 열은 금액 문자열을 수로 바꿔 돌려줄 수 있다). 금액 열이
    없다 — 조건 안의 금액은 받은 글자 그대로의 기록이다(원칙 VI 해석). 대상 테이블과 외래 키가
    없다 — 대상이 없어져도 저장한 비교는 남고 불러올 때 막힘으로 드러난다(FR-017).
    """

    __tablename__ = "saved_comparison"
    __table_args__ = (Index("ix_saved_comparison_list", "saved_at", "id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    #: 사용자가 붙인 이름 — 앞뒤 공백을 뺀 1~100자. 같은 이름이 여럿일 수 있다.
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    #: 자산군 — `condition`의 `asset`과 같다(목록 표시·검증용).
    asset_class: Mapped[str] = mapped_column(
        Enum(*COMPARISON_ASSET_CLASSES, native_enum=False, length=16,
             name="comparison_asset_class"),
        nullable=False,
    )
    condition: Mapped[str] = mapped_column(Text, nullable=False)
    #: 저장 시각(UTC, 초 단위). 목록 차례다.
    saved_at: Mapped[dt.datetime] = mapped_column(TS, nullable=False)


# ───────────────────────── 014: 대시보드 지표 ─────────────────────────


class MarketIndicatorDaily(Base):
    """대시보드 지표의 확정 종가 (014 data-model 1.1). `trade_date`는 **그 시장의 현지
    거래일**이다(R14-3).

    없는 날만 넣는다 — 있는 날의 값이 출처에서 바뀌면 덮어쓰지 않고 `market_close_revision`에
    남긴다(원칙 V 재현성). 오늘(현지)의
    봉과 종가가 빈 행(휴일 자리 표시)은 넣지 않는다 — 잠정 열이 없는 까닭이다. 환율 셋은 이 표가
    아니라 외환 고시 이력이다.
    """

    __tablename__ = "market_indicator_daily"

    indicator_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    trade_date: Mapped[dt.date] = mapped_column(Date, primary_key=True)
    #: 종가. 음수가 될 수 있다(WTI 2020-04-20 −37.63).
    close: Mapped[Decimal] = mapped_column(PRICE, nullable=False)
    #: 시가·고가·저가(반복 2026-10-10b). 출처가 주지 않거나 0이면 비운다 — 새 날만 넣고 덮지 않는다
    open_price: Mapped[Decimal | None] = mapped_column(PRICE, nullable=True)
    high_price: Mapped[Decimal | None] = mapped_column(PRICE, nullable=True)
    low_price: Mapped[Decimal | None] = mapped_column(PRICE, nullable=True)
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    ingested_at: Mapped[dt.datetime] = mapped_column(TS, nullable=False, server_default=func.now())


class MarketIndicatorRaw(Base):
    """지표 청크의 원본 응답 본문 그대로(오늘 봉 포함) — 잠정에서 확정으로 바뀐 값을 사후에 되짚는
    근거다(014 data-model 1.2)."""

    __tablename__ = "market_indicator_raw"
    __table_args__ = (Index("ix_market_raw_received", "indicator_id", "received_at"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    indicator_id: Mapped[str] = mapped_column(String(32), nullable=False)
    requested_from: Mapped[dt.date] = mapped_column(Date, nullable=False)
    requested_to: Mapped[dt.date] = mapped_column(Date, nullable=False)
    status_code: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    body: Mapped[str] = mapped_column(Text(length=16_777_215), nullable=False)
    received_at: Mapped[dt.datetime] = mapped_column(TS, nullable=False)


class MarketIndicatorCoverage(Base):
    """지표마다의 수집 상태 (014 data-model 1.3) — 발견한 첫 날, **요청한** 연속 구간, 마지막
    성공·실패(FR-019)."""

    __tablename__ = "market_indicator_coverage"

    indicator_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    #: 출처의 첫 거래일 — 응답의 첫 거래일 정보에서 발견해 기록한다(코드에 날짜를 두지 않는다).
    first_day: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    covered_from: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    covered_through: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    last_success_at: Mapped[dt.datetime | None] = mapped_column(TS, nullable=True)
    last_failure_at: Mapped[dt.datetime | None] = mapped_column(TS, nullable=True)
    #: `connection`·`rate_limited`·`blocked`·`invalid_body`·`not_found`
    last_failure_kind: Mapped[str | None] = mapped_column(String(32), nullable=True)
    last_failure_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    updated_at: Mapped[dt.datetime | None] = mapped_column(
        TS, server_default=func.now(), onupdate=func.now())


class MarketCloseRevision(Base):
    """확정으로 저장한 날의 값이 다시 받을 때 달랐던 사실 (014 data-model 1.4). 저장 값은 그대로다.
    """

    __tablename__ = "market_close_revision"
    __table_args__ = (
        UniqueConstraint(
            "indicator_id", "trade_date", "source_close", name="ux_market_close_revision"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    indicator_id: Mapped[str] = mapped_column(String(32), nullable=False)
    trade_date: Mapped[dt.date] = mapped_column(Date, nullable=False)
    stored_close: Mapped[Decimal] = mapped_column(PRICE, nullable=False)
    source_close: Mapped[Decimal] = mapped_column(PRICE, nullable=False)
    detected_at: Mapped[dt.datetime] = mapped_column(TS, nullable=False)
