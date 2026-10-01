"""ORM 타입 매핑 테스트 (T012).

헌법 원칙 VI: 금액·비율은 DECIMAL이어야 하며 ORM 필드도 DECIMAL로 매핑되어야 한다.
ORM은 Float 매핑을 쉽게 허용하므로 메타데이터 수준에서 강제한다 (research R7).
"""
from decimal import Decimal

from sqlalchemy import Float, Numeric

from src.db.models import Base

# 금액·비율을 담는 컬럼 — 반드시 DECIMAL로 매핑되어야 한다
MONETARY_COLUMNS = {
    ("fx_rate", "base_rate"),
    ("fx_spread", "cash_buy"),
    ("fx_spread", "cash_sell"),
    ("fx_spread", "remit_send"),
    ("fx_spread", "remit_receive"),
}


def test_메타데이터에_Float_컬럼이_없다() -> None:
    """헌법 원칙 VI: FLOAT/DOUBLE 사용 금지."""
    offenders = [
        f"{t.name}.{c.name}"
        for t in Base.metadata.tables.values()
        for c in t.columns
        if isinstance(c.type, Float)
    ]
    assert offenders == [], f"부동소수점 컬럼 발견: {offenders}"


def test_금액_비율_컬럼이_Numeric으로_매핑된다() -> None:
    tables = Base.metadata.tables
    for table_name, col_name in MONETARY_COLUMNS:
        assert table_name in tables, f"{table_name} 테이블이 없다"
        col = tables[table_name].columns[col_name]
        assert isinstance(col.type, Numeric), f"{table_name}.{col_name}가 Numeric이 아니다"


def test_금액_컬럼이_Decimal로_반환된다() -> None:
    """asdecimal=False면 float으로 돌아와 원칙 VI가 무력화된다."""
    tables = Base.metadata.tables
    for table_name, col_name in MONETARY_COLUMNS:
        col = tables[table_name].columns[col_name]
        assert col.type.asdecimal is True, f"{table_name}.{col_name}.asdecimal이 False"
        assert col.type.python_type is Decimal


def test_정밀도와_스케일이_research_R7과_일치한다() -> None:
    t = Base.metadata.tables
    rate = t["fx_rate"].columns["base_rate"].type
    assert (rate.precision, rate.scale) == (18, 6)
    spread = t["fx_spread"].columns["cash_buy"].type
    assert (spread.precision, spread.scale) == (9, 6)


def test_data_model의_7개_테이블이_모두_정의된다() -> None:
    expected = {"currency", "fx_rate", "fx_raw_response", "fx_coverage",
                "fx_spread", "fx_collection_job", "fx_collection_lock"}
    assert expected <= set(Base.metadata.tables), \
        f"누락: {expected - set(Base.metadata.tables)}"


def test_시계열_복합_기본키가_통화와_날짜다() -> None:
    """헌법 원칙 V: (자산 식별자, 날짜) 복합 유니크 키로 멱등성 보장."""
    pk = [c.name for c in Base.metadata.tables["fx_rate"].primary_key.columns]
    assert pk == ["currency_code", "quote_date"]


def test_잠금_획득이_기본키_충돌로_판정된다() -> None:
    """research R6: 기본 키 INSERT 충돌이 곧 잠금 획득 실패.

    002에서 `scope`가 키에 추가됐다(research R2-8). 통화 하나로만 잠그면 오늘 새로고침이
    대량 수집과 충돌해 FR-036a("새로고침은 수집과 독립")를 어긴다. 판정 수단이 기본 키
    충돌이라는 성질은 그대로다.
    """
    pk = [c.name for c in Base.metadata.tables["fx_collection_lock"].primary_key.columns]
    assert "currency_code" in pk, "통화가 잠금 키에서 빠지면 통화별 단일 실행이 깨진다"
    assert "scope" in pk, "범위가 없으면 수집과 새로고침이 서로를 막는다"


def test_잠금_테이블에_생성컬럼이_없다() -> None:
    """헌법 v4.0.0: DB 종속 문법(생성 컬럼) 금지."""
    for t in Base.metadata.tables.values():
        for c in t.columns:
            assert c.computed is None, f"{t.name}.{c.name}이 생성 컬럼이다"

