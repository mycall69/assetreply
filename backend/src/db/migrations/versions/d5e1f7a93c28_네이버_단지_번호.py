"""Npay 부동산 단지 번호 (010 반복 3)

테이블 하나를 더한다(data-model 8.2) — 단지의 Npay 부동산 단지 번호를 단지 하나에 한 행으로 저장한다
(공개되지 않은 단지 자동완성으로 한 번 찾는다 — 헌법 원칙 II 이탈, research R10-19). 기존 테이블은
바꾸지 않는다. 실패는 행을 만들지 않는다.

Revision ID: d5e1f7a93c28
Revises: a9d3e5c71f20
Create Date: 2026-10-06
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d5e1f7a93c28"
down_revision: str | None = "a9d3e5c71f20"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TS = sa.DateTime(timezone=False)
MEDIUMTEXT = sa.Text(length=16_777_215)


def upgrade() -> None:
    op.create_table(
        "apt_complex_naver",
        sa.Column("complex_id", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("naver_complex_no", sa.Integer(), nullable=True),
        sa.Column("naver_name", sa.String(120), nullable=True),
        sa.Column("keyword", sa.String(160), nullable=False),
        sa.Column("checked_at", TS, nullable=False),
        sa.Column("raw_response", MEDIUMTEXT, nullable=True),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("ingested_at", TS, server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["complex_id"], ["apt_complex.id"],
                                name="fk_apt_complex_naver_complex"),
        sa.PrimaryKeyConstraint("complex_id"),
    )


def downgrade() -> None:
    op.drop_table("apt_complex_naver")
