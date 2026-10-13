"""투자 비교 설정 (014 반복 2026-10-13)

투자 비교 화면의 더하기 한도 — 최대 대상 수 — 를 저장한다(014 FR-044, data-model 18). 테이블 하나:
- `comparison_setting` — 전역 단일 행(`id` 늘 1). `max_targets`는 2~100이고 검증은 서비스가 한다(DB `CHECK` 없음 — 다른 설정
  테이블과 같다). 행이 없으면 기본 20이다(서비스)

기존 테이블은 바꾸지 않는다 — 저장한 비교의 조건 열(TEXT)도 그대로다(길이는 서비스가 막는다).

Revision ID: c7d4e2a9b615
Revises: e9f3b7c2a4d1
Create Date: 2026-10-13
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c7d4e2a9b615"
down_revision: str | None = "e9f3b7c2a4d1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TS = sa.DateTime(timezone=False)


def upgrade() -> None:
    op.create_table(
        "comparison_setting",
        sa.Column("id", sa.SmallInteger(), nullable=False),
        sa.Column("max_targets", sa.SmallInteger(), nullable=False),
        sa.Column("updated_at", TS, server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("comparison_setting")