def test_잠정_구분_컬럼이_불리언이며_기본값이_거짓이다() -> None:
    """헌법 v5.0.0 원칙 V: 확정과 잠정을 구분해 저장해야 한다 (T003).

    기존 행은 전부 확정값이므로 기본값이 거짓이어야 한다. 기본값이 참이면
    마이그레이션 이후 과거 데이터가 통째로 잠정으로 오인된다.
    """
    from sqlalchemy import Boolean

    col = Base.metadata.tables["fx_rate"].columns["is_provisional"]
    assert isinstance(col.type, Boolean), "is_provisional이 불리언이 아니다"
    assert not col.nullable, "is_provisional은 NOT NULL이어야 한다"
    assert col.server_default is not None, "기존 행을 채울 서버 기본값이 필요하다"


def test_잠금_테이블의_기본키가_범위와_통화다() -> None:
    """FR-036a: 수집 잠금과 새로고침 잠금이 같은 통화에서 공존해야 한다 (T003)."""
    pk = [c.name for c in Base.metadata.tables["fx_collection_lock"].primary_key.columns]
    assert set(pk) == {"scope", "currency_code"}, f"기본 키가 {pk}"


# ─────────────────────────── 005: 주식 시뮬레이션 ───────────────────────────

#: 005가 더한 금액·비율 컬럼 (T103).
STOCK_MONETARY_COLUMNS = {
    ("stock_price", "open_raw"),
    ("stock_price", "close_raw"),
    ("stock_price", "close_adjusted"),
    ("stock_dividend", "amount_per_share"),
    ("stock_setting", "trade_fee_rate"),
    ("stock_setting", "dividend_tax_rate"),
}


def test_주식_금액_컬럼이_Decimal로_매핑된다() -> None:
    """T103 — 헌법 원칙 VI. `asdecimal=False`면 float으로 돌아와 원칙이 무력화된다."""
    tables = Base.metadata.tables
    for table_name, col_name in STOCK_MONETARY_COLUMNS:
        assert table_name in tables, f"{table_name} 테이블이 없다"
        col = tables[table_name].columns[col_name]
        assert isinstance(col.type, Numeric), f"{table_name}.{col_name}가 Numeric이 아니다"
        assert col.type.asdecimal is True, f"{table_name}.{col_name}.asdecimal이 False"
        assert col.type.python_type is Decimal


def test_분할_비율이_정수다() -> None:
    """분할은 **비율이 아니라 분자·분모**다.

    `1.5`로 저장하면 3:2 분할과 15:10 분할을 구별할 수 없고, 무엇보다 소수로 적는
    순간 주식 수 계산이 부동소수를 탄다 (원칙 VI).
    """
    from sqlalchemy import Integer

    cols = Base.metadata.tables["stock_split"].columns
    assert isinstance(cols["numerator"].type, Integer)
    assert isinstance(cols["denominator"].type, Integer)


def test_data_model의_주식_테이블이_모두_정의된다() -> None:
    expected = {
        "stock", "stock_price", "stock_dividend", "stock_split",
        "stock_raw_response", "stock_coverage", "stock_collection_job",
        "stock_collection_lock", "stock_setting",
    }
    assert expected <= set(Base.metadata.tables), \
        f"누락: {expected - set(Base.metadata.tables)}"


def test_주식_시계열_복합_기본키가_종목과_날짜다() -> None:
    """헌법 시계열 불변식 — `(자산 식별자, 날짜)` 복합 키 + upsert로 멱등성 확보."""
    pk = [c.name for c in Base.metadata.tables["stock_price"].primary_key.columns]
    assert pk == ["stock_id", "quote_date"]


def test_주식_점유가_종목_단위다() -> None:
    """research R5-7 — 자산군을 가로질러 공유하지 않는다.

    통화 단위 점유와 한 테이블에 섞으면 FX 수집이 주식 수집을 막으면서 그 이유가
    화면 어디에도 드러나지 않는다.
    """
    pk = [c.name for c in
          Base.metadata.tables["stock_collection_lock"].primary_key.columns]
    assert pk == ["stock_id"]
