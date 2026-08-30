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


def test_잠금_테이블의_기본키가_통화다() -> None:
    """research R6: 기본 키 INSERT 충돌이 곧 잠금 획득 실패."""
    pk = [c.name for c in Base.metadata.tables["fx_collection_lock"].primary_key.columns]
    assert pk == ["currency_code"]


def test_잠금_테이블에_생성컬럼이_없다() -> None:
    """헌법 v4.0.0: DB 종속 문법(생성 컬럼) 금지."""
    for t in Base.metadata.tables.values():
        for c in t.columns:
            assert c.computed is None, f"{t.name}.{c.name}이 생성 컬럼이다"
