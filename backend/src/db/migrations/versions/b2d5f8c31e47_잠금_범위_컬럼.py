"""잠금 범위 컬럼 추가 (T063)

FR-036a: 오늘 새로고침이 대량 수집 잠금과 독립적으로 동작해야 한다.
기존 기본 키가 `currency_code` 하나여서 새로고침이 같은 테이블을 쓰면 수집과 충돌한다.

범위를 키에 더하면 001이 세운 메커니즘(기본 키 INSERT 충돌 = 진행 중, 하트비트로
스테일 회수)을 그대로 재사용하면서 두 요구를 동시에 만족한다 (research R2-8).

잠금은 실행 중에만 존재하는 휘발성 데이터이므로 기존 행을 비우고 진행해도 무방하다.

Revision ID: b2d5f8c31e47
Revises: a1c4e7b90d21
Create Date: 2026-08-30

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'b2d5f8c31e47'
down_revision: str | Sequence[str] | None = 'a1c4e7b90d21'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _fk_names(conn: sa.Connection, column: str) -> list[str]:
    """`fx_collection_lock`의 해당 컬럼을 참조하는 외래 키 이름.

    초기 스키마가 제약에 이름을 주지 않아 DB가 자동 생성한다(`..._ibfk_N`). 이름을
    가정하지 않고 조회하는 이유는 그 규칙이 DB마다 다르기 때문이다.
    """
    rows = conn.execute(sa.text(
        "SELECT constraint_name FROM information_schema.key_column_usage "
        "WHERE table_schema = DATABASE() AND table_name = 'fx_collection_lock' "
        "AND column_name = :col AND referenced_table_name IS NOT NULL"
    ), {"col": column}).all()
    return [r[0] for r in rows]


def upgrade() -> None:
    # 잠금은 휘발성이다. 남아 있던 행은 프로세스가 죽은 흔적이므로 비우고 시작한다.
    op.execute("DELETE FROM fx_collection_lock")
    op.add_column(
        "fx_collection_lock",
        sa.Column("scope", sa.String(20), nullable=False,
                  server_default="collection",
                  comment="잠금 종류: collection | today_refresh"),
    )

    # MySQL은 외래 키가 참조 중인 PRIMARY 인덱스를 드롭하지 못한다. 잠시 떼었다 붙인다.
    conn = op.get_bind()
    fks = _fk_names(conn, "currency_code")
    for name in fks:
        op.drop_constraint(name, "fx_collection_lock", type_="foreignkey")

    op.drop_constraint("PRIMARY", "fx_collection_lock", type_="primary")
    op.create_primary_key("pk_fx_collection_lock", "fx_collection_lock",
                          ["scope", "currency_code"])

    op.create_foreign_key("fk_lock_currency", "fx_collection_lock", "currency",
                          ["currency_code"], ["code"])


def downgrade() -> None:
    op.execute("DELETE FROM fx_collection_lock")
    op.drop_constraint("fk_lock_currency", "fx_collection_lock", type_="foreignkey")
    op.drop_constraint("pk_fx_collection_lock", "fx_collection_lock", type_="primary")
    op.create_primary_key("PRIMARY", "fx_collection_lock", ["currency_code"])
    op.create_foreign_key("fk_lock_currency", "fx_collection_lock", "currency",
                          ["currency_code"], ["code"])
    op.drop_column("fx_collection_lock", "scope")
