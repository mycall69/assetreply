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
    dividend_tax_rate: Mapped[Decimal] = mapped_column(SPREAD)
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
